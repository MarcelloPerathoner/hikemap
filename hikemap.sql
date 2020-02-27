DROP VIEW IF EXISTS hiking_routes_ref_view;
DROP VIEW IF EXISTS hiking_routes_name_view;
DROP VIEW IF EXISTS hiking_routes_halo_view;
DROP VIEW IF EXISTS hiking_paths_casing_view;
DROP VIEW IF EXISTS hiking_paths_fill_view;
DROP VIEW IF EXISTS hiking_roads_text_ref;
DROP VIEW IF EXISTS hiking_paths_text_name;
DROP VIEW IF EXISTS local_names;

DROP VIEW IF EXISTS all_routes_view CASCADE;
DROP VIEW IF EXISTS planet_osm_line_view CASCADE;
DROP VIEW IF EXISTS relations_of;
DROP VIEW IF EXISTS route_lines;
DROP VIEW IF EXISTS check_routes;

DROP AGGREGATE IF EXISTS ref_agg (TEXT);

DROP FUNCTION IF EXISTS altilenimetry;
DROP FUNCTION IF EXISTS altimetry;
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
  -- SELECT $1 || string_to_array (regexp_replace ($2, 'AV(\d+)', '\1⃤'), ';');
  SELECT $1 || string_to_array ($2, ';');
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

ALTER TABLE planet_osm_line ADD COLUMN IF NOT EXISTS route_refs TEXT;
ALTER TABLE planet_osm_line ADD COLUMN IF NOT EXISTS route_names TEXT;

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


CREATE VIEW relations_of AS
SELECT *
FROM snapshot.relation_members mn
    JOIN snapshot.relations r ON mn.relation_id = r.id;


CREATE VIEW all_routes_view AS
WITH RECURSIVE all_routes (way_id, rel_id, rel_tags) AS (
    -- select all lines in some relation
    SELECT line.osm_id AS way_id, r.id AS rel_id, r.tags AS rel_tags
    FROM planet_osm_line line
      JOIN relations_of r ON r.member_id = line.osm_id
  UNION
    -- add all super relations
    SELECT ar.way_id, r.id AS rel_id, r.tags AS rel_tags
    FROM all_routes ar
      JOIN relations_of r ON r.member_id = ar.rel_id
)
SELECT way_id,
       ref_agg (rel_tags->'ref') AS refs,
       ref_agg (rel_tags->'name') AS names,
       array_agg (rel_id) AS rel_ids
FROM all_routes ar
WHERE rel_tags->'route' = 'hiking'
GROUP BY way_id;


UPDATE planet_osm_line l
SET route_refs = ar.refs, route_names = ar.names
FROM all_routes_view ar
WHERE l.osm_id = ar.way_id;

CREATE VIEW hiking_routes_ref_view AS
SELECT route_refs, (ST_Dump (ST_LineMerge (ST_Collect (way)))).geom as way
FROM planet_osm_line_view
WHERE route_refs IS NOT NULL
GROUP BY route_refs;

CREATE VIEW hiking_routes_name_view AS
SELECT route_names, (ST_Dump (ST_LineMerge (ST_Collect (way)))).geom as way
FROM planet_osm_line_view
WHERE route_names IS NOT NULL
GROUP BY route_names;

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

-- returns altimetry of a linestring, elevation in m in Z
CREATE FUNCTION altimetry (geometry (LineString)) RETURNS geometry (LineString, 3857) AS $$
WITH
  points3d AS
    (SELECT ST_MakePoint (ST_X (p.geom), ST_Y (p.geom), ST_Value (dtm.rast, 1, p.geom)) AS geom
    FROM (SELECT (ST_DumpPoints (ST_Transform ($1, 3857))).geom) AS p
    JOIN raster_dtm dtm ON (ST_Intersects (dtm.rast, p.geom)))
  SELECT ST_MakeLine (geom) FROM points3d;
$$ LANGUAGE SQL IMMUTABLE;

-- returns altimetry and walked distance of a linestring,
-- elevation in m in Z, distance in m in M
CREATE FUNCTION altilenimetry (geometry (LineString)) RETURNS geometry (LineString, 3857) AS $$
WITH
  -- points and indices
  points2d AS
    (SELECT (dp).geom AS geom,
            (dp).path[1] AS index
     FROM (SELECT ST_DumpPoints (ST_Transform ($1, 3857)) AS dp) AS q),

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


CREATE VIEW check_routes AS
SELECT r.id                  AS rel,
       r.tags->'route'       AS route,
       r.tags->'ref'         AS "ref",
       r.tags->'name'        AS "name",
       r.tags->'network'     AS network,
       r.tags->'osmc:symbol' AS symbol
FROM snapshot.relations r
WHERE r.tags->'route' IN ('hiking', 'bicycle', 'mtb', 'piste', 'bus');


-- to check if route segments are ordered
CREATE VIEW route_lines AS
SELECT mn.relation_id AS rel,
       ST_AsGeoJSON (ST_Collect (w.linestring ORDER BY sequence_id)) AS lines
FROM snapshot.relation_members mn
    JOIN snapshot.ways w ON w.id = mn.member_id
WHERE mn.member_role = ''
GROUP BY rel;
