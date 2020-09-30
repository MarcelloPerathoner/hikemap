#!/usr/bin/python3

import os
from pathlib import Path
import re

import osmapi
import sqlalchemy

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
cs = None
changes = 0

rows = conn.execute ("select rel, ref, name, network, symbol from check_routes order by ref")
for row in rows:
    # get (maybe stale) content from local database
    rel, ref, name, network, symbol = row
    new_symbol = "red:red:white_bar:{ref}:black".format (ref = ref)

    # continue to next row if everything is fine
    if name is None and symbol == new_symbol:
        continue

    # get current content from api
    r = api.RelationGet (row[0])
    if r['uid'] != 8199540: # only fix our own changesets
        continue

    ref     = r['tag'].get ('ref')
    name    = r['tag'].get ('name')
    network = r['tag'].get ('network')
    symbol  = r['tag'].get ('osmc:symbol')
    msg     = "on route %s (%s)" % (ref, rel)
    row_changed = False
    comment = set ()

    if ref and name:
        m = re.match ('^%s - (.+)$' % ref, name)
        if m:
            new_name = m.group (1)
            print ('Bogus name : "%s" %s' % (name, msg))
            print ('New name   : "%s" %s' % (new_name, msg))

            r['tag']['name'] = new_name
            comment.add ('fix route name')
            row_changed = True

    if ref and re.match ('^[0-9]+[ABC]?$', ref) :
        if symbol != new_symbol:
            print ("Bogus symbol: %s %s" % (symbol, msg))

            r['tag']['osmc:symbol'] = new_symbol
            comment.add ('fix osmc:symbol')
            row_changed = True

    if ref and network is None:
        print ("No network %s" % msg)

        r['tag']['network'] = 'lwn'
        comment.add ('add network')
        row_changed = True

    if 0 and row_changed:
        if cs is None:
            cs = api.ChangesetCreate ({})
        r = api.RelationUpdate (r)
        changes += 1

    if changes >= 10:
        print ("%d changes" % changes)
        api.ChangesetUpdate ({ 'comment' : ', '.join (list (comment)) })
        api.ChangesetClose ()
        cs = None
        changes = 0


if cs is not None:
    print ("%d changes" % changes)
    api.ChangesetUpdate ({ 'comment' : ', '.join (list (comment)) })
    api.ChangesetClose ()
