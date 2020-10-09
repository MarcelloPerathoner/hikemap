#!/usr/bin/python3
# -*- encoding: utf-8 -*-

"""A simple info server.

Serve general information about this service.

"""

from flask import current_app, Blueprint

import common

class Config (object):
    pass


class infoBlueprint (Blueprint):
    def init_app (self, app):
        app.config.from_object (Config)


info_app = infoBlueprint ('info_server', __name__)


@info_app.route ('/')
def info_json ():
    """ Info endpoint: send information about server and available layers. """

    conf = current_app.config
    i = {
        'title'       : 'Hikemap Tile Server',
        'min_zoom'    : conf['TILE_MIN_ZOOM'],
        'max_zoom'    : conf['TILE_MAX_ZOOM'],
        'tile_layers' : conf['TILE_LAYERS'],
        'geo_layers'  : conf['GEO_LAYERS'],
        'wms_layers'  : conf['WMS_LAYERS'],
    }
    return common.make_json_response (i, 200)
