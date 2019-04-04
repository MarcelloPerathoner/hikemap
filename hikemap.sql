DROP VIEW IF EXISTS hiking_routes_ref_view;
DROP VIEW IF EXISTS hiking_routes_halo_view;
DROP VIEW IF EXISTS hiking_paths_casing_view;
DROP VIEW IF EXISTS hiking_paths_fill_view;
DROP VIEW IF EXISTS hiking_roads_text_ref;
DROP VIEW IF EXISTS hiking_paths_text_name;
DROP VIEW IF EXISTS local_names;

DROP VIEW IF EXISTS all_routes_view      CASCADE;
DROP VIEW IF EXISTS planet_osm_rels_view CASCADE;
DROP VIEW IF EXISTS planet_osm_line_view CASCADE;

DROP AGGREGATE IF EXISTS ref_agg (TEXT);

DROP FUNCTION IF EXISTS altilenimetry;
DROP FUNCTION IF EXISTS altimetry;
DROP FUNCTION IF EXISTS all_relations;
DROP FUNCTION IF EXISTS ref_to_string;
DROP FUNCTION IF EXISTS refs_to_string;
DROP FUNCTION IF EXISTS add_refs;
DROP FUNCTION IF EXISTS array_distinct;
DROP FUNCTION IF EXISTS natsort;

CREATE FUNCTION natsort (text) RETURNS text[] AS
$$
  SELECT array_agg (
    CASE
      WHEN a.match_array[1]::text IS NOT NULL
        THEN a.match_array[1]::text
      ELSE length (a.match_array[2]::text) || a.match_array[2]::text
    END::text
  )
  FROM (
    SELECT regexp_matches (
      CASE WHEN $1 = '' THEN NULL ELSE $1 END, E'(\\D+)|(\\d+)', 'g'
    ) AS match_array
  ) AS a
$$ LANGUAGE sql IMMUTABLE;

CREATE FUNCTION array_distinct(anyarray) RETURNS anyarray AS $$
  SELECT array_agg(DISTINCT x) FROM unnest($1) t(x);
$$ LANGUAGE SQL IMMUTABLE;

CREATE FUNCTION ref_to_string(TEXT) RETURNS TEXT AS $$
  SELECT array_to_string (array_agg (x ORDER BY natsort (x)), ' - ')
    FROM unnest(array_distinct (string_to_array ($1, ';'))) t(x);
$$ LANGUAGE SQL IMMUTABLE;

CREATE FUNCTION add_refs(TEXT [], TEXT) RETURNS TEXT[] AS $$
  SELECT $1 || string_to_array (regexp_replace ($2, 'AV(\d+)', '\1⃤'), ';');
$$ LANGUAGE SQL IMMUTABLE;

CREATE FUNCTION refs_to_string(TEXT[]) RETURNS TEXT AS $$
  SELECT array_to_string (array_agg (x ORDER BY natsort (x)), ' - ')
    FROM unnest(array_distinct ($1)) t(x);
$$ LANGUAGE SQL IMMUTABLE;

CREATE AGGREGATE ref_agg (TEXT) (
  sfunc = add_refs,
  stype = TEXT[],
  initcond = '{}',
  finalfunc = refs_to_string
);

ALTER TABLE planet_osm_rels ADD COLUMN IF NOT EXISTS tagstore hstore;
ALTER TABLE planet_osm_rels ADD COLUMN IF NOT EXISTS "type" TEXT;
ALTER TABLE planet_osm_rels ADD COLUMN IF NOT EXISTS route TEXT;
UPDATE planet_osm_rels SET tagstore = hstore (tags);
UPDATE planet_osm_rels SET "type"   = tagstore->'type';
UPDATE planet_osm_rels SET route    = tagstore->'route';

ALTER DATABASE osm SET postgis.gdal_enabled_drivers TO 'GTiff PNG JPEG';
ALTER DATABASE osm SET postgis.enable_outdb_rasters = True;

ALTER TABLE planet_osm_line ADD COLUMN IF NOT EXISTS route_refs TEXT;
ALTER TABLE planet_osm_line ADD COLUMN IF NOT EXISTS route_names TEXT;

CREATE FUNCTION all_relations (bigint, text) RETURNS TABLE (osm_id bigint, "type" text) AS $$
WITH RECURSIVE all_rels (osm_id) AS (
    SELECT rels.id AS osm_id, rels.type AS "type"
    FROM planet_osm_rels rels
    WHERE rels.parts @> ARRAY[$1]
  UNION
    SELECT rels.id AS osm_id, rels.type AS "type"
    FROM all_rels, planet_osm_rels rels
    WHERE rels.parts @> ARRAY[all_rels.osm_id]
)
SELECT osm_id, "type" FROM all_rels;
$$ LANGUAGE SQL IMMUTABLE;


CREATE VIEW local_names AS
SELECT osm_id,
       "natural",
       name,
       ref,
       ST_Length (way)::integer as way_length,
       way
FROM planet_osm_line
WHERE "natural" IN ('arete', 'ridge', 'valley');


CREATE VIEW hiking_paths_fill_view AS
SELECT osm_id,
       highway,
       COALESCE (tags->'sac_scale', '') AS sac_scale,
       COALESCE (tags->'trail_visibility', '') AS trail_visibility,
       tracktype,
       surface,
       way
FROM planet_osm_line
WHERE highway IN ('path', 'footway', 'track', 'via_ferrata')
ORDER BY sac_scale;


CREATE VIEW planet_osm_line_view AS
SELECT osm_id,
       highway,
       COALESCE (name, array_to_string (ARRAY["name:lld", "name:de", "name:it"], ' - ')) as name,
       COALESCE ("ref:hiking", ref, substr (name, 1, 3), '') AS ref,
       COALESCE (tags->'sac_scale', '') AS sac_scale,
       COALESCE (tags->'trail_visibility', '') AS trail_visibility,
       tracktype,
       surface,
       route_refs,
       route_names,
       way
FROM planet_osm_line;


CREATE VIEW planet_osm_rels_view AS
SELECT id AS osm_id,
       COALESCE (tagstore->'name', array_to_string (
         ARRAY[tagstore->'name:lld', tagstore->'name:de', tagstore->'name:it'], ' - ')) as name,
       COALESCE (tagstore->'ref:hiking', tagstore->'ref', substr (tagstore->'name', 1, 3), '') AS ref,
       parts
FROM planet_osm_rels
WHERE route = 'hiking';


CREATE VIEW all_routes_view AS
WITH RECURSIVE all_routes (osm_id) AS (
    SELECT osm_id, rels.id AS rel_id, rels.type AS "type"
    FROM planet_osm_line line
      JOIN planet_osm_rels rels ON rels.parts @> ARRAY[line.osm_id]
    WHERE line.highway != '' AND rels.route = 'hiking'
  UNION
    SELECT osm_id, rels.id AS rel_id, rels.type AS "type"
    FROM all_routes line
      JOIN planet_osm_rels rels ON rels.parts @> ARRAY[line.rel_id]
)
SELECT ar.osm_id, ref_agg (rels.ref) AS refs, ref_agg (name) AS names
FROM all_routes ar
  JOIN planet_osm_rels_view rels ON ar.rel_id = rels.osm_id
GROUP BY ar.osm_id;


UPDATE planet_osm_line l
SET route_refs = ar.refs
FROM all_routes_view ar
WHERE l.osm_id = ar.osm_id;

UPDATE planet_osm_line l
SET route_names = ar.names
FROM all_routes_view ar
WHERE l.osm_id = ar.osm_id;

CREATE VIEW hiking_routes_ref_view AS
SELECT route_refs, (ST_Dump (ST_LineMerge (ST_Collect (way)))).geom as way
FROM planet_osm_line_view
GROUP BY route_refs;

CREATE VIEW hiking_routes_halo_view AS
SELECT * FROM planet_osm_line_view;

CREATE VIEW hiking_paths_casing_view AS
SELECT * FROM hiking_paths_fill_view;

CREATE VIEW hiking_roads_text_ref AS
SELECT way, highway, ref AS refs
FROM planet_osm_line_view
WHERE ref != '' AND ref_to_string (ref) != route_refs;

CREATE VIEW hiking_paths_text_name AS
SELECT way, highway, name AS names
FROM planet_osm_line_view
WHERE name != '' AND ref_to_string (name) != route_refs;

CREATE FUNCTION altimetry (geometry (LineString, 3857)) RETURNS geometry (LineString, 3857) AS $$
WITH
  points3d AS
    (SELECT ST_MakePoint (ST_X (p.geom), ST_Y (p.geom), ST_Value (dtm.rast, 1, p.geom)) AS geom
    FROM (SELECT (ST_DumpPoints ($1)).geom) AS p
    JOIN raster_dtm dtm ON (ST_Intersects (dtm.rast, p.geom)))
  SELECT ST_MakeLine (geom) FROM points3d;
$$ LANGUAGE SQL IMMUTABLE;

CREATE FUNCTION altilenimetry (geometry (LineString, 3857)) RETURNS geometry (LineString, 3857) AS $$
WITH
  -- points and indices
  points2d AS
    (SELECT (dp).geom AS geom,
            (dp).path[1] AS index
     FROM (SELECT ST_DumpPoints ($1) AS dp) AS q),

  -- add altimetry
  points3d AS
    (SELECT ST_MakePoint (ST_X (p.geom), ST_Y (p.geom), ST_Value (dtm.rast, 1, p.geom)) AS geom,
            p.index
    FROM points2d p
    JOIN raster_dtm dtm ON (ST_Intersects (dtm.rast, p.geom))),

  -- add cumulative distance from origin
  points4d AS
    (SELECT ST_MakePoint (
                ST_X (p.geom),
                ST_Y (p.geom),
                ST_Z (p.geom),
                ST_Length2D (ST_MakeLine (p.geom) OVER (ORDER BY p.index))
                ) AS geom
     FROM points3d p)

SELECT ST_MakeLine (geom) FROM points4d;
$$ LANGUAGE SQL IMMUTABLE;

DROP VIEW pg_hill_shade_view;
CREATE VIEW pg_hill_shade_view AS
SELECT ST_Hillshade (rast, 1, '8BUI') AS rast
FROM raster_dtm;
