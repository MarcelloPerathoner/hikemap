#!/usr/bin/python3

""" Check ways in OSM for the presence of hiking related refs. """

import argparse
import re

from osgeo import ogr, osr, gdal
import osmapi
import sqlalchemy

import connect

MY_UID = 8199540

RE_NAME_SPLIT = re.compile (' - ')
RE_REF = re.compile ('^(SI|Fer|PU|P|(E|AV)?\d+[A-Z]?)$')
RE_BAD_NAMES = re.compile (r'\(SI|Sentiero Italia|Alta via|Dolomiten-Höhenweg|Traumpfad')

def split_ref (ref):
    return set (ref.split (';') if ref else [])

def split_name (name):
    """ Split a name like '42 - 69 - Roda de Valun - Valun Rundweg' into refs and name.
    refs = {'42', '69'}
    name = {'Roda de Valun - Valun Rundweg'}
    """
    if not name:
        return set (), set ()
    parts = [r.strip () for r in RE_NAME_SPLIT.split (name) if r and not RE_BAD_NAMES.search (r)]
    refs  = set ([ r for r in parts if     RE_REF.match (r) ])
    names = set ([ r for r in parts if not RE_REF.match (r) ])
    return refs, names

def join_ref (refs):
    return ';'.join (sorted (refs))

def join_name (refs, names):
    names = names - refs
    parts = sorted (refs) + sorted (names)
    return ' - '.join (parts)

def set_tag (way, name, value):
    if value:
        way['tag'][name] = value
    else:
        del way['tag'][name]

def build_parser ():
    """ Build the commandline parser. """

    parser = argparse.ArgumentParser (description = __doc__)

    parser.add_argument (
        '-v', '--verbose', dest='verbose', action='count',
        help='increase output verbosity', default=0
    )
    parser.add_argument (
        '-l', '--live', dest='get_live_data', action='store_true',
        help='get live data from OSM database',
    )
    parser.add_argument (
        '-e', '--edit', action='store_true',
        help='edit the OSM database',
    )
    parser.add_argument (
        '-u', '--user', dest='my_edits', action='store_true',
        help='only report about my edits',
    )
    parser.add_argument (
        '--min-length', dest="min_length", type=float, default=1000.0,
        help='way must be longer than this to get a ref (in m) (default=1000)',
    )
    parser.add_argument (
        '--batch-size', dest="batch_size", type=int, default=10,
        help='apply OSM edits in changesets of this size (default=10)',
    )
    return parser


if __name__ == "__main__":
    api = connect.api
    cs = None
    changes = 0
    relations = dict ()

    args = build_parser ().parse_args ()

    args.get_live_data |= args.edit # only edit live data

    # get all paths and tracks that are in a hiking route
    rows = connect.conn.execute (sqlalchemy.text ("""
    WITH routes AS (
        WITH RECURSIVE rec_routes (way_id, rel_id, rel_tags) AS (
            -- select all lines in some relation
            SELECT line.osm_id AS way_id, r.id AS rel_id, r.tags AS rel_tags
            FROM planet_osm_line line
              JOIN relations_of r ON r.member_id = line.osm_id
          UNION
            -- add all super relations
            SELECT ar.way_id, r.id AS rel_id, r.tags AS rel_tags
            FROM rec_routes ar
              JOIN relations_of r ON r.member_id = ar.rel_id
        )
    SELECT way_id,
           array_agg (rel_tags->'ref') AS refs,
           array_agg (rel_tags->'name') AS names,
           array_agg (rel_id) AS rel_ids
    FROM rec_routes
    WHERE rel_tags->'route' = 'hiking'
    GROUP BY way_id
    )

    SELECT w.id               AS way_id,
           refs,
           names,
           rel_ids,
           w.tags->'highway'  AS highway,
           w.tags->'ref'      AS "ref",
           w.tags->'name'     AS "name",
           ST_Length (w.linestring::geography) AS length
    FROM snapshot.ways w
      LEFT JOIN routes r ON w.id = r.way_id
    WHERE w.tags->'highway' IN ('track', 'path', 'footway')
          AND ST_Intersects (:boundary, w.linestring)
          -- AND ST_Length (w.linestring::geography) > :min_length
    ORDER BY length DESC
    """), { 'boundary' : connect.boundary, 'min_length' : args.min_length })

    print ("Checking %d ways" % rows.rowcount)

    faulty_ways = set ()

    for row in rows:
        # get (maybe stale) content from local database
        way_id, route_refs, route_names, rel_ids, highway, ref, name, length = row

        my_edit = False
        way = None
        comment = set ()

        #
        # check if the way should have a ref and a name
        #

        refs_in_routes  = set ([r for r in route_refs  if r is not None] if route_refs else [])

        names_in_routes = set ()
        if route_names:
            for route_name in route_names:
                if route_name and not RE_BAD_NAMES.search (route_name):
                    refs_in_name, names_in_name = split_name (name)
                    names_in_routes |= names_in_name
        names_in_routes -= refs_in_routes

        refs_in_ref                 = split_ref (ref)
        refs_in_name, names_in_name = split_name (name)

        # do a quick check of the local database
        if args.get_live_data and (
                (ref == '') or
                (name == '') or
                (refs_in_routes != refs_in_ref) or
                (highway == 'track' and refs_in_name) or
                (highway != 'track' and (refs_in_routes != refs_in_name) or (names_in_routes - names_in_name))):

            # the local database indicates a problem
            # get live data from the api and try again
            refs_in_routes  = set ()
            names_in_routes = set ()
            try:
                way     = api.WayGet (way_id)
                ref     = way['tag'].get ('ref')
                name    = way['tag'].get ('name')
                highway = way['tag'].get ('highway')

                way_rels = api.WayRelations (way_id)
                for way_rel in way_rels:
                    rel_id = way_rel['id']
                    if rel_id not in relations:
                        relations[rel_id] = way_rel # cache relations
                    r = relations[rel_id]
                    rel_ref   = r['tag'].get ('ref')
                    rel_name  = r['tag'].get ('name')
                    rel_route = r['tag'].get ('route')

                    if rel_route == 'hiking':
                        if rel_ref:
                            refs_in_routes.add (rel_ref)
                        if rel_name and not RE_BAD_NAMES.search (rel_name):
                            names_in_routes |= split_name (rel_name)[1]

                        if r['uid'] == MY_UID:
                            my_edit = True

            except (osmapi.XmlResponseInvalidError) as e:
                # way has no relations
                pass

            except (KeyError, osmapi.ElementDeletedApiError) as e:
                print ("%s in rel_id %s" % (e, rel_id))
                continue

            # only edit relations I touched last
            if args.my_edits and not my_edit:
                continue

            # reload from live data
            names_in_routes -= refs_in_routes

            refs_in_ref                 = split_ref (ref)
            refs_in_name, names_in_name = split_name (name)

        row_changed = False

        if ref == '':
            print ("{highway:8} {way_id:10} {length:6.0f} ref is ''".format (
                highway = highway, way_id = way_id, length = length))
            if way:
                set_tag (way, 'ref', None)
                row_changed = True
                comment.add ('remove empty ref')

        if name == '':
            print ("{highway:8} {way_id:10} {length:6.0f} name is ''".format (
                highway = highway, way_id = way_id, length = length))
            if way:
                set_tag (way, 'name', None)
                row_changed = True
                comment.add ('remove empty name')

        ref  = ref or ''
        name = name or ''

        if length < args.min_length:

            # only check for wrong refs on short ways
            if refs_in_ref - refs_in_routes:
                ref_should_be = join_ref (refs_in_routes)
                if way:
                    set_tag (way, 'ref', ref_should_be)
                    row_changed = True
                    comment.add ('fix refs from hiking routes')
                #print (highway, way_id, length, ref, ref_should_be)
                print ("{highway:8} {way_id:10} {length:6.0f} ref  '{ref}' should be '{refs}'".format (
                    highway = highway, way_id = way_id, length = length, ref = ref, refs = ref_should_be))
                faulty_ways.add (way_id)

            if (refs_in_name - refs_in_routes):
                name_should_be = join_name (refs_in_routes, names_in_routes | names_in_name)
                if way:
                    set_tag (way, 'name', name_should_be)
                    row_changed = True
                    comment.add ('fix names from hiking routes')

                print ("{highway:8} {way_id:10} {length:6.0f} name '{name}' should be '{names}'".format (
                    highway = highway, way_id = way_id, length = length, name = name, names = name_should_be))
                faulty_ways.add (way_id)

        else:

            # the refs on the way dont match the refs on the routes
            if refs_in_ref != refs_in_routes:
                ref_should_be = join_ref (refs_in_routes)
                if way:
                    set_tag (way, 'ref', ref_should_be)
                    row_changed = True
                    comment.add ('put refs from hiking routes into way ref')
                #print (highway, way_id, length, ref, ref_should_be)
                print ("{highway:8} {way_id:10} {length:6.0f} ref  '{ref}' should be '{refs}'".format (
                    highway = highway, way_id = way_id, length = length, ref = ref, refs = ref_should_be))
                faulty_ways.add (way_id)

            if (highway == 'track'):
                # a track already shows name *and* refs on the map
                # so remove refs from track names
                name_should_be = join_name (set (), names_in_routes | names_in_name)
                if refs_in_name:
                    if way:
                        set_tag (way, 'name', name_should_be)
                        row_changed = True
                        comment.add ('remove refs from track name')

                    print ("{highway:8} {way_id:10} {length:6.0f} name '{name}' should be '{names}'".format (
                        highway = highway, way_id = way_id, length = length, name = name, names = name_should_be))
                    faulty_ways.add (way_id)
            else:
                # a path shows only the name on the map
                # so we must put the refs into the name
                name_should_be = join_name (refs_in_routes, names_in_routes | names_in_name)
                if (refs_in_routes != refs_in_name) or (names_in_routes - names_in_name):
                    if way:
                        set_tag (way, 'name', name_should_be)
                        row_changed = True
                        comment.add ('put refs from hiking routes into path name')

                    #print (highway, way_id, length, name, name_should_be)
                    if 0:
                        print ()
                        print ("refs  in routes: ", refs_in_routes)
                        print ("names in routes: ", names_in_routes)
                        print ("refs  in ref:    ", refs_in_ref)
                        print ("refs  in name:   ", refs_in_name)
                        print ("names in name:   ", names_in_name)

                    print ("{highway:8} {way_id:10} {length:6.0f} name '{name}' should be '{names}'".format (
                        highway = highway, way_id = way_id, length = length, name = name, names = name_should_be))
                    faulty_ways.add (way_id)

        if way and row_changed and args.edit:
            if cs is None:
                cs = api.ChangesetCreate ({})

            way = api.WayUpdate (way)
            changes += 1
            comment.add ('add refs from hiking routes to tracks, to make the routes show up on the main osm map')

            if changes >= args.batch_size:
                print ("changeset %d (%d changes)" % (cs, changes))
                api.ChangesetUpdate ({ 'comment' : ', '.join (list (comment)) })
                api.ChangesetClose ()
                cs = None
                changes = 0
                comment = set ()

    if cs is not None:
        print ("changeset %d (%d changes)" % (cs, changes))
        api.ChangesetUpdate ({ 'comment' : ', '.join (list (comment)) })
        api.ChangesetClose ()

    print ('Faulty way ids: ' + ' '.join ([str (n) for n in sorted (faulty_ways)]))
