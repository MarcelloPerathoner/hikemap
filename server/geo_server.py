#!/usr/bin/python3
# -*- encoding: utf-8 -*-

"""Geo queries API server for the Hikemap."""

from flask import abort, current_app, request, Blueprint

import common
from db_tools import execute

class Config (object):
    pass


class geoBlueprint (Blueprint):
    def init_app (self, app):
        app.config.from_object (Config)


geo_app  = geoBlueprint ('geo',  __name__)


def make_extent (extent):
    ex = [float (x) for x in extent.split (',')]
    return "{ex[0]},{ex[1]},{ex[2]},{ex[3]}".format (ex = ex)


def init_query_params (conn):
    try:
        params = {}
        if 'extent' in request.args:
            params['extent'] = make_extent (request.args.get ('extent'))
            current_app.logger.info ("extent: {extent}".format (extent = params['extent']))

    except ValueError:
        abort (400)

    return params


@geo_app.route ('/hikemap.geojson')
def hikemap_geojson ():
    """ Return all places along with mss count. """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT ST_AsGeoJSON (ST_Transform (way, 4326))::json AS geom,
               osm_id as geo_id, highway, sac_scale, trail_visibility, tracktype, surface,
               route_refs
        FROM planet_osm_line_view
        WHERE route_refs IS NOT NULL
           AND way && ST_Transform (
              ST_MakeEnvelope ({extent}, 4326), 3857
           )
        """, init_query_params (conn))

        return common.make_geojson_response (
            res, 'geom, geo_id, highway, sac_scale, trail_visibility, tracktype, surface, route_refs'
        )


@geo_app.route ('/buslines.geojson')
def buslines_geojson ():
    """ Return all public transport lines. """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT way AS geom, osm_id AS geo_id, type
        FROM bus_lines_fill_view
        """, init_query_params (conn))

        return common.make_geojson_response (
            res, 'geom, geo_id, type'
        )


@geo_app.route ('/extent.json')
def extent_json ():
    """ Return the max. extent of all data points in latlng. """

    with current_app.config.dba.engine.begin () as conn:
        res = execute (conn, """
        SELECT ST_AsGeoJSON (ST_MakeEnvelope ({extent}, 4326))::json AS geom, 1 as geo_id
        """, { 'extent' : make_extent (current_app.config['GEO_EXTENT']) })

        return common.make_geojson_response (res, 'geom, geo_id')


@geo_app.route ('/', methods = ['GET', 'OPTIONS'])
def info_json ():
    """ Info endpoint: send information about server and available layers. """

    i = {
        'title'    : 'Hikemap App Server',
        'layers'   : current_app.config['GEO_LAYERS'],
    }
    return common.make_json_response (i, 200)
