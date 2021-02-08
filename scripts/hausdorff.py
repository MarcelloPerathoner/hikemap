#!/usr/bin/python3

import collections
import itertools
import logging
from logging import ERROR, WARN, INFO, DEBUG
import math
import operator
import json
import re
import sys
from multiprocessing import Pool

import requests

from pyproj import Transformer

import scipy.spatial.distance

from shapely.strtree import STRtree
import shapely.ops
from shapely import wkt, wkb
from shapely.geometry import MultiLineString, LineString, MultiPoint, Point, Polygon
from shapely.geometry import box, mapping
from shapely.prepared import prep

from tqdm import tqdm


import connect
hd = sys.modules[__name__] # pseudo-import this module


# We test the equality of an osm-route and geokatalog-route in two steps:
#
# 1. Test if the whole osm-route covers every segment of the geokatalog-route.
#
# 2. Test if the whole geokatalog route covers every segment of the osm route.
#
# In an osm-route a segment can be any of 'main', 'alternative', 'connection',
# 'approach', 'excursion' etc.  In geokatalog a route may be divided in
# segments in a quite arbitrary fashion.
#
# Thus the osm-route and the geokatalog-route may turn out to be cut into
# segments in different and sometimes interesting ways.

total = 0
matched = 0

RESAMPLE = 100.0

# SRS_BZIT = EPSG:25832    # ETRS89 / UTM zone 32N used by provinz.bz.it
# SRS_WGS  = EPSG:4326     # WGS84

# geokatalog .geojson is lon,lat in WGS84
# osm api data is also in WGS
# we transform both into a projection that allows easy distance calculations
transformer  = Transformer.from_crs ("EPSG:4326", "EPSG:25832", always_xy = True)
itransformer = Transformer.from_crs ("EPSG:25832", "EPSG:4326", always_xy = True)

def dist (a, b):
    """ Since we are using UTM we can use a simple euclidean distance. """
    return math.sqrt ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)


def _distance (coords1, coords2):
    """ Return Hausdorff distance in m """

    hd1 = scipy.spatial.distance.directed_hausdorff (coords1, coords2)

    # hd2 = scipy.spatial.distance.directed_hausdorff (coords2, coords1)
    # hd = max (hd1[0], hd2[0])

    a = coords1[hd1[1]]
    b = coords2[hd1[2]]
    return dist (a, b)


def resample (geom, threshold):
    """Resample the linestrings in geometry.

    After resampling the distance between consecutive points in a linestring
    will be no longer than threshold.

    """

    if geom.is_empty:
        return geom

    if geom.type in ('LineString', 'LinearRing'):
        pts = []
        last_pt = geom.coords[0]

        for pt in geom.coords:
            d = dist (pt, last_pt)
            if d > threshold:
                # add some points in between
                long_line = LineString ([last_pt, pt])
                i = threshold
                while i <= d:
                    pts.append (long_line.interpolate (i))
                    i += threshold
            pts.append (pt)
            last_pt = pt

        return type (geom) (pts)

    elif geom.type.startswith ('Multi') or geom.type == 'GeometryCollection':
        return type (geom) ([ resample (part, threshold) for part in geom.geoms])

    return geom


def clip_st (geom):
    """ Clip geometry to South Tyrol.

    Take of the routes only what's inside South Tyrol because in geokatalog
    many routes are drawn only up to or little beyond the border.
    """

    splits = shapely.ops.split (geom, boundary_south_tyrol_utm)

    # N.B.: This convoluted way is actually faster than filtering the
    # points like: filter (boundary_south_tyrol_utm.contains, line.coords)
    lines = []
    for l in splits:
        n = len (l.coords)
        if Point (l.coords[n // 2]).within (boundary_south_tyrol_utm):
            lines.append (l)

    return MultiLineString (lines)


# load geoportal.provinz.bz.it data

gk_routes = dict ()
osm_routes = dict ()
gk_tree = None
osm_tree = None


def match_route (rtags, gk_props):
    """ See if these routes match using metadata only.
    Return True / False / None """

    ref  = rtags.get ('ref:geokatalog', rtags.get ('ref', ''))
    name = rtags.get ('name:geokatalog', rtags.get ('name:de', rtags.get ('name', '')))

    gk_ref  = str (gk_props.get ('WEGENR',     ''))
    gk_name = str (gk_props.get ('ROUTENNAME', ''))

    if (gk_ref == ref):
        return True

    # special case for CAI Trentino Est
    m = re.match (r'^E(\d\d\d)$', ref)
    if m and gk_ref == m.group (1):
        return True

    if (gk_ref and ref and gk_ref != ref):
        return False

    if (gk_name != name):
        return None

    return True


def get_relation (osm_relation):
    rel_id = osm_relation['id']
    try:
        rfull = connect.relation_full (rel_id)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 410:
            # relation not found
            return None
        raise

    relation = rfull[-1]
    rtags = relation['tags']
    geom = connect.osm_relation_as_multilinestring (rfull)
    geom = shapely.ops.transform (transformer.transform, geom)
    geom = clip_st (geom)
    geom = resample (geom, RESAMPLE)

    if boundary_utm_prep.intersects (geom):
        log (DEBUG, "OSM relation %s inside boundaries" % rel_id)

        return {
            'id'         : rel_id,
            'geometry'   : geom,
            'properties' : rtags,
            'rfull'      : rfull,
        }

    log (DEBUG, "OSM relation %s outside boundaries" % rel_id)
    return None


def process_gk_route (gk_dict):
    lines = gk_dict['lines']
    geom = shapely.ops.linemerge ([ wkb.loads (l, hex = True) for l in lines ])
    if geom.type == 'LineString':
        geom = MultiLineString ([geom])
    geom = shapely.ops.transform (transformer.transform, geom)
    geom = clip_st (geom)
    geom = resample (geom, RESAMPLE)

    if boundary_utm_prep.intersects (geom):
        gk_dict['geometry'] = geom
        return gk_dict

    return None


def init (osm_relations, filenames):
    """ Build a spatial index tree of the features. """

    global gk_routes, gk_tree, osm_tree

    hd.log = logging.getLogger ().log

    log (INFO, "preparing areas")

    hd.boundary_utm = shapely.ops.transform (transformer.transform, connect.boundary)
    hd.boundary_utm_prep = prep (boundary_utm)

    hd.boundary_south_tyrol_utm = shapely.ops.transform (transformer.transform, connect.boundary_south_tyrol)
    hd.boundary_south_tyrol_utm = boundary_south_tyrol_utm.simplify (10)
    hd.boundary_south_tyrol_utm_prep = prep (boundary_south_tyrol_utm)

    # get osm route relations from overpass

    log (INFO, "getting OSM routes from OSM API")

    with Pool () as p:
        geoms = list (tqdm (p.imap (get_relation, osm_relations),
                            total = len (osm_relations),
                            desc = 'OSM Routes'))

    geoms = [ g for g in geoms if g is not None ]
    for geom in geoms:
        osm_routes[geom['id']] = geom
        geom['geometry'].id = geom['id']

    osm_tree = STRtree ([ g['geometry'] for g in geoms ])

    log (INFO, "  %d relations found in osm" % len (geoms))

    # get geokatalog routes from geojson files

    geoms_by_id = dict ()

    for filename in set (filenames):
        with open (filename, 'r') as fp:
            log (INFO, "reading %s" % filename)

            data = json.load (fp)

            for feature in data['features']:
                props = feature['properties']

                # '.' is placeholder in geoportal data
                ref   = str (props.get ('WEGENR', '.'))
                name  = str (props.get ('ROUTENNAME', '.'))
                gk_id = str (props.get ('ID'))
                if ref == '.' and name == '.':
                    continue

                coords = feature['geometry']['coordinates']
                # coords is lon,lat
                line = LineString (coords)

                if gk_id not in geoms_by_id:
                    geoms_by_id[gk_id] = {
                        'id'         : gk_id,
                        'properties' : props,
                        'lines'      : set (),
                    }

                # this eliminates duplicate geometries, wkb makes it hashable
                geoms_by_id[gk_id]['lines'].add (line.wkb_hex)

    log (INFO, "processing GK routes")

    with Pool () as p:
        geoms = list (tqdm (p.imap (process_gk_route, geoms_by_id.values ()),
                            total = len (geoms_by_id),
                            desc = 'GK Routes'))

    geoms = [ g for g in geoms if g is not None ]

    for geom in geoms:
        gk_routes[geom['id']] = geom
        geom['geometry'].id = geom['id']

    gk_tree = STRtree ([ g['geometry'] for g in geoms ])

    log (INFO, "  %d relations found in geokatalog" % len (geoms))



def check_osm_covered (rel_id, errors):
    """For every chunk in the osm route there must be a route in geokatalog with
    matching id, ref or name that covers it.

    This triggers if the osm route is too long.  It does not trigger if the osm
    route is too short.

    """

    rel    = osm_routes[rel_id]
    rtags  = rel['properties']

    osm_mls = rel['geometry']
    osm_coords = [ c for ls in osm_mls for c in ls.coords ]

    # search geokatalog for one or more routes that may be used to cover it
    matches = []
    maybees = []

    # try matching on metadata
    # we need this because an OSM route can be matched by more than one GK routes
    for gk_mls in gk_tree.query (osm_mls):
        if gk_mls.intersects (osm_mls):
            gk_id = gk_mls.id
            gk_props = gk_routes[gk_id]['properties']
            m = match_route (rtags, gk_props)
            if m is None:
                maybees.append (gk_mls)
            if m:
                matches.append (gk_mls)

    if not matches:
        # get the best-matching geometry
        min_d = 9999999
        for gk_mls in maybees:
            gk_coords = [ c for ls in gk_mls for c in ls.coords ]
            d = _distance (osm_coords, gk_coords)
            if d < min_d:
                min_d = d
                matches = [gk_mls]

    if not matches:
        errors.append ((ERROR, 'Route not found in geokatalog.'))
        return

    gk_coords = [ c for mls in matches for ls in mls for c in ls.coords ]

    d = _distance (osm_coords, gk_coords)
    if d > 100:
        errors.append ((ERROR, 'Not fully covered. Matched {matches} with error = {d:.0f}m'.format (
            d = d, matches = '; '.join ([ connect.format_gk_route (gk_routes[m.id]['properties']) for m in matches]))))
    elif errors:
        # not an error but good to have in the report
        errors.append ((ERROR, 'Fully covered by {matches}'.format (
            matches = '; '.join ([ connect.format_gk_route (gk_routes[m.id]['properties']) for m in matches]))))


def check_geokatalog_covered (gk_id, errors):
    """For every chunk in the geokatalog route there must be a route in osm with
    matching ref or name that covers it.

    This triggers if the osm route is too short.  It does not trigger if the osm
    route is too long.

    """

    gk_route  = gk_routes[gk_id]
    gk_props  = gk_route['properties']
    gk_mls    = gk_route['geometry']
    gk_coords = [c for ls in gk_mls for c in ls.coords ]
    if not gk_coords:
        return

    found   = False
    covered = False

    matches = []
    maybees = []

    # search osm for one or more routes that may be used to cover it
    # try matching on metadata
    for osm_mls in osm_tree.query (gk_mls):
        if gk_mls.intersects (osm_mls):
            rel_id  = osm_mls.id
            rel     = osm_routes[rel_id]
            rtags   = rel['properties']

            m = match_route (rtags, gk_props)
            if m is None:
                maybees.append (osm_mls)
            if m:
                matches.append (osm_mls)

    if not matches:
        # get the best-matching geometry
        min_d = 9999999
        for osm_mls in maybees:
            rel_id  = osm_mls.id
            rel     = osm_routes[rel_id]
            rtags   = rel['properties']

            # osm_mls = rel['geometry']
            found   = True

            # check if the osm route covers the geokatalog chunk
            osm_coords = [ c for ls in osm_mls for c in ls.coords ]
            if not osm_coords:
                return

            d = _distance (gk_coords, osm_coords)
            if d < min_d:
                min_d = d
                matches = [osm_mls]

    if not matches:
        errors.append ((ERROR, 'No intersecting osm route matches with ref or name.'))
        return

    osm_coords = [ c for mls in matches for ls in mls for c in ls.coords ]
    d = _distance (gk_coords, osm_coords)

    if d > 100:
        errors.append ((ERROR, 'Not fully covered. Best match is {matches} with error = {d:.0f}m'.format
                       (d = d, matches = '; '.join ([
                           connect.format_route (osm_routes[osm_mls.id]['rfull'][-1]) for osm_mls in matches
                       ]))))
