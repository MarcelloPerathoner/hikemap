#!/usr/bin/python3

import collections
import os
from pathlib import Path
import pprint

import requests
import sqlalchemy
import osmapi

import shapely.ops
from shapely.geometry import MultiLineString, LineString, MultiPoint, Point, MultiPolygon, Polygon, box


MY_UID = 8199540

BOUNDARY_ST = (
    47046, # South Tyrol
)

BOUNDARY_REL = (
    47242, # Sëlva
    47244, # S. Crestina
    47265, # Urtijëi
)

BOUNDARY_REL2 = (
    47234, # Ciastel
    47275, # Laion
    47274, # Waidbruck
    47232, # Völs
    47218, # Tiers

    47252, # Corvara
    47255, # Badia
    47276, # St. Martin de Tor
    47278, # Mareo
    47289, # La Val

    47285, # Toblach
    47286, # Sexten
    47301, # Prags
    47309, # Innichen
    47311, # Olang
    47312, # Welsberg
    47313, # Niederdorf
    47316, # St. Lorenzen
    47317, # Bruneck
    47324, # Kiens
    47326, # Pfalzen
    47327, # Vintl
    47333, # Terenten

    47277, # Villnöß
    47292, # Klausen
    47298, # Feldthurns
    47287, # Villanders
    47266, # Barbian

    47300, # Brixen
    47306, # Lüsen
    47307, # Vahrn
    47314, # Schabs
    47321, # Rodeneck
    47322, # Franzensfeste
    47323, # Mühlbach
    47330, # Freienfeld

    47212, # Karneid
    47164, # Welschnofen
    47145, # Deutschnofen
    47122, # Aldein
    47102, # Truden
    47075, # Altrei
    47089, # Montan
    47080, # Neumarkt
    47045, # Salurn
)

BOUNDARY_REL_XXX = (
    47233, # Ritten
    47282, # Sarntal

    47207, # Bozen
    47187, # Leifers
    47173, # Branzoll
    47139, # Auer
    47119, # Tramin
)

IGNORE = {
      38304, # E66
     934999, # Hike Sentiero Europeo E5, Italia
    1736379, # Traumpfad München-Venedig
    2460773, # Ciclovia del Sole
    2759974, # EuroVelo 7 - Sun Route - part Italy 1
    2770634, # EuroVelo 7 - Sun Route - part Austria
    3968183, # 960X Korridorbus Innsbruck - Lienz
    3970708, # 960X Korridorbus Lienz - Innsbruck
    4587693, # Bus: BELLUNO - AGORDO - ALLEGHE - ARABBA - CORVARA - COLFOSCO
    6504729, # Bicycle: "Munich-Venice
    9218098, # Via Romea
    3312655, # Via Claudia Augusta
    6032965, # Cammino del beato Enrico
   10694060, # E45 (reason: oneways and no forward / backward)
    6980895, # Bus 101 Penia Trento
     113579, # Bus 101 Trento Penia
      66701, # Bus 102 Trento Cavalese
    6970784, # Bus 102 Cavalese Trento
    3118896, # Sentiero Botanico sul dossone di Cembra (missing segment)
    4222607, # mtb trudner horn (unofficial and a mess)
     949981, # B100 Drautal Straße

    1753217, # Strada Statale 51 di Alemagna (Tratto ANAS)
    1405697, # Strada Statale 52 Carnica
    1754080, # Strada Provinciale 49 di Misurina
     186221, # 03 Südalpenweg
   10102927, # R1 Drauradweg
    9741603, # Hike Herz-Ass Villgratental
    7392620, # Cortina 108A
    1116692, # Cortina 149
    8490449, # Cortina 155
    8483592, # Cortina 159
    3107761, # ÖAV
    1116678, # ÖAV 471
   12104164, # ÖAV Bonner Höhenweg
    3107942, # ÖAV Heimatsteig
    3107762, # ÖAV 403 Karnischer Höhenweg
    1163255, # ÖAV 403 Karnischer Höhenweg

    7397080, # N01 Ferrata Masare etc.
    7392618, # "Silvano De Romedi"






}
"""Routes we don't want checked, eg. monster routes that go far outside our
area of interest."""

CHUNKS = {
     959876 : 2, # LS64 Kastelruth - St. Ulrich
    1657836 : 2, # AV3 (incomplete mapping)
}
"""Expected no. of chunks for routes that for some reason have more than one
chunk."""

CHECKED_TYPES = ('foot', 'hiking', 'worship', 'bicycle', 'mtb', 'piste', 'ski', 'bus', 'road')
""" Route types we check. """

def way_is_way (way):
    # only consider these kinds of ways

    wtags = way['tag']
    return wtags and ('highway'    in wtags or
                      'railway'    in wtags or
                      'aerialway'  in wtags or
                      'piste:type' in wtags)


def way_is_area (way):
    # check if the way should be treated as area
    # in an area all points are valid entry and exit points
    wtags  = way['tag']
    wnodes = way['nd']

    area       = wtags.get ('area', '') == 'yes'
    roundabout = wtags.get ('junction', '') in ('roundabout', 'circular')
    closed     = wnodes[0] == wnodes[-1]
    return closed and (area or roundabout)


def format_route (relation):
    rtags  = relation['tag']
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
    q   = "[out:json][timeout:25];\n\n%s" % q

    r = requests.post (url, data = {'data' : q})
    r.raise_for_status ()

    return r.json ().get ('elements', [])



def relations_in_areas (area_ids, types = CHECKED_TYPES):
    areas = ''.join ('area(%d);' % (3600000000 + id_) for id_ in area_ids)
    types = '|'.join (types)

    q = """
    ({areas})->.location;
    (
        relation["route"~"{types}"](area.location);
    );
    out ids tags bb;
    """.format (areas = areas, types = types)

    return query (q)

def relations_in_bbox (bbox, types = CHECKED_TYPES):
    bbox  = ', '.join ([str (b) for b in bbox])
    types = '|'.join (types)

    q = """
    (
        relation["route"~"{types}"]({bbox});
    );
    out ids tags bb;
    """.format (bbox = bbox, types = types)

    return query (q)


def osm_relation_as_nodeset (rfull):
    """ Return all nodes in route in random order. """

    relation = rfull[-1]['data']
    return [Point (n['data']['lon'], n['data']['lat']) for n in rfull if n['type'] == 'node']


def osm_relation_as_multilinestring (rfull):

    relation = rfull[-1]['data']

    nodes_dict = dict ([(n['data']['id'], n['data']) for n in rfull if n['type'] == 'node'])
    ways_dict  = dict ([(w['data']['id'], w['data']) for w in rfull if w['type'] == 'way'])

    ways = [ m['ref'] for m in relation['member'] if m['type'] == 'way' ]

    lines = []
    for way in ways:
        nodes = ways_dict[way]['nd']
        lines.append (LineString ([ (nodes_dict[n]['lon'], nodes_dict[n]['lat']) for n in nodes ]))

    mls = shapely.ops.linemerge (lines)
    if mls.type == 'LineString':
        return MultiLineString ([mls])
    return mls


def areas_as_polygon (area_ids):
    polys = []
    for area_id in area_ids:
        # print ("resolving area %d" % area_id)
        rfull = api.RelationFull (area_id)
        relation = rfull[-1]['data']

        nodes_dict = dict ([(n['data']['id'], n['data']) for n in rfull if n['type'] == 'node'])
        ways_dict  = dict ([(w['data']['id'], w['data']) for w in rfull if w['type'] == 'way'])

        ways = [ m['ref'] for m in relation['member'] if m['type'] == 'way' and m['role'] == 'outer' ]
        lines = []
        for way in ways:
            nodes = ways_dict[way]['nd']
            lines.append (LineString ([ (nodes_dict[n]['lon'], nodes_dict[n]['lat']) for n in nodes ]))

        polys += list (shapely.ops.polygonize (lines))

    return shapely.ops.unary_union (polys)


def relations_in_boundary (boundary, types = CHECKED_TYPES):
    rows = conn.execute (sqlalchemy.text ("""
    SELECT r.id AS rel_id, r.tags as tags
    FROM snapshot.relations r
      JOIN snapshot.relation_members mn ON r.id = mn.relation_id
        JOIN snapshot.ways w ON w.id = mn.member_id
    WHERE ST_Intersects (:boundary, w.linestring)
      AND r.tags->'route' IN :checked
      AND COALESCE (r.tags->'name', '') !~ 'Flixbus'
    GROUP BY r.tags->'route', natsort (r.tags->'ref'), r.tags->'name', r.id
    ORDER BY r.tags->'route', natsort (r.tags->'ref'), r.tags->'name', r.id
    """), { 'boundary' : boundary, 'checked' : types })

    Relations = collections.namedtuple ('Relations', 'rel_id, tags')
    return [ Relations._make (r) for r in rows ]


params = {
    'host'     : os.environ.get ('PGHOST')     or 'localhost',
    'port'     : os.environ.get ('PGPORT')     or '5432',
    'database' : os.environ.get ('PGDATABASE') or 'osm',
    'user'     : os.environ.get ('PGUSER')     or 'osm',
}

engine = sqlalchemy.create_engine (
    "postgresql+psycopg2://{user}@{host}:{port}/{database}".format (**params)
)

conn = engine.connect ()

api = osmapi.OsmApi (passwordfile = Path ("~/.osmpass").expanduser ())

#result = relations_in_areas ([47242, 47244])
#for r in result:
#    print (r['id'])
#    tags = r['tags']
#    print ("Name: %s" % tags.get ("name", tags.get ("ref", "n/a")))
#    bounds = r['bounds']
#    print (bounds)


sql = """WITH boundaries AS (
SELECT ST_Polygonize (w.linestring) AS boundary
FROM snapshot.relations r
    JOIN snapshot.relation_members mn ON mn.relation_id = r.id
    JOIN snapshot.ways w              ON w.id = mn.member_id
WHERE r.id IN :boundaries
GROUP BY r.id
)

SELECT ST_Union (boundary) AS boundary FROM boundaries
"""

boundary_south_tyrol = areas_as_polygon (BOUNDARY_ST)
boundary             = areas_as_polygon (BOUNDARY_REL)

#rows = conn.execute (sqlalchemy.text (sql), { 'boundaries' : BOUNDARY_REL })
#boundary = rows.fetchone ()[0]

#rows = conn.execute (sqlalchemy.text (sql), { 'boundaries' : BOUNDARY_ST })
#boundary_south_tyrol = rows.fetchone ()[0]
