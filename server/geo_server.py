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


def _hikemap_altimetry (route_id):
    """ Return route altimetry.

    This always returns altimetry for the whole route.
    """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT ST_AsGeoJSON (ST_Collect (linestringz ORDER BY sequence_id))::json AS geom,
               rel_id AS geo_id,
               rel_tags AS tags
        FROM ways_in_routes w
        WHERE rel_id = :relation_id AND member_role = ''
        GROUP BY rel_id, rel_tags
        """, init_query_params (conn, relation_id = route_id))

        return common.make_geojson_response (
            res, 'geom, geo_id, tags'
        )


@geo_app.route ('/altimetry/<int:route_id>')
def altimetry (route_id):
    """ Return route altimetry. """

    return _hikemap_altimetry (route_id)


@geo_app.route ('/routes/<route_type:route_type>.json')
def routes_geojson (route_type):
    """ Return all routes that intersect the bounding box.
    """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT NULL as geom,
               rel_id   AS geo_id,
               rel_tags AS tags
        FROM ways_in_routes w
        WHERE linestring && {bbox}
          AND rel_tags->'route' = :route_type
        GROUP BY rel_id, rel_tags
        """, init_query_params (conn, route_type = route_type))

        return common.make_geojson_response (
            res, 'geom, geo_id, tags'
        )


@geo_app.route ('/extent.json')
def extent_json ():
    """ Return the max. extent of all data points in latlng. """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT ST_AsGeoJSON ({bbox})::json AS geom, 1 as geo_id
        """, { 'bbox' : make_bbox (current_app.config['GEO_EXTENT']) })

        return common.make_geojson_response (res, 'geom, geo_id')
