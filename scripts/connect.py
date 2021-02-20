#!/usr/bin/python3

import logging
from logging import ERROR, WARN, INFO, DEBUG
from pathlib import Path
import pprint
import re
import sys
from multiprocessing import Pool

import requests
import osmapi

import shapely.ops
from shapely.geometry import MultiLineString, LineString, MultiPoint, Point, MultiPolygon, Polygon, LinearRing, box
from shapely import wkt, wkb

from tqdm import tqdm

connect = sys.modules[__name__] # pseudo-import this module

MY_UID = 8199540

BOUNDARY_ST = (
    47046, # South Tyrol
)

CHUNKS = {
     934999 : 2, # Hike: "Sentiero Europeo E5, Italia", Gap @ Bolzano
     959876 : 2, # Road: LS64 Gap @ Kastelruth
    1657836 : 2, # Hike: AV3 (incomplete mapping)
}
"""Expected no. of chunks for routes that for some reason have more than one
chunk."""

HIKING_TYPES = ('foot', 'hiking', 'worship')
""" Hiking route types. """

CHECKED_TYPES = HIKING_TYPES + ('bicycle', 'mtb', 'piste', 'ski', 'bus', 'road')
""" Route types we check. """


# Transform a string so that numbers in the string sort naturally.
#
# Transform any contiguous run of digits so that it sorts
# naturally during an alphabetical sort. Every run of digits gets
# the length of the run prepended, eg. 123 => 3123, 123456 =>
# 6123456.

def natural_sort (s):
    def f (m):
        s = m.group (0)
        return str (len (s)) + s
    return re.sub ('\d+', f, s)


def way_is_way (way, clip_exceptions = False):
    # only consider these kinds of ways

    wtags = way.get ('tags')
    if clip_exceptions and 'geokatalog:exception' in wtags:
        return False

    return wtags and ('highway'       in wtags or
                      'razed:highway' in wtags or
                      'railway'       in wtags or
                      'aerialway'     in wtags or
                      'piste:type'    in wtags)


def way_is_area (way):
    # check if the way should be treated as area
    # in an area all points are valid entry and exit points
    wtags  = way.get ('tags')
    wnodes = way.get ('nodes')

    area       = wtags and wtags.get ('area', '') == 'yes'
    roundabout = wtags and wtags.get ('junction', '') in ('roundabout', 'circular')
    closed     = wnodes[0] == wnodes[-1]
    return closed and (area or roundabout)


def format_route (relation):
    rtags  = relation['tags']
    rel_id = relation['id']

    route = rtags.get ('route', '')
    ref   = rtags.get ('ref', '')
    name  = ' "%s"' % rtags['name'] if 'name' in rtags else ''

    return 'OSM {route} route {ref} (id: {rel_id}){name}'.format (route = route, ref = ref, rel_id = rel_id, name = name)


def format_gk_route (props):
    id_  = props.get ('ID',     '')
    ref  = props.get ('WEGENR', '')
    name = props.get ('ROUTENNAME')
    name = ' "%s"' % name if name else ''

    return 'GK route {ref} (id: {id}){name}'.format (ref = ref, name = name, id = id_)


# Overpass answer mode: ids tags bb
#
# {
#   "elements": [
#   {
#     "type": "relation",
#     "id": 2461906,
#     "bounds": {
#       "minlat": 46.5498064,
#       "minlon": 11.6867462,
#       "maxlat": 46.5944804,
#       "maxlon": 11.8388519
#     },
#     "tags": {
#       "network": "lwn",
#       "osmc:symbol": "red:red:white_bar:2:black",
#       "ref": "2",
#       "route": "hiking",
#       "type": "route"
#     }
#   },
#    ]
# }

def query (q):
    url = "http://overpass-api.de/api/interpreter"
    q   = "[out:json];\n\n%s" % q

    r = requests.post (url, data = {'data' : q})
    r.raise_for_status ()

    return r.json ().get ('elements', [])


def relations_in_areas (area_ids, types = CHECKED_TYPES):
    areas = ''.join ('area(%d);' % (3600000000 + int (id_)) for id_ in area_ids)
    types = '|'.join (types)

    q = """
    ({areas})->.location;
    (
        relation["route"~"{types}"](area.location);
        relation["abandoned:route"~"{types}"](area.location);
    );
    out ids;
    """.format (areas = areas, types = types)

    return query (q)


def osm_relation_as_multilinestring (rfull, clip_exceptions = False):
    """ Return an OSM relations as multilinestring.

    Optionally remove ways marked as exceptions.
    """

    try:
        relation = rfull[-1]

        nodes_dict = dict ([(n['id'], n) for n in rfull if n['type'] == 'node'])
        ways_dict  = dict ([(w['id'], w) for w in rfull if w['type'] == 'way'])

        ways = [ ways_dict[m['ref']] for m in relation['members'] if m['type'] == 'way' ]

        lines = []
        for way in ways:
            if way_is_way (way, clip_exceptions):
                nodes = way['nodes']
                lines.append (LineString ([ (nodes_dict[n]['lon'], nodes_dict[n]['lat']) for n in nodes ]))

        mls = shapely.ops.linemerge (lines)
        if mls.type == 'LineString':
            return MultiLineString ([mls])
        return mls
    except KeyError:
        log (ERROR, "KeyError in relation %s" % format_route (relation))
        raise


def get_area (area_id):
    area_id = int (area_id)
    rfull = relation_full (area_id)
    relation = rfull[-1]
    # log (DEBUG, "relation %s" % relation)

    nodes_dict = dict ([(n['id'], n) for n in rfull if n['type'] == 'node'])
    ways_dict  = dict ([(w['id'], w) for w in rfull if w['type'] == 'way'])

    ways = [ m['ref'] for m in relation['members'] if m['type'] == 'way' and m['role'] == 'outer' ]
    lines = []
    for way in ways:
        nodes = [ nodes_dict[n] for n in ways_dict[way]['nodes'] ]
        ls = LineString ([ (n['lon'], n['lat']) for n in nodes ])
        assert ls.is_simple, "way %d is not simple" % way
        lines.append (ls)

    ls = shapely.ops.linemerge (lines)
    assert ls.type == 'LineString', "Area %d is not a LineString" % area_id
    assert ls.is_simple,            "Area %d is not simple" % area_id
    assert ls.is_ring,              "Area %d is not a ring" % area_id

    result, dangles, cuts, invalids = shapely.ops.polygonize_full (ls)
    #log (DEBUG, "result: %s"   % result.wkt[:1000])
    #log (DEBUG, "dangles: %s"  % dangles.wkt[:1000])
    #log (DEBUG, "cuts: %s"     % cuts.wkt[:1000])
    #log (DEBUG, "invalids: %s" % invalids.wkt[:1000])

    polys = list (result)

    assert len (polys) == 1, "Area %d must have 1 polygon (but has %d instead)" % (area_id, len (polys))
    return polys


def relation_full (rel_id):
    url = 'https://api.openstreetmap.org/api/0.6/relation/{rel_id}/full.json'
    r = requests.get (url.format (rel_id = rel_id))
    r.raise_for_status ()

    return r.json ()['elements']


def init ():
    connect.log = logging.getLogger ().log
    connect.api = osmapi.OsmApi (passwordfile = Path ("~/.osmpass").expanduser ())

    # area_ids = BOUNDARY_ST + tuple (sys.args.areas)
    area_ids = tuple (sys.args.areas)
    with Pool () as p:
        polys = list (tqdm (
            p.imap (get_area, area_ids),
            total = len (area_ids),
            desc = 'Areas'
        ))

    polys = [p for sublist in polys for p in sublist] # flatten list of lists
    # connect.boundary_south_tyrol = polys.pop (0)
    connect.boundary = shapely.ops.unary_union (polys)
