#!/usr/bin/python3

import os
from pathlib import Path

import osmapi
import sqlalchemy

MY_UID = 8199540

# BOUNDARY_REL = 47046 # South Tyrol

# BOUNDARY_REL = 47229 # Campitello
# BOUNDARY_REL = 47234 # Ciastel
# BOUNDARY_REL = 47242 # Sëlva
# BOUNDARY_REL = 47244 # S. Crestina
# BOUNDARY_REL = 47252 # Corvara
# BOUNDARY_REL = 47265 # Urtijëi
# BOUNDARY_REL = 47275 # Laion

BOUNDARY_REL = (
    # 47229, # Campitello
    47234, # Ciastel
    47242, # Sëlva
    47244, # S. Crestina
    47252, # Corvara
    47265, # Urtijëi
    47275, # Laion
)

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

rows = conn.execute (sqlalchemy.text ("""
WITH boundaries AS (
SELECT ST_Polygonize (w.linestring) AS boundary
FROM snapshot.relations r
    JOIN snapshot.relation_members mn ON mn.relation_id = r.id
    JOIN snapshot.ways w              ON w.id = mn.member_id
WHERE r.id IN :boundaries
)

SELECT ST_Simplify (ST_Union (boundary), 0.01) AS boundary FROM boundaries
"""), { 'boundaries' : BOUNDARY_REL })

boundary = rows.fetchone ()[0]
