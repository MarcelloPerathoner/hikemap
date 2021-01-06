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


@geo_app.route ('/altimetry/<int:route_id>/')
@geo_app.route ('/altimetry/<int:route_id>/<alternate>')
def altimetry (route_id, alternate = ''):
    """ Return route altimetry and POIs.

    This always returns altimetry for the whole route.
    """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT ST_AsGeoJSON (ST_Collect (linestringz ORDER BY sequence_id), 6)::json AS geom,
               rel_id || '/' || member_role AS geo_id,
               member_role,
               rel_tags AS tags
        FROM ways_in_routes w
        WHERE rel_id = :relation_id AND member_role = :alt AND exist (way_tags, 'highway')
        GROUP BY rel_id, rel_tags, member_role

        UNION ALL

        SELECT ST_AsGeoJSON (linestringz, 6)::json AS geom,
               way_id || '/' || member_role AS geo_id,
               member_role,
               way_tags AS tags
        FROM ways_in_routes w
        WHERE rel_id = :relation_id AND member_role = :alt AND NOT exist (way_tags, 'highway')

        UNION ALL

        SELECT ST_AsGeoJSON (geomz, 6)::json AS geom,
               node_id || '/' || member_role AS geo_id,
               member_role,
               node_tags AS tags
        FROM pois_in_routes w
        WHERE rel_id = :relation_id AND member_role = :alt

        """, init_query_params (conn, relation_id = route_id, alt = alternate))

        return common.make_geojson_response (
            res, 'geom, geo_id, member_role, tags'
        )


@geo_app.route ('/routes/<route_type:route_type>.json')
def routes_geojson (route_type):
    """ Return all routes that intersect the bounding box.
    """

    if route_type == 'hiking':
        route_type = (route_type, 'foot')
    else:
        route_type = (route_type, )

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT NULL as geom,
               rel_id || '/' || member_role AS geo_id,
               member_role,
               rel_tags AS tags
        FROM ways_in_routes w
        WHERE linestring && {bbox}
          AND rel_tags->'route' IN :route_type
        GROUP BY rel_id, rel_tags, member_role
        """, init_query_params (conn, route_type = route_type))

        return common.make_geojson_response (
            res, 'geom, geo_id, member_role, tags'
        )


@geo_app.route ('/extent.json')
def extent_json ():
    """ Return the max. extent of all data points in latlng. """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT ST_AsGeoJSON ({bbox})::json AS geom, 1 as geo_id
        """, { 'bbox' : make_bbox (current_app.config['GEO_EXTENT']) })

        return common.make_geojson_response (res, 'geom, geo_id')
