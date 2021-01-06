<template>
  <div id="map" />
</template>

<script>
/**
 * This module displays a tiled map with overlays.
 *
 * @component map
 * @author Marcello Perathoner
 *
 * GeoJSON specs: https://tools.ietf.org/html/rfc7946
 *
 * TODO: layer for route names
 *       layer for bus route stations / endpoints
 */

import { mapGetters } from 'vuex'

import * as d3    from 'd3';
import * as d3geo from 'd3-geo-projection';
import L          from 'leaflet';
import _          from 'lodash';

import * as tools from '../js/tools.js';

import 'leaflet/dist/leaflet.css';

const l_sym  = d3.local ();  // <symbol> data for <use>

// A Leaflet layer that uses D3 to display features.  Easily styleable with CSS.

L.D3_geoJSON = L.Layer.extend ({
    onAdd (map) {
        const that = this;

        // L.Layer.prototype.onAdd.call (this, map);
        this.map = map;

        this.svg = d3.select (this.getPane ())
            .append ('svg')
            .classed ('d3 hikemap ' + this.my_options.classes, true)
            .style ('--hikemap-color', this.my_options.color);

        this.g = this.svg.append ('g')
            .classed ('leaflet-zoom-hide', true);

        this.project_point = function (x, y) {
            const point = map.latLngToLayerPoint (new L.LatLng (y, x));
            this.stream.point (point.x, point.y);
        }

        this.transform = d3.geoTransform ({ 'point' : this.project_point });

        this.project = (ll) => {
            return map.latLngToLayerPoint (ll);
        }

        this.unproject = (pt) => {
            return map.layerPointToLatLng (pt);
        }

        // this.transform = d3.geoTransform ({ 'point' : projectPoint });
    },
    onRemove (map) {
        this.svg.remove ();
        this.svg = null;
        this.g   = null;
        this.map = null;

        // L.Layer.prototype.onRemove.call (this, map);
    },
    getEvents () {
        return {
            'zoomend' : this.on_zoom_end,
            'moveend' : this.on_move_end,
        };
    },
    setDatasource (url) {
        this.url = url;
    },
    load_data (has_zoomed) {
        const that = this;
        if (this.url
            && (this.map.getZoom () >= this.my_options.min_zoom)
            && (this.map.getZoom () <= this.my_options.max_zoom)) {

            const url    = new URL (this.url);
            const params = this.map.getBounds ().toBBoxString ();
            url.searchParams.set ('extent', params);

            if (process.env.NODE_ENV !== 'production') {
                console.log (`Loading routes for bbox: ${params}`);
            }
            this.set_clip ();

            d3.json (url) // get routes
                .then (function (json) {
                    that.routes_in_bbox = json;
                    that.d3_update (json, has_zoomed);
                });
        } else {
            that.d3_update (tools.empty_feature_collection (), has_zoomed);
        }
    },
    getAttribution () {
        return this.options.attribution;
    },
    setAttribution (attribution) {
        return this.options.attribution = attribution;
    },
    set_clip () {
        const b = this.map.getBounds ();
        this.clip = d3.geoIdentity ().clipExtent ([
            [b.getWest (), b.getSouth ()],
            [b.getEast (), b.getNorth ()]
        ]);
    },
    on_zoom_end (event) {
        const that = this;
        if (process.env.NODE_ENV !== 'production') {
            console.log ('on_zoom_end', event);
        }

        /* smooth the path
           const context = d3.path ();
           const curve = d3.curveCardinal.tension (0.5) (context);
           curve.lineStart ();
           d3.geoPath (that.transform, tools.curveContext (curve)) (response);
           curve.lineEnd ();
           return context;
        */

        this.load_data (true);
        if (this.svg) {
            this.svg.attr ('data-zoom', 'Z'.repeat (this.map.getZoom ()));
        }
    },
    on_move_end (event) {
        if (process.env.NODE_ENV !== 'production') {
            console.log ('on_move_end', event);
        }
        this.load_data (false);
    },
    d3_reset () {
        // override this
    },
    d3_update (geojson, has_zoomed) {
        // override this
    },
});

function fid (feature) {
    return `${feature.id}-${feature.properties.member_role}`;
}

L.Layer_Shields = L.D3_geoJSON.extend ({
    // a shield layer
    onAdd (map) {
        const that = this;

        L.D3_geoJSON.prototype.onAdd.call (this, map);
        this.svg.style ('z-index', 1000);

        this.g_lines      = this.g.append ('g').classed ('layer lines',   true);
        this.g_highlights = this.g.append ('g').classed ('highlight',     true);
        this.g_shields    = this.g.append ('g').classed ('layer shields', true);

        // a circle to highlight a position on the path
        this.circle = this.g_highlights.append ('circle').classed ('highlight', true);

        this.svg.on ('click', function (event, d) {
            // event bubbled up from rect thru g.route to svg
            // add some useful stuff and let it bubble further up
            if (event.hikemap) {
                event.hikemap.layer = that;
            }
        });
        this.on_zoom_end ();
    },
    d3_reset () {
        this.g_lines.selectAll      ('g').remove ();
        this.g_highlights.selectAll ('g').remove ();
        this.g_shields.selectAll    ('g').remove ();
    },
    set_marker (latlng) {
        const layer = this;

        if (latlng === null) {
            layer.circle.classed ('visible', false);
        } else {
            const pt = layer.map.latLngToLayerPoint (latlng);
            layer.circle
                .attr ('cx', pt.x)
                .attr ('cy', pt.y);
            layer.circle.classed ('visible', true);
        }
    },
    update () {
        const that = this;
        that.d3_update (that.routes_in_bbox, false);
    },
    d3_update (feature_collection, has_zoomed) {
        // array of features to show

        if (process.env.NODE_ENV !== 'production') {
            if (feature_collection.type !== 'FeatureCollection') {
                console.error (`Got type '${feature_collection.type}' instead of 'FeatureCollection'.`);
            }
            console.log (`d3_update${has_zoomed ? ' (zoomed)' : ''}: data`, feature_collection.features);
        }

        const that     = this;
        const vm       = that.my_options.vm;
        const features = feature_collection.features;
        const quad     = d3.quadtree ();
        const delta    = that.my_options.step; // min. distance between shields of the same route
        const epsilon  = 50;                   // min. distance between all shields

        const selected_features = features.filter (f => f.id === vm.selected_id);

        // Make a <g> in both layers for every route that crosses the bounding
        // box

        const u_lines = that.g_lines
              .selectAll ('g.route')
              .data (features, d => d.id); // key

        const u_highlights = that.g_highlights
              .selectAll ('g.route')
              .data (selected_features, d => d.id); // key

        const u_shields = that.g_shields
              .selectAll ('g.route')
              .data (features, d => d.id); // key

        // remove routes that are no longer in view
        u_lines.exit ().each (function (d, i, nodes) {
            vm.$store.commit ('delete_route', d.id);
        });

        // remove all routes that aren't in bbox any more
        u_lines.exit ().remove ();
        u_highlights.exit ().remove ();
        u_shields.exit ().remove ();

        // remove all shields of all routes
        that.g_shields.selectAll ('use.shield').remove ();

        // append <g> for new routes in bounding box in lines layer
        const e_lines = u_lines.enter ()
              .append ('g')
              .classed ('route', true)
              .attr ('data-route-ref',   d => d.properties.tags.ref)
              .attr ('data-relation-id', d => d.id);
        e_lines.each (function (d, i, nodes) {
            tools.ensure_ref (d.properties);
            tools.ensure_osmc_symbol (d.properties, that.my_options);
        });
        e_lines.append ('path')
            .style ('stroke', d => tools.osmc_waycolor (d.properties.tags['osmc:symbol']));

        // append <g> for new routes in bounding box in highlights layer
        const e_highlights = u_highlights.enter ()
              .append ('g')
              .classed ('route', true)
              .attr ('data-route-ref',   d => d.properties.tags.ref)
              .attr ('data-relation-id', d => d.id);
        e_highlights.append ('path')
            .classed ('highlight', true)
            .on ('mousemove', function (event, d) {
                const ll = that.map.containerPointToLatLng (new L.Point (event.x, event.y));
                event.hikemarker = {
                    'latlng' : ll,
                };
            })
            .on ('mouseout', function (event, d) {
                event.hikemarker = {
                    'latlng' : null,
                };
            });

        // append <g> for new routes in bounding box in shields layer
        const e_shields = u_shields.enter ()
              .append ('g')
              .classed ('route', true)
              .attr ('data-route-ref',   d => d.properties.tags.ref)
              .attr ('data-relation-id', d => d.id)
              .on ('click', function (event, d) {
                  // set this in event, then let it bubble up
                  event.hikemap = {
                      'id'    : d.id,
                      'index' : null,
                  };
              });

        e_shields.each (function (d, i, nodes) {
            // append the <symbol> for the route
            tools.ensure_ref (d.properties);
            tools.ensure_osmc_symbol (d.properties, that.my_options);
            const [symbol, size] = tools.osmc_symbol (d.properties.tags['osmc:symbol']);
            symbol.attr ('id', `sym_${d.id}`);

            const d3g = d3.select (this);  // g.layer.shields g.route
            d3g.node ().appendChild (symbol.node ());
            l_sym.set (d3g.node (), size);
        });

        // Lazy load the geojson data.  We store the geojson data in separate
        // store because changing the joined data would update all nodes on the
        // next d3_update ().  Local data doesn't work well either because we
        // have to access it from both layers.

        const url = `${that.my_options.vm.$root.api_url}geo/altimetry/`;
        e_shields.each (function (d, i, nodes) {
            const data = {
                'route' : tools.empty_feature_collection (),
                'pois'  : tools.empty_feature_collection (),
                'layer' : that,
            };
            data.promise = d3.json (url + d.id)
                .then (function (response) {
                    if (response.type !== 'FeatureCollection') {
                        console.error (`Got type '${response.type}' instead of 'FeatureCollection'.`);
                    }
                    if (process.env.NODE_ENV !== 'production') {
                        const p = response.features[0].properties;
                        console.log (`Added route ${p.tags.ref} (${d.id}) ${p.member_role}`);
                    }
                    for (const feature of response.features) { // main, alternative, pois, ...
                        if (tools.is_feature_route (feature)) {
                            tools.ensure_ref (feature.properties);
                            tools.ensure_osmc_symbol (feature.properties, that.my_options);
                            tools.sort_lines (feature.geometry);
                            data.route.features.push (feature);
                        }
                        if (tools.is_feature_poi (feature)) {
                            data.pois.features.push (feature);
                        }
                    }
                });
            vm.$store.commit ('add_route', { 'id' : d.id, 'data' : data }); // must be done this early!
        });

        // update all paths
        e_lines.merge (u_lines).each (function (d, i, nodes) {
            const d3g = d3.select (this);
            const data = vm.routes[d.id];

            data.promise.then (function (response) {
                data.clipped = d3geo.geoProject (data.route, that.clip);
                d3g.select ('path')
                    .attr ('d', d => d3.geoPath (that.transform) (data.clipped));
            });
        });

        // update all highlights
        e_highlights.merge (u_highlights).each (function (d, i, nodes) {
            const d3g = d3.select (this);
            const data = vm.routes[d.id];

            data.promise.then (function (response) {
                data.clipped = d3geo.geoProject (data.route, that.clip);
                d3g.select ('path')
                    .attr ('d', d => d3.geoPath (that.transform) (data.clipped));
            });
        });

        // update all shields
        e_shields.merge (u_shields).each (function (d, i, nodes) {
            const d3g  = d3.select (this);  // g.route
            const data = vm.routes[d.id];

            data.promise.then (function (response) {
                const size = l_sym.get (d3g.node ());
                const ref_quad = d3.quadtree ();
                let lx = 0, ly = 0;  // last point

                const shield_stream = {
                    lineStart (x, y) {
                    },
                    lineEnd (x, y) {
                    },
                    point (x, y, z) {
                        ({ x, y } = that.map.latLngToLayerPoint (new L.LatLng (y, x)));

                        if (x === lx && y === ly) {
                            // projects to the same pixel as the last one
                            return;
                        }
                        lx = x; ly = y;

                        if (ref_quad.find (x, y, delta)) {
                            // not far enough from the last shield of the same route
                            return;
                        }
                        if (quad.find (x, y, epsilon)) {
                            // not far enough from other shields
                            return;
                        }

                        // place looks good
                        const g = d3g.append ('use')
                              .classed ('shield', true)
                              .attr ('href', `#sym_${d.id}`)
                              .attr ('width',  size.width)
                              .attr ('height', size.height)
                              .attr (
                                  'transform',
                                  `translate(${x - size.width / 2},${y - size.height / 2})`
                              );
                        quad.add ([x, y]);     // mark this place
                        ref_quad.add ([x, y]);
                    },
                };
                d3.geoStream (data.clipped, shield_stream);

            }).catch (function (error) { // promise
                console.error (error);
            });
        });
    },
})

L.Control.Info_Pane = L.Control.extend ({
    onAdd (map) {
	    this._div = L.DomUtil.create ('div', 'info-pane-control');
        L.DomEvent.disableClickPropagation (this._div);
        L.DomEvent.disableScrollPropagation (this._div);
	    d3.select (this._div).append ('div').classed ('info-panels');
	    return this._div;
    },

    onRemove (map) {
	},
});

export default {
    'props' : {
        'marker'   : L.LatLng,
    },
    'data'  : function () {
        return {
            'layer'          : null,  // our custom map layer
            'geo_data'       : null,
            'layer_infos'    : [],
            'base_layers'    : {},
            'overlay_layers' : {},
        };
    },
    'computed' : {
        ... mapGetters ([
            'layers_shown',
            'geo_layers',
            'tile_layers',
            'wms_layers',
            'routes',
            'selected_id',
            'selected',
        ])
    },
    'watch' : {
        'tile_layers' : function (new_val) {
            this.init_layers (new_val);
        },
        'selected_id' : function (new_val, old_val) {
            const vm = this;
            if (new_val) {
                vm.routes[new_val].layer.update ();
            } else {
                if (old_val) {
                    // turn off previous selection
                    vm.routes[old_val].layer.update ();
                }
            }

        },
        'marker' : function () {
            const sel = this.selected;
            if (sel) {
                sel.layer.set_marker (this.marker);
            }
        },
        $route (to, from) {
            this.set_view (to.hash);
        },
    },
    'methods' : {
        init_layers () {
            const vm = this;

            for (const layer_info of vm.tile_layers) {
                const layer = L.tileLayer (
                    layer_info.url.replace ('{api}', vm.$root.api_url),
                    {
                        'attribution' : layer_info.attribution,
                    }
                );
                if (layer_info.type === 'base') {
                    vm.base_layers[layer_info.title] = layer;
                    if (Object.keys (vm.base_layers).length === 1) {
                        layer.addTo (vm.map);
                    }
                } else {
                    vm.overlay_layers[layer_info.title] = layer;
                }
            }

            for (const layer_info of vm.wms_layers) {
                const layer = L.tileLayer.wms (
                    layer_info.url.replace ('{api}', vm.$root.api_url),
                    {
                        'layers'      : layer_info.wms_layer,
                        'attribution' : layer_info.attribution,
                    }
                );
                if (layer_info.type === 'base') {
                    vm.base_layers[layer_info.title] = layer;
                    if (Object.keys (vm.base_layers).length === 1) {
                        layer.addTo (vm.map);
                    }
                } else {
                    vm.overlay_layers[layer_info.title] = layer;
                }
            }

            for (const layer_info of vm.geo_layers) {
                const sublayers = [];
                for (const sublayer_info of layer_info.layers) {
                    const sublayer = new L.Layer_Shields (
                        null, // geojson object
                        {
                            'interactive'         : true,
                            'bubblingMouseEvents' : false,
                            'attribution'         : layer_info.attribution,
                        }
                    );
                    sublayer.setDatasource (sublayer_info.url.replace ('{api}', vm.$root.api_url));
                    const color = sublayer_info.color || layer_info.color || 'red';
                    const bg    = d3.hsl (color).brighter ();
                    sublayer.my_options = {
                        'vm'         : vm,
                        'id'         : layer_info.id,
                        'classes'    : layer_info.classes,
                        'min_zoom'   : layer_info.min_zoom,
                        'max_zoom'   : layer_info.max_zoom,
                        'step'       : sublayer_info.step  || 200,
                        'color'      : color,
                        'background' : bg,
                    };
                    sublayers.push (sublayer);
                };

                if (layer_info.type === 'overlay') {
                    // vector layers should always be overlays
                    vm.overlay_layers[layer_info.title] = new L.LayerGroup (sublayers);
                }
            }

            L.control.layers (vm.base_layers, vm.overlay_layers, { 'collapsed' : true }).addTo (vm.map);

            vm.map.options.minZoom = vm.tile_layers.min_zoom;
            vm.map.options.maxZoom = vm.tile_layers.max_zoom;

            if (!vm.set_view (this.$route.hash, true)) {
                vm.zoom_extent ();
            }
        },
        zoom_extent (json) {
            const vm = this;
            d3.json (vm.build_full_api_url ('geo/extent.json')).then (function (json) {
                const [[l, b], [r, t]] = d3.geoPath ().bounds (json);
                vm.map.fitBounds (L.latLngBounds (L.latLng (b, r), L.latLng (t, l)));
            });
        },
        pan_to_marker () {
            const vm = this;
            if (vm.marker) {
                vm.map.panTo (vm.marker);
                if (vm.selected) {
                    vm.selected.layer.set_marker (vm.marker);
                }
            }
        },
        update_attribution () {
            const ac = this.map.attributionControl;
            if (ac) {
                ac._attributions = {};
                this.map.eachLayer (function (layer) {
                    ac.addAttribution (layer.getAttribution ());
                });
            }
        },
        make_hash (ll, zoom) {
            const lat = ll.lat.toFixed (5);
            const lng = ll.lng.toFixed (5);
            return `#map=${zoom}/${lat}/${lng}`;
        },
        set_view (hash, force) {
            const re = new RegExp ('^#map=([0-9]+)/([.0-9]+)/([.0-9]+)');
            const m = re.exec (hash);
            if (m) {
                const ll = new L.LatLng (m[2], m[3]);
                const zoom = parseFloat (m[1]);
                if (force || hash != this.make_hash (ll, zoom)) {
                    this.map.setView (ll, zoom);
                }
            }
            return m;
        },
        on_move_end (event) {
            // adjust the url in the navigation bar
            // after scrolling or zooming
            const zoom  = this.map.getZoom ();
            const c     = this.map.getCenter ();
            const hash  = this.make_hash (c, zoom);

            if (hash != this.$route.hash) {
                this.$router.replace ({
                    'name' : 'map',
                    'hash' : hash,
                });
            }
        },
    },
    'mounted' : function () {
        const vm = this;

        vm.map = L.map ('map', {
            'renderer'    : L.svg (),
            'zoomControl' : false,
        });
        new L.Control.Info_Pane ({ position: 'topleft' }).addTo (vm.map);
        vm.map.on ('moveend', this.on_move_end);
        vm.map.on ('zoomend', this.on_move_end);

        vm.set_view (vm.$route.hash, true);
    },
};
</script>

<style lang="scss">
/* map.vue */
@import "~/src/css/bootstrap-custom";

#map {
    position: absolute;
    overflow: hidden;
    width: 100%;
    height: 100%;
}

.leaflet-control-layers-toggle {
	background-image: url(leaflet/dist/images/layers.png);
}

.leaflet-retina .leaflet-control-layers-toggle {
	background-image: url(leaflet/dist/images/layers-2x.png);
}

svg.hikemap {
    overflow: visible;
    background-color: transparent;

    path {
        stroke-linecap: round;
        stroke-linejoin: round;
        shape-rendering: geometricPrecision;
        pointer-events: none;
    }

    g.routes {
        path, g {
            display: none;
        }
    }

    g.lines {
        opacity: 0.2;

        path {
            stroke: var(--hikemap-color);
            stroke-width: 10px;
            fill: none;
        }
    }

    g.highlight {
        path {
            fill: none;
        }
        circle.highlight {
            stroke: yellow;
            stroke-width: 5px;
            fill: transparent;
            r: 20px;
            opacity: 0;
            pointer-events: none;
            &.visible {
                opacity: 1;
            }
        }
        path.highlight {
            stroke: yellow;
            stroke-width: 5px;
            cursor: pointer;
            pointer-events: stroke;
        }
    }

}

/* used as symbol */

g.shield {
    cursor: pointer;
    rect {
        &.rounded {
            rx: 2pt;
            ry: 2pt;
        }
    }

    text {
        dominant-baseline: middle;
        text-anchor: middle;
        font: bold 12px sans-serif;
    }
}

</style>
