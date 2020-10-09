<template>
  <div id="map" @click="on_click" />
  </div>
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

import * as d3  from 'd3';
import L        from 'leaflet';
import _        from 'lodash';

import * as tools from '../js/tools.js';

import 'leaflet/dist/leaflet.css';

const l_pos  = d3.local ();  // position
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

        this.defs = this.svg.append ('defs');

        this.project = (ll) => {
            return map.latLngToLayerPoint (ll);
        }

        this.unproject = (pt) => {
            return map.layerPointToLatLng (pt);
        }

        function projectPoint (x, y) {
            const point = map.latLngToLayerPoint (new L.LatLng (y, x));
            this.stream.point (point.x, point.y);
        }

        this.transform = d3.geoTransform ({ 'point' : projectPoint });
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

            d3.json (url) // get routes
                .then (function (json) {
                    that.d3_update (json.features.map (f => {
                        tools.ensure_ref (f.properties);
                        tools.ensure_osmc_symbol (f.properties, that.my_options);
                        return f;
                    }), has_zoomed);
                });
        } else {
            that.d3_update ([], has_zoomed);
        }
    },
    getAttribution () {
        return this.options.attribution;
    },
    setAttribution (attribution) {
        return this.options.attribution = attribution;
    },
    on_zoom_end (event) {
        if (process.env.NODE_ENV !== 'production') {
            console.log ('on_zoom_end', event);
        }
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

L.Layer_Shields = L.D3_geoJSON.extend ({
    // a shield layer
    onAdd (map) {
        const that = this;

        L.D3_geoJSON.prototype.onAdd.call (this, map);
        this.svg.style ('z-index', 1000);

        this.g_lines     = this.g.append ('g').classed ('layer lines',   true);
        this.g_highlight = this.g.append ('g').classed ('highlight',     true);
        this.g_shields   = this.g.append ('g').classed ('layer shields', true);

        // a circle to highlight a position on the path
        this.circle = this.g_highlight.append ('circle').classed ('highlight', true);

        this.store = {}; // a data store for data shared between shields and lines

        this.svg.on ('click', function (event, d) {
            // event bubbled up from rect thru g.route to svg
            // select the clicked route, deselect all other routes
            // and bubble further up
            if (event.hikemap) {
                const id = event.hikemap.features[0].id;
                that.g_lines.selectAll ('g.route')
                    .classed ('selected', d => d.id === id);

                event.hikemap.g_lines     = that.g_lines;
                event.hikemap.g_highlight = that.g_highlight;
                event.hikemap.g_shields   = that.g_shields;
                event.hikemap.circle      = that.circle;

                event.hikemap.unselect = () => {
                    that.g_lines.selectAll ('g.route')
                        .classed ('selected', false);
                };

                event.hikemap.set_marker = (index) => {
                    if (index === null) {
                        that.circle.classed ('active', false);
                    } else {
                        const geom = event.hikemap.features[0].geometry;
                        const pt   = geom.coordinates[index];
                        const pt2  = that.project (new L.LatLng (pt[1], pt[0]));
                        that.circle
                            .attr ('cx', pt2.x)
                            .attr ('cy', pt2.y);
                        that.circle.classed ('active', true);
                    }
                }
            }
        });
        this.on_zoom_end ();
    },
    d3_reset () {
        this.g_lines.selectAll     ('g').remove ();
        this.g_highlight.selectAll ('g').remove ();
        this.g_shields.selectAll   ('g').remove ();
    },
    d3_update (features, has_zoomed) {
        // array of features to show

        if (process.env.NODE_ENV !== 'production') {
            console.log (`d3_update${has_zoomed ? ' (zoomed)' : ''}: data`, features);
        }
        const that    = this;
        const quad    = d3.quadtree ();
        const step    = that.my_options.step;
        const epsilon = step / 10;

        // Make a <g> for every route that crosses the bounding box
        // Nested selection see: https://bost.ocks.org/mike/nest/

        const u = that.g
              .selectAll ('g.layer')
              .data ([features, features]) // matrix
              .selectAll ('g.route')
              .data (d => d, d => d.id); // key

        // remove routes that are no longer in view
        u.exit ().each (function (d, i, nodes) {
            if (process.env.NODE_ENV !== 'production') {
                const p = d.properties;
                console.log (`Dropped route ${p.tags ? p.tags.ref : ''} (${d.id})`);
            };
            delete that.store[d.id];
        });
        u.exit ().remove ();  // routes that aren't in bbox any more

        if (has_zoomed) {
            // remove shields from still existing routes too
            that.g_shields.selectAll ('use.shield').remove ();
        }
        // put still extant shields into quadtree
        that.g_shields.selectAll ('use.shield').each (function (d, i) {
            const pt = l_pos.get (this);
            quad.add ([pt.x, pt.y]);
        });

        // append <g> for new routes in bounding box
        // appends in both layers !
        const e = u.enter ()
              .append ('g')
              .classed ('route', true)
              .attr ('data-route-ref',   d => d.properties.tags.ref)
              .attr ('data-relation-id', d => d.id);

        e.each (function (d, i, nodes) {
            const layer = this.parentNode.classList.contains ('lines') ? 0 : 1;
            const d3g = d3.select (this);  // g.route

            if (layer === 0) {  // path layer
                d3g.append ('path')
                    .on ('mousemove', function (event, d) {
                        const ll = that.map.containerPointToLatLng (new L.Point (event.x, event.y));
                        event.hikemarker = {
                            'index' : tools.getIndexAtPoint (
                                that.store[d.id].response.features[0].geometry.coordinates, ll),
                            'g_shields_g_route' : d3.select (this),
                        };
                    })
                    .on ('mouseout', function (event, d) {
                        event.hikemarker = {
                            'index' : null,
                            'g_shields_g_route' : d3.select (this),
                        };
                    });
            }
            if (layer === 1) {  // shield layer
                const [symbol, size] = tools.osmc_symbol (d.properties.tags['osmc:symbol']);
                symbol.attr ('id', `sym_${d.id}`);
                d3g.node ().appendChild (symbol.node ());
                l_sym.set (d3g.node (), size);

                d3g.on ('click', function (event, d) {
                    // set this in event, then let it bubble up

                    event.hikemap = that.store[d.id].response;
                    event.hikemap.index = null;
                    event.g_shields_g_route = d3g;
                });
            }

            // Lazy load the geojson data.  We store the geojson data in separate
            // store because changing the joined data would update all nodes on the
            // next d3_update ().
            const url = `${that.my_options.vm.$root.api_url}geo/altimetry/`;

            that.store[d.id] = {
                'promise' : d3.json (url + d.id),
            };
            if (process.env.NODE_ENV !== 'production') {
                const p = d.properties;
                console.log (`Loaded route ${p.tags.ref} (${d.id})`);
            }
        });

        (has_zoomed ? e.merge (u) : e).each (function (d, i, nodes) {
            const that_route = this;
            const d3g  = d3.select (this);  // g.route
            const layer = this.parentNode.classList.contains ('lines') ? 0 : 1;
            const data = that.store[d.id];

            data.promise.then (function (response) {
                const feature = response.features[0];
                tools.ensure_ref (feature.properties);
                tools.ensure_osmc_symbol (feature.properties, that.my_options);

                if (layer === 0) {
                    const path = d3g.select ('path');
                    path.attr ('d', d => {
                        // smooth the path
                        const context = d3.path ();
                        const curve = d3.curveCardinal.tension (0.5) (context);
                        curve.lineStart ();
                        d3.geoPath (that.transform, tools.curveContext (curve)) (response);
                        curve.lineEnd ();
                        return context;
                    });
                }
                if (layer === 1) {
                    data.response = response;

                    try {
                        feature.geometry = tools.stitch (feature.geometry);
                        tools.add_m_dimension (feature.geometry.coordinates);
                    } catch (e) {
                        if (process.env.NODE_ENV !== 'production') {
                            const p = d.properties;
                            console.warn (`${e} in route ${p.tags.ref} (${d.id})`);
                        }
                        return;
                    }

                    const coords = feature.geometry.coordinates.map (pt => {
                        return that.project (new L.LatLng (pt[1], pt[0]));
                    });

                    let l = step / 2; // the target length for the next shield
                    let s = 0;        // the current length along the path

                    const z = _.zip (coords.slice (0, -1), coords.slice (1));
                    for (const [p1, p2] of z) {
                        s += Math.sqrt ((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2);
                        if (s > l) {
                            if (quad.find (p2.x, p2.y, 1.5 * epsilon) !== undefined) {
                                // place is occupied, try again just a little bit further along the path
                                l += epsilon;
                                continue;
                            }

                            // place is free to squat
                            const size = l_sym.get (d3g.node ());
                            if (size) {
                                const g = d3g.append ('use')
                                      .classed ('shield', true)
                                      .attr ('href', `#sym_${d.id}`)
                                      .attr ('width',  size.width)
                                      .attr ('height', size.height)
                                      .attr (
                                          'transform',
                                          `translate(${p2.x - size.width / 2},${p2.y - size.height / 2})`
                                      );
                                l_pos.set (g.node (), p2);
                                quad.add ([p2.x, p2.y]); // mark place as occupied
                            }
                            l += step; // place the next shield a good distance further along
                        }
                    }
                }
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
        'selected' : Object,
        'marker'   : Number,
    },
    'data'  : function () {
        return {
            'geo_data'       : null,
            'layer_infos'    : [],
            'base_layers'    : {},
            'overlay_layers' : {},
        };
    },
    'computed' : {
        ... mapGetters ([
            'xhr_params',
            'layers_shown',
            'geo_layers',
            'tile_layers',
            'wms_layers',
        ])
    },
    'watch' : {
        'xhr_params' : function () {
        },
        'tile_layers' : function (new_val) {
            this.init_layers (new_val);
        },
        'selected' : function () {
            this.on_selected ();
        },
        'marker' : function () {
            const sel = this.selected;
            if (sel) {
                sel.set_marker (this.marker);
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
                    sublayer.my_options = {
                        'vm'       : vm,
                        'id'       : layer_info.id,
                        'classes'  : layer_info.classes,
                        'min_zoom' : layer_info.min_zoom,
                        'max_zoom' : layer_info.max_zoom,
                        'step'     : sublayer_info.step  || 200,
                        'color'    : sublayer_info.color || layer_info.color || 'red',
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
        on_click (event) {
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
        on_selected () {
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
            stroke-linecap: round;
            stroke-linejoin: round;
            shape-rendering: geometricPrecision;
            pointer-events: none;
        }

        g.route.selected path {
            stroke-width: 20px;
            cursor: pointer;
            pointer-events: stroke;
        }
    }

    g.highlight {
        circle.highlight {
            stroke: var(--hikemap-color);
            stroke-width: 5px;
            fill: transparent;
            r: 20px;
            opacity: 0;
            pointer-events: none;
            &.active {
                opacity: 1;
            }
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
