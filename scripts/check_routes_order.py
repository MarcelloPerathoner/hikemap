#!/usr/bin/python3

import collections
import itertools
import operator
import json

import osmapi
import sqlalchemy

import connect

IGNORE = {
    1736379, # Traumpfad München-Venedig
    2460773, # Ciclovia del Sole
    2759974, # EuroVelo 7 - Sun Route - part Italy 1
    4587693, # Bus: BELLUNO - AGORDO - ALLEGHE - ARABBA - CORVARA - COLFOSCO
   10694060, # E45 (reason: oneways and no forward / backward)
}
"""Routes we don't want checked, eg. monster routes that go far outside our
area of interest."""

CHUNKS = {
      959876 : 2, # LS64 Kastelruth - St. Ulrich
      # 960769 : 2, # A22 Brennerautobahn (reason: gap in Database extract)
}
"""Expected no. of chunks for routes that for some reason have more than one
chunk."""

def ways_ok (ways, route):
    chunks = 1
    last_nodes = set ()

    # check_oneway (tags) checks if this is a oneway road
    check_oneway = lambda tags: False
    if route == 'road':
        check_oneway = lambda tags: tags.get ('oneway', tags.get ('roundabout', 'no')) == 'yes'
    if route == 'bus':
        check_oneway = lambda tags: tags.get ('oneway:psv', tags.get ('oneway', tags.get ('roundabout', 'no'))) == 'yes'
    if route in ('bicycle', 'mtb'):
        check_oneway = lambda tags: tags.get ('oneway:bicycle', tags.get ('oneway', tags.get ('roundabout', 'no'))) == 'yes'

    for n, way in enumerate (ways):
        oneway = check_oneway (way.tags)

        if oneway:
            nodes = { way.nodes[0] }
        else:
            nodes = { way.nodes[0], way.nodes[-1] }

        if len (last_nodes) > 0 and len (last_nodes & nodes) == 0:
            last_nodes = set ()
            chunks += 1

        if oneway:
            last_nodes = { way.nodes[-1] }
            way.tags['reversed'] = False
        else:
            last_nodes = nodes - last_nodes
            # make a note how the way is oriented,
            # this is used to check bus stops
            way.tags['reversed'] = way.nodes[0] in last_nodes

    return chunks

def stops_ok (ways, relation_id):
    errors = 0

    res = connect.conn.execute (sqlalchemy.text ("""
    SELECT n.id, n.tags
    FROM snapshot.relation_members mn
      JOIN snapshot.nodes n ON mn.member_id = n.id
    WHERE mn.member_role = 'stop'
      AND mn.relation_id = :relation_id
    ORDER BY mn.sequence_id
    """), { 'relation_id' : relation_id })

    Stops = collections.namedtuple ('Stops', 'node_id, tags')
    stops = [ Stops._make (r) for r in res ]
    stops_iter = iter (stops)
    try:
        next_stop = next (stops_iter)
        for way in ways:
            reverse = way.tags['reversed']
            for node_id in reversed (way.nodes) if reverse else way.nodes:
                if node_id == next_stop.node_id:
                    direction = 'backward' if reverse else 'forward'
                    if next_stop.tags.get ('direction', direction) != direction:
                        print ('  Stop "%s" in route %d has wrong direction' %
                               (next_stop.tags.get ('name', 'unnnamed'), rel_id))
                        errors += 1
                    #if next_stop.tags.get ('highway') != 'bus_stop':
                    #    print ('  Stop "%s" in route %d has no highway=bus_stop' %
                    #           (next_stop.tags.get ('name', 'unnnamed'), rel_id))
                    # stop reached, on to the next one
                    next_stop = next (stops_iter)

    except StopIteration:
        return errors == 0 # all stops reached

    print ('  Stop "%s" in route %d not reached' % (next_stop.tags.get ('name', 'unnnamed'), rel_id))
    return False


def check_route (rel, g, report = False):
    rel_id = rel['rel_id']
    route  = rel['route']

    expected_chunks = CHUNKS.get (rel_id, 1)
    ok = False

    if route == 'road':
        forward  = [ w for w in g if w.role in ('', 'forward') ]
        backward = [ w for w in g if w.role in ('', 'backward') ]
        found_chunks = ways_ok (forward, route)
        forward_ok   = found_chunks == expected_chunks
        if report and not forward_ok:
            print ('Road {route} route {ref} ({rel_id}) "{name}" forward in DISORDER ({fc}/{ec})'.format (
                fc = found_chunks, ec = expected_chunks, **rel))
        found_chunks = ways_ok (reversed (backward), route)
        backward_ok = found_chunks == expected_chunks
        if report and not backward_ok:
            print ('Road {route} route {ref} ({rel_id}) "{name}" backward in DISORDER ({fc}/{ec})'.format (
                fc = found_chunks, ec = expected_chunks, **rel))
        ok = forward_ok and backward_ok
    elif route == 'bus':
        ways = [ w for w in g if w.role == '' ]
        found_chunks = ways_ok (ways, route)
        ok = found_chunks == expected_chunks and stops_ok (ways, rel_id)
        if report and not ok:
            print ('Bus {route} route {ref} ({rel_id}) "{name}" in DISORDER ({fc}/{ec})'.format (
                fc = found_chunks, ec = expected_chunks, **rel))
    else:
        ways = [ w for w in g if w.role == '' ]
        found_chunks = ways_ok (ways, route)
        ok = found_chunks == expected_chunks
        if report and not ok:
            print ('{route} route {ref} ({rel_id}) "{name}" in DISORDER ({fc}/{ec})'.format (
                fc = found_chunks, ec = expected_chunks, **rel))

    return ok


rows = connect.conn.execute (sqlalchemy.text ("""
WITH routes_in_boundary AS (
SELECT mn.relation_id
FROM snapshot.relation_members mn
    JOIN snapshot.ways w ON w.id = mn.member_id
WHERE ST_Intersects (:boundary, w.linestring)
GROUP BY relation_id
)

SELECT r.id             AS rel_id,
       r.tags->'route'  AS route,
       r.tags->'ref'    AS "ref",
       r.tags->'name'   AS "name",
       w.id             AS way_id,
       w.nodes          AS nodes,
       mn.member_role   AS role,
       w.tags           AS tags
FROM snapshot.relations r
   JOIN routes_in_boundary b ON r.id = b.relation_id
   JOIN snapshot.relation_members mn ON r.id = mn.relation_id
       JOIN snapshot.ways w ON w.id = mn.member_id
WHERE r.tags->'route' IN ('hiking', 'bicycle', 'mtb', 'piste', 'bus', 'road')
  AND COALESCE (r.tags->'name', '') !~ 'Flixbus'
ORDER BY r.tags->'route', natsort (r.tags->'ref'), r.tags->'name', r.id, mn.sequence_id
"""), { 'boundary' : connect.boundary })


print ("Checking %d ways" % rows.rowcount)

Ways = collections.namedtuple ('Ways', 'rel_id, route, ref, name, way_id, nodes, role, tags')
rows = [ Ways._make (r) for r in rows ]

APIWays = collections.namedtuple ('APIWays', 'way_id, nodes, role, tags')

checked_relations = 0
faulty_relations = set ()

for rel_id, group in itertools.groupby (rows, operator.attrgetter ('rel_id')):
    if rel_id in IGNORE:
        continue

    checked_relations += 1

    g = list (group)
    ok = check_route (g[0]._asdict (), g)
    if ok:
        continue

    # there is a problem in the nightly snapshot, get the current data for the
    # faulty relation from the api and check again

    try:
        rfull = connect.api.RelationFull (rel_id)
    except osmapi.ElementDeletedApiError:
        # route was deleted, nothing to report
        break

    # print (json.dumps (rfull, indent=4, sort_keys=True, default=lambda o: '<not serializable>'))

    # dict way_id : data
    ways = dict ( [[row['data']['id'], row['data']] for row in rfull if row['type'] == 'way'] )

    # dict rel_id : data
    rels = dict ( [[row['data']['id'], row['data']] for row in rfull if row['type'] == 'relation'] )

    members = []
    for member in rels[rel_id]['member']:
        if member['type'] == 'way':
            way_id = member['ref']
            way = ways[way_id]
            members.append (APIWays._make ( (
                way_id,
                way['nd'],
                member['role'],
                way['tag'],
            )))

    rel = rels[rel_id]
    tags = rel['tag']
    ok = check_route ({
        'rel_id' : rel_id,
        'route'  : tags.get ('route'),
        'ref'    : tags.get ('ref'),
        'name'   : tags.get ('name'),
    }, members, report = True)

    if not ok:
        faulty_relations.add (rel_id)


print ('Checked relations: %d' % checked_relations)
print ('Faulty relations:  %d' % len (faulty_relations))
print ('Faulty relation ids: ' + ' '.join ([str (rel) for rel in sorted (faulty_relations)]))
