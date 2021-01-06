#!/usr/bin/python3

import collections
import itertools
import operator
import json
import re

import osmapi
import sqlalchemy

import connect
import hausdorff as hd


def check_osmc_symbol (rtags):
    sym = rtags.get ('osmc:symbol')
    ref = rtags.get ('ref')
    errors = []

    if sym:
        m = re.match (r'^(.*?):red:white_', sym)
        if m and m.group (1) != 'red':
            errors.append ('  Bogus osmc:symbol {sym}'.format (sym = sym))

        if ref:
            rx = ':%s:' % ref

            m = re.match (r'([0-9]{1,2}[ABC]?)$', ref)
            if m:
                rx = '^red:red:white_bar:%s:black$' % m.group (1)

            m = re.match (r'E([0-9]{3}[ABC]?)$', ref)
            if m:
                rx = '^red:red:white_stripe:%s:black$' % m.group (1)

            m = re.match (r'AV([0-9])$', ref)
            if m:
                rx = '^red::blue_triangle_line:%s:blue$' % m.group (1)

            m = re.match (r'VA-([A-Z][0-9]+)$', ref)
            if m:
                rx = '^red::gray_triangle:V:blue$'

            if not re.search (rx, sym):
                errors.append ('  Ref {ref} and osmc:symbol {sym} mismatch.'.format (ref = ref, sym = sym))
                # errors.append ('  rx = {rx}'.format (rx = rx))

    return errors


def check_stop_tags (stops):
    errors = []

    for stop in stops:
        stags = stop['tag']

        pt = stags.get ('public_transport')
        if pt != 'stop_position':
            errors.append ('  Stop {id} is missing tags.'.format (id = stop['id']))

    return errors


def check_network (rtags):
    route = rtags['route']
    network = rtags.get ('network')
    errors = []

    rx = None
    if route in ('foot', 'hiking'):
        rx = r'^[lrni]wn$'
    if route == 'bicycle':
        rx = r'^[lrni]cn$'

    if rx:
        if network is None:
            errors.append ('  No network in route')
        else:
            m = re.search (rx, network)
            if not m:
                errors.append ('  Bogus network {nw} in route'.format (nw = network))

    return errors


def ways_ok (rfull, ways, stops = [], direction = ''):
    relation = rfull[-1]['data']

    rtags  = relation['tag']
    route  = rtags['route']
    rel_id = relation['id']
    expected_chunks = connect.CHUNKS.get (rel_id, 1)

    chunks = []
    chunk = []
    error_msgs = []

    # filter non-ways
    ways = [ w for w in ways if connect.way_is_way (w) ]

    # the node(s) last reached
    last_nodes = set ()

    # to know the first way's orientation we have to peek at the second way
    if len (ways) > 1:
        w0nodes = ways[0]['nd']
        w1nodes = ways[1]['nd']
        if connect.way_is_area (ways[0]):
            # route can start with any node of the first way
            last_nodes = set ( w0nodes )
        elif w0nodes[-1] in w1nodes:
            # the first way is forward, route starts with the first node of the first way
            last_nodes = { w0nodes[0] }
        elif w0nodes[0] in w1nodes:
            # the first way is backward, route starts with the last node of the first way
            last_nodes = { w0nodes[-1] }

    next_stop = stops.pop (0) if stops else None

    for way in ways:
        wtags   = way['tag']
        wnodes  = way['nd']
        reverse = None # do we use the way in reverse direction?

        roundabout = wtags.get ('junction', '') in ('roundabout', 'circular')
        is_area = connect.way_is_area (way)

        oneway = wtags.get ('oneway', 'no')
        if route == 'bus':
            oneway = wtags.get ('oneway:psv', wtags.get ('oneway:bus', oneway))
        if route in ('bicycle', 'mtb'):
            oneway = wtags.get ('oneway:bicycle', oneway)
        if route == 'piste':
            oneway = wtags.get ('piste:oneway', oneway)
        oneway = (oneway == 'yes')
        oneway = oneway or roundabout   # roundabout implies oneway for vehicles
        if 'aerialway' in wtags:
            oneway = True # mtb tours
        if route in ('foot', 'hiking', 'worship'):
            oneway = False

        if is_area:
            # route can enter at any node
            nodes = set (wnodes)
        else:
            if oneway:
                # route can enter at first node only
                nodes = { wnodes[0] }
            else:
                # route can enter at both endnodes
                nodes = { wnodes[0], wnodes[-1] }

        if len (last_nodes) > 0 and len (last_nodes & nodes) == 0:
            last_nodes = set ()
            chunks.append (chunk)
            chunk = []
            if oneway:
                error_msgs.append ('  Oneway violation in way "%s" (%d)' %
                                   (wtags.get ('name', 'unnamed'), way['id']))
            else:
                if expected_chunks == 1:
                    error_msgs.append ('  Route disconnected at way "%s" (%d)' %
                                       (wtags.get ('name', 'unnamed'), way['id']))

        if is_area:
            # route can exit by any node
            last_nodes = nodes
            reverse = False
        else:
            if oneway:
                # route can exit by last node only
                last_nodes = { wnodes[-1] }
                reverse = False
            else:
                # route can exit by both endnodes
                last_nodes = nodes - last_nodes
                # which direction did we take?
                # this is used to check bus stops
                reverse = wnodes[0] in last_nodes

        chunk.extend (reversed (wnodes) if reverse else wnodes)

        # check stops in way
        if next_stop:
            for node_id in (reversed (wnodes) if reverse else wnodes):
                if node_id == next_stop['id']:
                    stop_tags = next_stop['tag']
                    # next stop reached
                    name = stop_tags.get ('name', 'unnamed')
                    # print ('  Stop reached "%s" %s road' % (name, 'in reversed' if reverse else ''))
                    sdirection = stop_tags.get ('direction', 'both')
                    if (sdirection == 'both') or (reverse is None) or (reverse == (sdirection == 'backward')):
                        # stop reached, on to the next one
                        next_stop = stops.pop (0) if stops else None
                        if next_stop is None:
                            break

    if stops:
        stop_id = stops[0]['id']
        stags = stops[0]['tag']
        name = stags.get ('name', '<noname>')
        error_msgs.append ('  Stop "{name}" ({stop_id}) not reached'.format (name = name, stop_id = stop_id))

    chunks.append (chunk)
    if len (chunks) != expected_chunks:
        error_msgs.append (
            '  Route {direction} in DISORDER ({fc}/{ec})'.format (
                direction = direction,
                fc = len (chunks),
                ec = expected_chunks,
            )
        )

    return error_msgs, chunks


def route_ok (rfull):
    relation = rfull[-1]['data']
    rtags    = relation['tag']
    route    = rtags['route']
    members  = relation['member']

    errors = []

    errors += check_osmc_symbol (rtags)
    errors += check_network (rtags)

    ways_dict = dict ([(w['data']['id'], w['data']) for w in rfull if w['type'] == 'way'])

    oneway = rtags.get ('oneway', 'yes') == 'yes'
    forward_backward = any ([w['role'] in ('forward', 'backward') for w in members])

    if (route in ('road', 'bicycle')) or (route == 'mtb' and forward_backward):
        ways = [ ways_dict[w['ref']] for w in members if w['type'] == 'way' and w['role'] in ('', 'forward') ]
        err, chunks = ways_ok (rfull, ways, [], 'forward')
        errors += err

        ways = [ ways_dict[w['ref']] for w in members if w['type'] == 'way' and w['role'] in ('', 'backward') ]
        err, chunks = ways_ok (rfull, reversed (ways), [], 'backward')
        errors += err

    else:
        ways = [ ways_dict[w['ref']] for w in members if w['type'] == 'way' and w['role'] in ('', 'start')]
        if route == 'bus':
            nodes_dict = dict ([(n['data']['id'], n['data']) for n in rfull if n['type'] == 'node'])
            stops = [ nodes_dict[n['ref']] for n in members
                      if n['type'] == 'node' and n['role'] in ('stop', 'stop_exit_only', 'stop_entry_only') ]
            err, chunks = ways_ok (rfull, ways, stops)
            errors += err
            errors += check_stop_tags (stops)
        else:
            err, chunks = ways_ok (rfull, ways, [])
            errors += err

    if (route in ('foot', 'hiking', 'worship')
        and not re.match (r'AV|E|SI|VA', rtags.get ('ref', ''))
        and not 'via_ferrata_scale' in rtags
        and not rtags.get ('hiking') == 'via_ferrata'):

        errors += hd.check_osm_covered (rfull)

    if errors:
        errors.insert (0, '{r}'.format (r = connect.format_route (relation)))

    return errors

#
# get all route relations that intersect our area of interest
#

interesting_relations = connect.relations_in_areas (connect.BOUNDARY_REL, ('foot', 'hiking', 'worship'))
checked_relations = 0
faulty_relations = set ()

hd.init (
    interesting_relations,
    (
        'data/hiking-trails-east.geojson',
        'data/hiking-trails-center.geojson'
    )
)

for rel in interesting_relations:
    errors = []
    rel_id = rel['id']
    if rel_id in connect.IGNORE:
        continue

    try:
        rfull = connect.api.RelationFull (rel_id)
        relation = rfull[-1]['data']
        rtags = relation['tag']

        route = rtags['route']
        if route not in connect.CHECKED_TYPES:
            continue

        if 'fixme' in rtags:
            continue

        # print (json.dumps (rfull, indent=4, sort_keys=True, default=lambda o: '<not serializable>'))
        errors += route_ok (rfull)
        checked_relations += 1

        if errors:
            print ('\n'.join (errors))
            faulty_relations.add (rel_id)

    except osmapi.ElementDeletedApiError:
        # route was deleted, nothing to report
        pass

    except osmapi.MaximumRetryLimitReachedError as e:
        print (e)


# Check all routes in geokatalog

for gk_id in hd.gk_routes.keys ():
    errors = []
    errors += hd.check_geokatalog_covered (gk_id)
    if errors:
        print ('\n'.join (errors))


print ('Checked relations: %d' % checked_relations)
print ('Faulty relations:  %d' % len (faulty_relations))
print ('Faulty relation ids: ' + ' '.join ([str (rel) for rel in sorted (faulty_relations)]))
