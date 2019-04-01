DROP VIEW IF EXISTS hiking_routes_ref;
DROP VIEW IF EXISTS planet_osm_rels_view;
DROP VIEW IF EXISTS planet_osm_line_view;
DROP VIEW IF EXISTS hiking_path_fill;
DROP VIEW IF EXISTS local_names;

DROP AGGREGATE IF EXISTS ref_agg (TEXT);

DROP FUNCTION IF EXISTS route_names;
DROP FUNCTION IF EXISTS route_refs;
DROP FUNCTION IF EXISTS all_relations;
DROP FUNCTION IF EXISTS refs_to_string;
DROP FUNCTION IF EXISTS add_refs;
DROP FUNCTION IF EXISTS array_distinct;
DROP FUNCTION IF EXISTS natsort;

CREATE OR REPLACE FUNCTION natsort (text) RETURNS text[] AS
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


CREATE VIEW hiking_path_fill AS
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
       COALESCE ("ref:hiking", ref, '') AS ref,
       COALESCE (tags->'sac_scale', '') AS sac_scale,
       COALESCE (tags->'trail_visibility', '') AS trail_visibility,
       tracktype,
       surface,
       way
FROM planet_osm_line;


CREATE VIEW planet_osm_rels_view AS
SELECT id AS osm_id,
       COALESCE (tagstore->'name', array_to_string (
         ARRAY[tagstore->'name:lld', tagstore->'name:de', tagstore->'name:it'], ' - ')) as name,
       COALESCE (tagstore->'ref:hiking', tagstore->'ref', '') AS ref,
       parts
FROM planet_osm_rels
WHERE route = 'hiking';


CREATE FUNCTION route_refs (bigint) RETURNS TEXT AS $$
SELECT ref_agg (route.ref)
FROM planet_osm_rels_view route
WHERE route.osm_id IN (SELECT osm_id FROM all_relations ($1, 'route'))
$$ LANGUAGE SQL IMMUTABLE;


CREATE FUNCTION route_names (bigint) RETURNS TEXT AS $$
SELECT ref_agg (route.name)
FROM planet_osm_rels_view route
WHERE route.osm_id IN (SELECT osm_id FROM all_relations ($1, 'route'))
$$ LANGUAGE SQL IMMUTABLE;


CREATE VIEW hiking_routes_ref AS
SELECT l.osm_id,
       l.highway,
       l.name,
       l.ref,
       l.sac_scale,
       l.trail_visibility,
       route_names (l.osm_id) AS route_name,
       route_refs (l.osm_id)  AS route_ref,
       l.way
FROM planet_osm_line_view l;
