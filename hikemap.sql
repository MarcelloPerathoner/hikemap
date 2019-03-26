DROP VIEW IF EXISTS hiking_path_fill;
DROP VIEW IF EXISTS hiking_text_ref;
DROP VIEW IF EXISTS hiking_text_ref_refs;
DROP VIEW IF EXISTS local_names;

CREATE OR REPLACE VIEW hiking_path_fill AS
SELECT osm_id,
       highway,
       tracktype,
       surface,
       ref,
       COALESCE (tags->'sac_scale', '') AS sac_scale,
       COALESCE (tags->'trail_visibility', '') AS trail_visibility,
       way
FROM planet_osm_line
WHERE highway IN ('path', 'footway', 'track')
ORDER BY sac_scale;


CREATE OR REPLACE VIEW hiking_text_ref_refs AS
SELECT osm_id,
       way,
       highway,
       COALESCE (name, array_to_string (ARRAY["name:lld", "name:de", "name:it"], ' - ')) as name,
       string_to_array (COALESCE ("ref:hiking", ref, ''), ';') AS refs
FROM planet_osm_line
WHERE route = 'hiking';


CREATE OR REPLACE VIEW hiking_text_ref AS
SELECT osm_id,
       highway,
       name,
       refs,
       height,
       width,
       way
FROM (
     SELECT osm_id,
            way,
            highway,
            name,
            array_to_string (refs, ' - ') AS refs,
            array_length (refs, 1) AS height,
            (SELECT MAX (char_length (ref)) FROM unnest (refs) AS u (ref)) AS width
     FROM hiking_text_ref_refs AS p
) AS q
WHERE height > 0 AND height <= 4 AND width <= 11
ORDER BY CASE
      WHEN highway = 'residential' THEN 32
      WHEN highway = 'service' THEN 31
      WHEN highway = 'track' THEN 30
      WHEN highway = 'path' THEN 6
      WHEN highway = 'footway' THEN 5
      ELSE 0
END DESC,
height DESC,
width DESC,
refs,
osm_id;


CREATE OR REPLACE VIEW local_names AS
SELECT osm_id,
       "natural",
       name,
       ref,
       ST_Length (way) / 1000 as km_length,
       ST_Simplify (way, 50, TRUE) as way
FROM planet_osm_line
WHERE "natural" IN ('valley', 'ridge');
