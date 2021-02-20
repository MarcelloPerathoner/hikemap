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

# import scipy.spatial.distance

from shapely.strtree import STRtree
import shapely.ops
from shapely import wkt, wkb
from shapely.geometry import MultiLineString, LineString, MultiPoint, Point, Polygon
from shapely.geometry import box, mapping
from shapely.prepared import prep

from tqdm import tqdm

import connect
geokatalog = sys.modules[__name__] # pseudo-import this module


# We test the equality of an osm-route and geokatalog-route in two steps:
#
# 1. Test if every segment of the geokatalog route is contained in a buffer
# around the OSM route.
#
# 2. Test if every segment of the OSM route is contained in a buffer around the
# geokatalog route.
#
# In an OSM route a segment can be any of 'main', 'alternative', 'connection',
# 'approach', 'excursion' etc.  In geokatalog a route may be split in segments
# at admin borders but often also in a quite arbitrary fashion.
#
# Thus the OSM route and the geokatalog route may turn out to be split into
# segments in different (and sometimes interesting) ways.

total = 0
matched = 0

BUFFER   = 100.0
# RESAMPLE = 100.0

# SRS_BZIT = EPSG:25832    # ETRS89 / UTM zone 32N used by provinz.bz.it
# SRS_WGS  = EPSG:4326     # WGS84

# geokatalog .geojson is lon,lat in WGS84
# osm api data is also in WGS
# we transform both into an UTM projection, that allows easy distance calculations
transformer  = Transformer.from_crs ("EPSG:4326", "EPSG:25832", always_xy = True)
itransformer = Transformer.from_crs ("EPSG:25832", "EPSG:4326", always_xy = True)

# def dist (a, b):
#     """ Since we are using UTM we can use a simple euclidean distance. """
#     return math.sqrt ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)


# def _distance (coords1, coords2):
#     """ Return Hausdorff distance in m """

#     hd1 = scipy.spatial.distance.directed_hausdorff (coords1, coords2)

#     # hd2 = scipy.spatial.distance.directed_hausdorff (coords2, coords1)
#     # hd = max (hd1[0], hd2[0])

#     a = coords1[hd1[1]]
#     b = coords2[hd1[2]]
#     return dist (a, b)


# def coords (geom):
#     if geom.is_empty:
#         return []
#     if geom.type in ('LineString', 'LinearRing'):
#         return geom.coords
#     if geom.type.startswith ('Multi') or geom.type == 'GeometryCollection':
#         return [c for l in geom for c in l.coords ]
#     return []


# def resample (geom, threshold):
#     """Resample the linestrings in geometry.

#     After resampling the distance between consecutive points in a linestring
#     will be no longer than threshold.

#     """

#     if geom.is_empty:
#         return geom

#     if geom.type in ('LineString', 'LinearRing'):
#         pts = []
#         last_pt = geom.coords[0]

#         for pt in geom.coords:
#             d = dist (pt, last_pt)
#             if d > threshold:
#                 # add some points in between
#                 long_line = LineString ([last_pt, pt])
#                 i = threshold
#                 while i <= d:
#                     pts.append (long_line.interpolate (i))
#                     i += threshold
#             pts.append (pt)
#             last_pt = pt

#         return type (geom) (pts)

#     elif geom.type.startswith ('Multi') or geom.type == 'GeometryCollection':
#         return type (geom) ([ resample (part, threshold) for part in geom.geoms])

#     return geom


gk_routes  = dict ()
osm_routes = dict ()
gk_routes_by_id = dict ()  # needed for STRtree
osm_routes_by_id = dict () # needed for STRtree
gk_tree = None  # STRtree
osm_tree = None # STRtree


def buffer (geom):
    """ Buffer the route geometry. """
    return geom.buffer (BUFFER)


def clip_area (geom):
    """ Clip route geometry to the area of interest. """
    return boundary_utm.intersection (geom)


def match_route (rtags, gk_props):
    """ See if these routes match using metadata only. """

    ref  = rtags.get ('ref:geokatalog', rtags.get ('ref', ''))
    name = rtags.get ('name:geokatalog', rtags.get ('name:de', rtags.get ('name', '')))

    gk_ref  = str (gk_props.get ('WEGENR',     ''))
    gk_name = str (gk_props.get ('ROUTENNAME', ''))

    if ref and gk_ref == ref:
        return True

    # special case for CAI Trentino Est
    m = re.match (r'^E(\d\d\d)$', ref)
    if m and gk_ref == m.group (1):
        return True

    if gk_name and gk_name in name.split (';'):
        return True

    return False


def get_relation (osm_relation):
    rel_id = osm_relation['id']
    try:
        rfull = connect.relation_full (rel_id)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 410:
            # relation not found
            return None
        raise

    try:
        relation = rfull[-1]
        rtags = relation['tags']
        res = {
            'id'         : rel_id,
            'properties' : rtags,
            'relation'   : relation,
            'rfull'      : rfull,
        }

        geom = connect.osm_relation_as_multilinestring (rfull)
        geom = shapely.ops.transform (transformer.transform, geom)
        # geom = resample (geom, RESAMPLE)

        res['geometry'] = geom
        res['geometry'].id = rel_id

        clipped = connect.osm_relation_as_multilinestring (rfull, True)
        clipped = shapely.ops.transform (transformer.transform, clipped)

        # clipped = resample (clipped, RESAMPLE)
        clipped = clip_area (clipped)

        if not clipped.is_empty:
            res['clipped']  = clipped
            res['buffered'] = buffer (geom)

    except KeyError:
        return None

    return res


def process_gk_route (gk_dict):
    lines = gk_dict['lines']
    geom = shapely.ops.linemerge ([ wkb.loads (l, hex = True) for l in lines ])
    if geom.type == 'LineString':
        geom = MultiLineString ([geom])
    geom = shapely.ops.transform (transformer.transform, geom)

    # geom = resample (geom, RESAMPLE)
    gk_dict['geometry'] = geom

    clipped = clip_area (geom)
    if not clipped.is_empty:
        gk_dict['clipped']  = clipped
        gk_dict['buffered'] = buffer (geom)

    return gk_dict


def init (osm_relations, filenames):
    """ Build a spatial index tree of the features. """

    global gk_tree, osm_tree

    geokatalog.log = logging.getLogger ().log

    log (INFO, "preparing areas")

    geokatalog.boundary_utm = shapely.ops.transform (transformer.transform, connect.boundary)
    geokatalog.boundary_utm_prep = prep (boundary_utm)

    log (INFO, "getting OSM routes from OSM API")

    with Pool () as p:
        geoms = list (tqdm (p.imap (get_relation, osm_relations),
                            total = len (osm_relations),
                            desc = 'OSM Routes'))

    geoms = [ g for g in geoms if g is not None and 'buffered' in g]
    for g in geoms:
        osm_routes[g['id']] = g
        osm_routes_by_id[id (g['buffered'])] = g

    osm_tree = STRtree ([ g['buffered'] for g in geoms ])

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
                gk_ref  = str (props.get ('WEGENR', '.'))
                gk_name = str (props.get ('ROUTENNAME', '.'))
                gk_id   = str (props.get ('ID'))
                if gk_ref == '.' and gk_name == '.':
                    continue

                # fix data errors
                if re.match (r'Dolomiten.*öhenweg', gk_name):
                    if gk_ref != '.':
                        props['WEGENR'] = 'AV' + gk_ref
                    else:
                        m = re.search (r'(\d)$', gk_name)
                        if m:
                            props['WEGENR'] = 'AV' + m.group (1)

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
    for g in geoms:
        gk_id = g['id']
        g['geometry'].id = gk_id
        gk_routes[gk_id] = g

    gk_tree = STRtree ([ g['geometry'] for g in geoms ])

    log (INFO, "  %d relations found in geokatalog" % len (geoms))



def check_osm_covered (rel_id, errors):
    """For every chunk in the osm route there must be a route in geokatalog with
    matching ref or name that covers it.

    This triggers if the osm route is too long.  It does not trigger if the osm
    route is too short.

    """

    rel   = osm_routes[rel_id]
    rtags = rel['properties']

    osm_mls    = rel['clipped']
    osm_buffer = rel['buffered']

    # search geokatalog for one or more routes that may be used to cover it
    matches = []

    # try matching on metadata
    # we need this because an OSM route can be matched by more than one GK routes
    for gk_mls in gk_tree.query (osm_buffer):
        # sometimes two very short routes run in parallel, so we need a bit of
        # buffer to make them intersect
        if gk_mls.intersects (osm_buffer):
            gk_id = gk_mls.id
            gk_route = gk_routes[gk_id]
            if 'buffered' in gk_route:
                m = match_route (rtags, gk_route['properties'])
                if m:
                    matches.append (gk_route)

    if not matches:
        errors.append ((ERROR, 'Route not found in geokatalog.'))
        return

    match = shapely.ops.unary_union (list (m['buffered'] for m in matches))

    if not match.contains (osm_mls):
        d = osm_mls.difference (match)
        errors.append ((ERROR, 'OSM route outside GK buffer for {length:.0f}m. Matched {matches}'.format (
            length = d.length,
            matches = '; '.join ([ connect.format_gk_route (m['properties']) for m in matches]))))
        d = shapely.ops.transform (itransformer.transform, d)
        errors.append ((ERROR, 'http://localhost:8111/load_and_zoom?left={0:.6f}&right={2:.6f}&top={3:.6f}&bottom={1:.6f}'.format (*d.bounds)))

    elif errors:
        # not an error but good to have in the report
        errors.append ((ERROR, 'Fully covered by {matches}'.format (
            matches = '; '.join ([ connect.format_gk_route (m['properties']) for m in matches]))))


def check_geokatalog_covered (gk_id, errors):
    """For every geokatalog route there must be a route in osm with matching ref or
    name that covers it.

    This triggers if the osm route is too short.  It does not trigger if the osm
    route is too long.

    """

    gk_route   = gk_routes[gk_id]
    gk_props   = gk_route['properties']
    gk_clipped = gk_route['clipped']

    matches = []

    # search osm for routes that intersect and match on metadata
    for osm_buffer in osm_tree.query (gk_clipped):
        rel = osm_routes_by_id[id (osm_buffer)]
        if osm_buffer.intersects (gk_clipped):
            if match_route (rel['properties'], gk_props):
                matches.append (rel)

    if not matches:
        errors.append ((ERROR, 'No intersecting osm route matches with ref or name.'))
        c = shapely.ops.transform (itransformer.transform, gk_clipped)
        errors.append ((ERROR, 'http://localhost:8111/zoom?left={0:.6f}&right={2:.6f}&top={3:.6f}&bottom={1:.6f}'.format (*c.bounds)))
        return

    osm_buffer = shapely.ops.unary_union (list (m['buffered'] for m in matches))

    if not osm_buffer.contains (gk_clipped):
        d = gk_clipped.difference (osm_buffer)
        errors.append ((ERROR, 'GK route outside OSM buffer for {length:.0f}m. Matched {matches}'.format (
            length = d.length,
            matches = '; '.join ([ connect.format_route (m['relation']) for m in matches]))))
        d = shapely.ops.transform (itransformer.transform, d)
        errors.append ((ERROR, 'http://localhost:8111/load_and_zoom?left={0:.6f}&right={2:.6f}&top={3:.6f}&bottom={1:.6f}'.format (*d.bounds)))
