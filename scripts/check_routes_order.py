#!/usr/bin/python3

"""An OSM route checker.

Checks:

- if routes are connected,
- forward / backward in road relations,
- oneways in cycle and bus routes,
- and correct order of stops in bus routes.

Also can compare OSM hiking routes against their counterpart in `geokatalog.provinz.bz.it`.

"""

import argparse
import collections
import itertools
import logging
from logging import ERROR, WARN, INFO, DEBUG
import operator
import json
import re
import sys

import connect
import hausdorff as hd


def check_osmc_symbol (rtags):
    sym = rtags.get ('osmc:symbol')
    ref = rtags.get ('ref')
    errors = []

    if sym:
        m = re.match (r'^(.*?):red:white_', sym)
        if m and m.group (1) != 'red':
            errors.append ((ERROR, '  Bogus osmc:symbol {sym}'.format (sym = sym)))

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
                errors.append ((ERROR, '  Ref {ref} and osmc:symbol {sym} mismatch.'.format (ref = ref, sym = sym)))
                # errors.append ('  rx = {rx}'.format (rx = rx))

    return errors


def check_stop_tags (stops):
    errors = []

    for stop in stops:
        stags = stop['tags']

        pt = stags.get ('public_transport')
        if pt != 'stop_position':
            errors.append ((ERROR, '  Stop {id} is missing tags.'.format (id = stop['id'])))

    return errors


def check_network (rtags):
    route = rtags['route']
    network = rtags.get ('network')
    errors = []

    rx = None
    if route in connect.HIKING_TYPES:
        rx = r'^[lrni]wn$'
    if route == 'bicycle':
        rx = r'^[lrni]cn$'

    if rx:
        if network is None:
            errors.append ((ERROR, '  No network in route'))
        else:
            m = re.search (rx, network)
            if not m:
                errors.append ((ERROR, '  Bogus network {nw} in route'.format (nw = network)))

    return errors


def ways_ok (rfull, ways, stops = [], direction = ''):
    relation = rfull[-1]

    rtags  = relation['tags']
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
        w0nodes = ways[0]['nodes']
        w1nodes = ways[1]['nodes']
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
        wtags   = way['tags']
        wnodes  = way['nodes']
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
        if route in connect.HIKING_TYPES:
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
                error_msgs.append ((ERROR, '  Oneway violation in way "%s" (%d)' %
                                   (wtags.get ('name', 'unnamed'), way['id'])))
            else:
                if expected_chunks == 1:
                    error_msgs.append ((ERROR, '  Route disconnected at way "%s" (%d)' %
                                       (wtags.get ('name', 'unnamed'), way['id'])))

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
                    stop_tags = next_stop['tags']
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
        stags = stops[0]['tags']
        name = stags.get ('name', '<noname>')
        error_msgs.append ((ERROR, '  Stop "{name}" ({stop_id}) not reached'.format (name = name, stop_id = stop_id)))

    chunks.append (chunk)
    if len (chunks) != expected_chunks:
        error_msgs.append ((ERROR,
            '  Route {direction} in DISORDER ({fc}/{ec})'.format (
                direction = direction,
                fc = len (chunks),
                ec = expected_chunks,
            )
        ))

    return error_msgs, chunks


def route_ok (rfull):
    relation = rfull[-1]
    rtags    = relation['tags']
    route    = rtags['route']
    members  = relation['members']

    errors = []

    errors += check_osmc_symbol (rtags)
    errors += check_network (rtags)

    ways_dict = dict ([(w['id'], w) for w in rfull if w['type'] == 'way'])

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
            nodes_dict = dict ([(n['id'], n) for n in rfull if n['type'] == 'node'])
            stops = [ nodes_dict[n['ref']] for n in members
                      if n['type'] == 'node' and n['role'] in ('stop', 'stop_exit_only', 'stop_entry_only') ]
            err, chunks = ways_ok (rfull, ways, stops)
            errors += err
            errors += check_stop_tags (stops)
        else:
            err, chunks = ways_ok (rfull, ways, [])
            errors += err

    return errors


class Formatter (logging.Formatter):
    """ Logging formatter. Allows colorful formatting of log lines. """

    COLORS = {
        logging.CRITICAL : ('\x1B[38;2;255;0;0m',  '\x1B[0m'),
        logging.ERROR    : ('\x1B[38;2;255;0;0m',  '\x1B[0m'),
        logging.WARN     : ('\x1B[38;2;255;64;0m', '\x1B[0m'),
        logging.INFO     : ('', ''),
        logging.DEBUG    : ('', ''),
    }

    def format (self, record):
        record.esc0, record.esc1 = self.COLORS[record.levelno]
        return super ().format (record)


def init_logging (args, *handlers):
    """ Init the logging stuff. """

    LOG_LEVELS = {
        0: logging.ERROR,     #
        1: logging.WARN,      # -v
        2: logging.INFO,      # -vv
        3: logging.DEBUG      # -vvv
    }
    args.log_level = LOG_LEVELS.get (args.verbose, logging.DEBUG)

    root = logging.getLogger ()
    root.setLevel (args.log_level)

    formatter = Formatter (
        fmt = '{esc0}{relativeCreated:6.0f} - {levelname:7} - {message}{esc1}',
        style='{'
    )

    if not handlers:
        handlers = [logging.StreamHandler ()] # stderr

    for handler in handlers:
        handler.setFormatter (formatter)
        root.addHandler (handler)


class MyArgumentParser (argparse.ArgumentParser):
    def convert_arg_line_to_args (self, line):
        # allow comments in @file
        bc = line.partition ('#')[0]
        if bc:
            return [bc.strip ()]
        return []


def build_parser ():
    parser = MyArgumentParser (description = __doc__, fromfile_prefix_chars = '@')

    parser.add_argument ('-v', '--verbose', action='count',
                         help='increase output verbosity', default=0)
    parser.add_argument ('-a', '--areas', nargs='+',
                         metavar='OSM_RELID',
                         help='OSM id of area')
    parser.add_argument ('-r', '--routes', nargs='*',
                         metavar='ROUTE',
                         help='routes to analyze (%s)' % ', '.join (connect.CHECKED_TYPES),
                         choices = connect.CHECKED_TYPES,
                         default = connect.CHECKED_TYPES)
    parser.add_argument ('-g', '--geokatalog', nargs='*',
                         metavar='path/to/geokatalog.geojson',
                         help="load geokatalog geojson file")
    parser.add_argument ('--osm-ignore', nargs='*', type=int, dest='osm_ignore',
                         metavar='OSM_RELID',
                         default = [],
                         help="ignore these OSM routes")
    parser.add_argument ('--osm-warn', nargs='*', type=int, dest='osm_warn',
                         metavar='OSM_RELID',
                         default = [],
                         help="convert errors into warnings for these OSM routes")
    parser.add_argument ('--gk-warn', nargs='*', dest='gk_warn',
                         metavar='GEOKATALOG_ID',
                         default = [],
                         help="convert errors into warnings for these geokatalog routes")
    parser.add_argument ('--write-areas-bbox',
                         metavar='FILENAME',
                         help="output boundary of selected areas in WKT format")
    return parser


if __name__ == '__main__':

    # just pin this on sys, makes it easy to pass around and is global anyway
    sys.args = build_parser ().parse_args ()

    init_logging (
        sys.args,
        logging.StreamHandler (), # stderr
        logging.FileHandler ('check_routes.log')
    )

    log = logging.getLogger ().log

    #
    # get all route relations that intersect our area of interest
    #

    connect.init ()

    # maybe just output areas

    if sys.args.write_areas_bbox:
        with open (sys.args.write_areas_bbox, 'w') as fp:
            fp.write ("{:.6f} {:.6f} {:.6f} {:.6f}".format (*connect.boundary.bounds))
        sys.exit ()

    log (INFO, 'querying overpass for route relations in areas ...')
    osm_relations = connect.relations_in_areas (sys.args.areas, sys.args.routes)
    log (INFO, 'got %d route relations from overpass' % len (osm_relations))

    hd.init (osm_relations, sys.args.geokatalog)

    log (INFO, 'start checking OSM routes')

    checked_relations = 0
    faulty_relations = set ()

    def osm_route_key (i):
        rtags = i[1]['rfull'][-1]['tags']
        return connect.natural_sort (rtags.get ('ref', rtags.get ('name', '')))

    for rel_id, data in sorted (hd.osm_routes.items (), key = osm_route_key):
        log (DEBUG, 'checking OSM route %s' % rel_id)

        errors = []
        if rel_id in sys.args.osm_ignore:
            continue

        try:
            rfull = data['rfull']
            relation = rfull[-1]
            rtags = relation['tags']
            context = connect.format_route (relation)

            route = rtags['route']
            if route not in connect.CHECKED_TYPES:
                continue

            fixme = rtags.get ('fixme')
            if fixme:
                errors.append ((ERROR, '%s - fixme: %s' % (context, fixme)))

            errors += route_ok (rfull)
            checked_relations += 1

            # check against geokatalog

            if (sys.args.geokatalog
                and route in connect.HIKING_TYPES
                and not re.match (r'AV|E|SI|VA', rtags.get ('ref', ''))
                and not 'via_ferrata_scale' in rtags
                and not rtags.get ('hiking') == 'via_ferrata'):

                hd.check_osm_covered (rel_id, errors)

            if errors:
                level = WARN if rel_id in sys.args.osm_warn else ERROR
                for level, error in errors:
                    log (level, "%s - %s" % (context, error))

        except Exception as e:
            print (e)

    log (INFO, 'Checked relations: %d' % checked_relations)
    log (INFO, 'Faulty relations:  %d' % len (faulty_relations))
    log (INFO, 'Faulty relation ids: ' + ' '.join ([str (rel) for rel in sorted (faulty_relations)]))

    # Check all routes in geokatalog

    log (INFO, 'start checking GK routes')

    def gk_route_key (i):
        props = i[1]['properties']
        return connect.natural_sort (props.get ('WEGENR', props.get ('ROUTENNAME', '')))

    for gk_id, gk_item in sorted (hd.gk_routes.items (), key = gk_route_key):
        errors = []
        hd.check_geokatalog_covered (gk_id, errors)
        if errors:
            gk_props = gk_item['properties']
            gk_ref   = gk_props.get ('WEGENR',     '')
            gk_name  = gk_props.get ('ROUTENNAME', '')

            level = WARN if (gk_name in sys.args.gk_warn or gk_ref in sys.args.gk_warn) else ERROR
            context = connect.format_gk_route (gk_props)
            for level, error in errors:
                log (level, "%s - %s" % (context, error))

    log (INFO, 'Done')
