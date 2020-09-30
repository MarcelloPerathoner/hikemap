#!/usr/bin/python3
# -*- encoding: utf-8 -*-

"""Geo queries API server for the Hikemap."""

from flask import abort, current_app, request, Blueprint
from werkzeug.routing import BaseConverter

import common
from db_tools import execute

class Config (object):
    pass

MAP_IDS = dict ()

class RouteTypeConverter (BaseConverter):

    def to_python (self, value):
        if value in MAP_IDS:
            return value
        abort (404)

    def to_url (self, value):
        return value


class geoBlueprint (Blueprint):
    def init_app (self, app):
        app.config.from_object (Config)
        for l in app.config['GEO_LAYERS']:
            MAP_IDS[l['id']] = l


geo_app  = geoBlueprint ('geo',  __name__)

def make_bbox (extent):
    ex = [float (x) for x in extent.split (',')]
    return "ST_MakeEnvelope ({ex[0]},{ex[1]},{ex[2]},{ex[3]}, 4326)".format (ex = ex)


def init_query_params (conn, **kw):
    try:
        params = dict (kw)
        if 'extent' in request.args:
            params['bbox'] = make_bbox (request.args.get ('extent'))

    except ValueError:
        abort (400)

    return params


def _hikemap_lines (route_type):
    """ Return hiking routes.  Suitable for line layers. """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT ST_AsGeoJSON (ST_LineMerge (ST_Collect (w.linestring ORDER BY rm.sequence_id)))::json AS geom,
               r.id   AS geo_id,
               r.tags AS tags
        FROM snapshot.ways w
          JOIN snapshot.relation_members rm
            ON (rm.member_id, rm.member_type) = (w.id, 'W')
            JOIN snapshot.relations r
              ON rm.relation_id = r.id
        WHERE w.linestring && {bbox}
          AND r.tags->'type'  = 'route'
          AND r.tags->'route' = :route_type
        GROUP BY 2
        """, init_query_params (conn, route_type = route_type))

        return common.make_geojson_response (
            res, 'geom, geo_id, tags'
        )


def _hikemap_shields (route_type):
    """Return routes.  Suitable for shield layers.

    The algorithm used returns one linestring for each route, that spans all
    ways that intersect the bounding box.  If a way is related to many routes,
    that way is included in many linestrings.

    This approach has problems with superroutes, because many routes are
    returned, bringing along a proliferation of shields with the same ref.

    """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        WITH RECURSIVE super_routes (way_id, relation_id) AS (
            -- selects lines in bounding box that are in some relation
            SELECT w.id AS way_id, rm.*
            FROM snapshot.ways w
              JOIN snapshot.relation_members rm
                ON (rm.member_id, rm.member_type) = (w.id, 'W')
            WHERE w.linestring && {bbox}
          UNION
            -- add all super relations
            SELECT sr.way_id, rm.*
            FROM super_routes sr
              JOIN snapshot.relation_members rm
                ON (rm.member_id, rm.member_type) = (sr.relation_id, 'R')
        )

        SELECT ST_AsGeoJSON (ST_LineMerge (ST_Collect (w.linestring ORDER BY sr.sequence_id)))::json AS geom,
               r.id   AS geo_id,
               r.tags AS tags
        FROM super_routes sr
            JOIN snapshot.ways w      ON (sr.way_id      = w.id)
            JOIN snapshot.relations r ON (sr.relation_id = r.id)
        WHERE r.tags->'type'  = 'route'
          AND r.tags->'route' = :route_type
        GROUP BY 2
        """, init_query_params (conn, route_type = route_type))

        return common.make_geojson_response (
            res, 'geom, geo_id, tags'
        )


def _hikemap_altimetry (route_id):
    """ Return route altimetry. """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT ST_AsGeoJSON (altilenimetry (ST_LineInterpolatePoints (
          ST_LineMerge (ST_Collect (w.linestring ORDER BY rm.sequence_id)), 0.01)))::json AS geom,
               r.id   AS geo_id,
               r.tags AS tags
        FROM snapshot.ways w
          JOIN snapshot.relation_members rm
            ON (rm.member_id, rm.member_type) = (w.id, 'W')
            JOIN snapshot.relations r
              ON rm.relation_id = r.id
        WHERE r.id = :relation_id AND rm.member_role = ''
        GROUP BY 2
        """, init_query_params (conn, relation_id = route_id))

        return common.make_geojson_response (
            res, 'geom, geo_id, tags'
        )


@geo_app.route ('/lines/<route_type:route_type>.geojson')
def lines_route_geojson (route_type):
    """ Return routes.  Suitable for line layers. """

    return _hikemap_lines (route_type)


@geo_app.route ('/shields/<route_type:route_type>.geojson')
def shields_route_geojson (route_type):
    """ Return routes.  Suitable for shield layers. """

    return _hikemap_shields (route_type)


@geo_app.route ('/altimetry/<int:route_id>')
def altimetry (route_id):
    """ Return route altimetry. """

    return _hikemap_altimetry (route_id)


@geo_app.route ('/extent.json')
def extent_json ():
    """ Return the max. extent of all data points in latlng. """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT ST_AsGeoJSON ({bbox})::json AS geom, 1 as geo_id
        """, { 'bbox' : make_bbox (current_app.config['GEO_EXTENT']) })

        return common.make_geojson_response (res, 'geom, geo_id')


@geo_app.route ('/', methods = ['GET', 'OPTIONS'])
def info_json ():
    """ Info endpoint: send information about server and available layers. """

    i = {
        'title'    : 'Hikemap App Server',
        'layers'   : current_app.config['GEO_LAYERS'],
    }
    return common.make_json_response (i, 200)
