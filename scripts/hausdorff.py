#!/usr/bin/python3

import collections
import itertools
import math
import operator
import json
import re
import sys

import osmapi
import sqlalchemy

import scipy.spatial.distance

from shapely.strtree import STRtree
import shapely.ops
from shapely import wkt, wkb
from shapely.geometry import MultiLineString, LineString, MultiPoint, Point, Polygon, box
from shapely.prepared import prep

from pyproj import CRS, Transformer

import connect

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


# load geoportal.provinz.bz.it data

boundary_utm = None
boundary_south_tyrol_utm = None
boundary_utm_prep = None
gk_routes = dict ()
gk_tree = None
osm_tree = None

def init (osm_relations, filenames):
    """ Build a spatial index tree of the features. """

    global boundary_utm, boundary_south_tyrol_utm, boundary_utm_prep
    global gk_routes, gk_tree, osm_tree

    # poly = wkb.loads (connect.boundary, hex = True)
    boundary_utm = shapely.ops.transform (transformer.transform, connect.boundary)
    boundary_utm_prep = prep (boundary_utm)

    # poly = wkb.loads (connect.boundary_south_tyrol, hex = True)
    boundary_south_tyrol_utm = shapely.ops.transform (transformer.transform, connect.boundary_south_tyrol)

    # get osm route relations from overpass

    geoms = []
    for rel in osm_relations:
        id_   = rel['id']
        props = rel['tags']
        b     = rel['bounds']
        geom  = shapely.ops.transform (
            transformer.transform,
            box (b['minlon'], b['minlat'], b['maxlon'], b['maxlat'])
        )

        if boundary_utm_prep.intersects (geom):
            geom.id    = id_
            geom.props = props
            geoms.append (geom)

    print ("hausdorff init: %d relations found in osm" % len (geoms))

    osm_tree = STRtree (geoms)

    # get geokatalog routes from geojson files

    geoms_by_id = collections.defaultdict (set)
    props_by_id = dict ()

    for filename in filenames:
        with open (filename, 'r') as fp:
            data = json.load (fp)

            for feature in data['features']:
                props = feature['properties']

                # '.' is placeholder in geoportal data
                ref   = props.get ('WEGENR', '.')
                name  = props.get ('ROUTENNAME', '.')
                gk_id = str (props.get ('ID'))
                if ref == '.' and name == '.':
                    continue

                # coords is lon,lat
                line = LineString (feature['geometry']['coordinates'])
                # eliminate duplicates, wkb makes it hashable
                geoms_by_id[gk_id].add (line.wkb_hex)

                props_by_id[gk_id] = props

    geoms = []
    for gk_id, lines in geoms_by_id.items ():
        geom = shapely.ops.linemerge ([ wkb.loads (l, hex = True) for l in lines ])
        geom = shapely.ops.transform (transformer.transform, geom)
        geom = resample (geom, RESAMPLE)

        if geom.type == 'LineString':
            geom = MultiLineString ([geom])

        if boundary_utm_prep.intersects (geom):
            props = props_by_id[gk_id]
            geom.props = props
            geoms.append (geom)
            gk_routes[gk_id] = {
                'properties' : props,
                'geometry'   : geom,
            }

    print ("hausdorff init: %d relations found in geokatalog" % len (geoms))

    gk_tree = STRtree (geoms)



def check_osm_covered (rfull):
    """For every chunk in the osm route there must be a route in geokatalog with
    matching id, ref or name that covers it.

    This triggers if the osm route is too long.  It does not trigger if the osm
    route is too short.

    """

    relation = rfull[-1]['data']
    rtags    = relation['tag']
    route    = rtags['route']
    members  = relation['member']
    errors = []

    ref    = rtags.get ('ref')
    name   = rtags.get ('name:de', rtags.get ('name'))
    ref_gk = rtags.get ('ref:geokatalog', [])
    if ref_gk:
        ref_gk = ref_gk.split (';')

    osm_mls = connect.osm_relation_as_multilinestring (rfull)
    osm_mls = shapely.ops.transform (transformer.transform, osm_mls)

    # Take of the osm route only what's inside South Tyrol because in geokatalog
    # many routes are drawn only up to or little beyond the border.
    osm_coords = []
    splits = shapely.ops.split (osm_mls, boundary_south_tyrol_utm)
    if len (splits) > 1:
        # N.B.: This convoluted way is actually faster that filtering the
        # points like: osm_coords = filter
        # (boundary_south_tyrol_utm.contains, line.coords)
        for l in splits:
            n = len (l.coords)
            if Point (l.coords[n // 2]).within (boundary_south_tyrol_utm):
                osm_coords += l.coords
    else:
        for ls in osm_mls:
            osm_coords += ls.coords

    # search geokatalog for one or more routes that may be used to cover it
    gk_coords = []
    best_gk_match = None

    for mls in gk_tree.query (osm_mls):
        props = mls.props

        gk_id   = str (props.get ('ID',         ''))
        gk_ref  = str (props.get ('WEGENR',     ''))
        gk_name = str (props.get ('ROUTENNAME', ''))

        # stitch the segments
        if (gk_id in ref_gk) or (gk_ref == ref) or (gk_name == name):
            best_gk_match = props
            for ls in mls:
                gk_coords += ls.coords

    if not best_gk_match:
        errors.append ('  Route not found in geokatalog.')
        return errors

    d = _distance (osm_coords, gk_coords)
    if d > 100:
        errors.append ('  Not fully covered. Best match is {best} with error = {d:.0f}m'.format (
            d = d, best = connect.format_gk_route (best_gk_match)))

    return errors


def check_geokatalog_covered (gk_id):
    """For every chunk in the geokatalog route there must be a route in osm with
    matching id, ref or name that covers it.

    This triggers if the osm route is too short.  It does not trigger if the osm
    route is too long.

    """

    errors = []

    gk_route = gk_routes[gk_id]
    gk_mls   = gk_route['geometry']

    props   = gk_route['properties']
    gk_ref  = props.get ('WEGENR',     '')
    gk_name = props.get ('ROUTENNAME', '')

    found   = False
    matched = False
    covered = False
    min_d   = 9999999
    best_osm_match = None

    gk_coords = []
    for ls in gk_mls:
        gk_coords += ls.coords

    # search osm for one or more routes that may be used to cover it
    for osm_bbox in osm_tree.query (gk_mls):
        rel_id = osm_bbox.id
        rtags  = osm_bbox.props

        ref    = rtags.get ('ref')
        name   = rtags.get ('name:de', rtags.get ('name'))
        ref_gk = rtags.get ('ref:geokatalog')

        found  = True

        if ref == gk_ref or ref_gk == gk_id or name == gk_name:
            matched = True
            # good candidate route
            # check if the osm route covers the geokatalog chunk

            rfull = connect.api.RelationFull (rel_id)
            osm_mls = connect.osm_relation_as_multilinestring (rfull)
            osm_mls = shapely.ops.transform (transformer.transform, osm_mls)
            osm_mls = resample (osm_mls, RESAMPLE)

            osm_coords = []
            for ls in osm_mls:
                osm_coords += ls.coords

            d = _distance (gk_coords, osm_coords)
            if d < min_d:
                best_osm_match = rfull[-1]['data']
                min_d = d
            if d < 100:
                covered = True
                break

    if not found:
        errors.append ('  No osm route intersects it.')
    elif not matched:
        errors.append ('  No intersecting osm route matches with ref or name or ref:geokatalog.')
    elif not covered:
        errors.append ('  Not fully covered. Best match is {best} with error = {d:.0f}m'.format
                       (d = min_d, best = connect.format_route (best_osm_match)))
    if errors:
        errors.insert (0, connect.format_gk_route (props))

    return errors
