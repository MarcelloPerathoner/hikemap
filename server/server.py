#!/usr/bin/python3
# -*- encoding: utf-8 -*-

"""The API server for the Hikemap."""

import argparse
import logging
import time

import flask
from flask import current_app, Flask, request
from werkzeug.routing import Map, Rule, Submount

import common
import config
from config import args, init_logging

from db_tools import PostgreSQLEngine

from info_server     import info_app
from tile_server     import tile_app
from geo_server      import geo_app, RouteTypeConverter

class Config (object):
    APPLICATION_HOST  = 'localhost'
    APPLICATION_PORT  = 5000
    CONFIG_FILE       = 'server.conf' # default relative to server.py
    USE_RELOADER      = False
    USE_DEBUGGER      = False
    SERVER_START_TIME = str (int (time.time ())) # for cache busting


def build_parser (default_config_file):
    """ Build the commandline parser. """

    parser = argparse.ArgumentParser (description = __doc__)

    parser.add_argument (
        '-v', '--verbose', dest='verbose', action='count',
        help='increase output verbosity', default=0
    )
    parser.add_argument (
        '-c', '--config-file', dest='config_file',
        default=default_config_file, metavar='CONFIG_FILE',
        help="the config file (default='%s')" % default_config_file
    )
    return parser


def create_app (Config):
    app = Flask (__name__)

    app.config.from_object (Config)
    app.url_map.converters['route_type'] = RouteTypeConverter

    app.config.from_pyfile (Config.CONFIG_FILE)

    app.register_blueprint (info_app, url_prefix = '/info')
    tile_app.init_app (app)

    app.register_blueprint (tile_app, url_prefix = '/tile')
    tile_app.init_app (app)

    app.register_blueprint (geo_app, url_prefix = '/geo')
    geo_app.init_app (app)

    app.logger.setLevel (Config.LOG_LEVEL)

    app.config.dba = PostgreSQLEngine (**app.config)

    return app


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    build_parser ('server.conf').parse_args (namespace = args)
    init_logging (
        args,
        flask.logging.default_handler,
        logging.FileHandler ('server.log')
    )

    Config.LOG_LEVEL   = args.log_level
    Config.CONFIG_FILE = args.config_file

    app = create_app (Config)

    @app.after_request
    def add_headers (response):
        origin = request.headers.get ('Origin')
        if origin and (origin == app.config['CORS_ALLOW_ORIGIN'] or
                       origin.startswith ('http://localhost')):
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type' # allow application/json
        response.headers['Server'] = 'Jetty 0.8.15'
        return response

    app.logger.info ("Mounted {name} at {host}:{port} from conf {conf}".format (
        name = app.config['APPLICATION_NAME'],
        host = app.config['APPLICATION_HOST'],
        port = app.config['APPLICATION_PORT'],
        conf = Config.CONFIG_FILE
    ))

    run_simple (
        app.config['APPLICATION_HOST'],
        app.config['APPLICATION_PORT'],
        app,
        use_reloader = app.config.get ('USE_RELOADER', False),
        use_debugger = app.config.get ('USE_DEBUGGER', False),
        extra_files  = app.config.get ('EXTRA_FILES', []),
    )
