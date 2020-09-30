<template>
    <div id="map">
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

import $        from 'jquery';
import * as d3  from 'd3';
import L        from 'leaflet';
import _        from 'lodash';

import 'leaflet/dist/leaflet.css';

function add_centroids (feature_collection) {
    if (feature_collection.type == 'FeatureCollection') {
        for (const feature of feature_collection.features) {
            feature.properties.centroid = d3.geoCentroid (feature);
        }
    }
}

const colorScale = d3.scaleOrdinal (d3.schemeSet2);

function wrap (text, width) {
    // Credit: adapted from https://bl.ocks.org/mbostock/7555321
    text.each (function () {
        var text = d3.select (this),
            words = text.text ().split (/\s+/).reverse (),
            word,
            line = [],
            lineNumber = 0,
            lineHeight = 1.3, // ems
            y = text.attr ("y"),
            dy = parseFloat (text.attr ("dy") || '0');
        let tspan = text.text (null)
            .append ("tspan")
            .attr ("x", 0)
            .attr ("y", y)
            .attr ("dy", dy + "em");
        while (word = words.pop ()) {
            line.push (word);
            tspan.text (line.join (" "));
            if (tspan.node ().getComputedTextLength () > width) {
                line.pop ();
                tspan.text (line.join (" "));
                line = [word];
                tspan = text.append ("tspan")
                    .attr ("x", 0)
                    .attr ("y", y)
                    .attr ("dy", (++lineNumber * lineHeight + dy) + "em")
                    .text (word);
            }
        }
    });
}

// A Leaflet layer that uses D3 to display features.  Easily styleable with CSS.

L.D3_geoJSON = L.Layer.extend ({
    onAdd (map) {
        const that = this;

        // L.Layer.prototype.onAdd.call (this, map);
        this.map = map;

        this.svg = d3.select (this.getPane ())
              .append ('svg')
              .classed ('d3', true)
              .classed ('hikemap', true)
              .classed (this.my_options.class, true);

        this.g = this.svg.append ('g')
            .classed ('leaflet-zoom-hide', true);

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
    addData (geojson) {
        this.geojson = geojson;
        this.d3_update (this.geojson);
    },
    setDatasource (url) {
        this.url = url;
    },
    load_data () {
        const that = this;
        if (this.url
            && (this.map.getZoom () >= this.my_options.min_zoom)
            && (this.map.getZoom () <= this.my_options.max_zoom)) {

            const url = new URL (this.url);
            const bb = this.map.getBounds ();

            url.searchParams.set ('extent', `${bb.getWest ()},${bb.getSouth ()},${bb.getEast ()},${bb.getNorth ()}`);

            d3.json (url).then (function (json) {
                that.addData (json);
            });
        } else {
            that.addData ({ 'features' : [] });
        }
    },
    getAttribution () {
        return this.options.attribution;
    },
    setAttribution (attribution) {
        return this.options.attribution = attribution;
    },
    getBounds () {
        const [[l, b], [r, t]] = d3.geoPath ().bounds (this.geojson);
        return L.latLngBounds (L.latLng (b, r), L.latLng (t, l));
    },
    on_zoom_end () {
        this.d3_reset ();

        this.load_data ();
        if (this.svg) {
            this.svg.attr ('data-zoom', 'Z'.repeat (this.map.getZoom ()));
        }
    },
    on_move_end () {
        this.load_data ();
    },
    d3_reset () {
        // override this
    },
    d3_update (geojson) {
        // override this
    },
});

// A stylable Lines Layer (for hiking paths or bus lines)

function curveContext (curve) {
    // https://observablehq.com/@d3/context-to-curve
    return {
        moveTo (x, y) {
            curve.lineEnd ();
            curve.lineStart ();
            curve.point (x, y);
        },
        lineTo (x, y) {
            curve.point (x, y);
        },
    };
}

L.Layer_Shields = L.D3_geoJSON.extend ({
    // a shield layer
    onAdd (map) {
        L.D3_geoJSON.prototype.onAdd.call (this, map);
        this.svg.style ('z-index', 1000);

        this.g_shields = this.g.append ('g').classed ('shields', true);

        this.on_zoom_end ();
    },
    d3_reset () {
        this.g_shields.selectAll ('g').remove ();
    },
    d3_update (geojson) {
        const that = this;

        // for each route in this view => g
        const u = that.g_shields
              .selectAll ('g')
              .data (geojson.features, d => d.properties.geo_id);

        u.exit ().remove (); // remove old routes

        // remove all shields of remaining routes
        that.g_shields.selectAll ('g.shield').remove ();
        const quad = d3.quadtree ();

        const e = u.enter ()
              .append ('g')
              .classed ('route', true)
              .attr ('data-route-ref', d => d.properties.tags.ref);

        // we string up the shields at regular intervals along this path
        e.append ('path').classed ('shield-helper', true);

        e.merge (u).each (function (d, i, nodes) {
            const p = d.properties;

            const d3this = d3.select (this);
            const path = d3this.select ('path');
            path.attr ('d', d => d3.geoPath (that.transform) (d));

            const step    = that.my_options.step;
            const maxlen  = path.node ().getTotalLength () - step / 2;
            const epsilon = step / 10;

            let l = step / 2;  // the current length along the path

            while (l < maxlen) {
                // find a free place to squat
                const pt = path.node ().getPointAtLength (l);
                if (quad.find (pt.x, pt.y, 1.5 * epsilon) !== undefined) {
                    // place is occupied, try again just a little bit further along the path
                    l += epsilon;
                    continue;
                }

                // place is free to squat
                const g = d3this.append ('g')
                      .classed ('shield', true)
                      .attr ('transform', `translate(${pt.x},${pt.y})`);
                const rect = g.append ('rect')
                      .style ('stroke', that.my_options.color)
                      .classed ('shield', true);
                const text = g.append ('text')
                      .text (d => p.tags.ref)
                      .style ('fill', that.my_options.color)
                      .classed ('shield', true)
                      .node ();

                g.on ('click', function (event, d) {
                    // set this in event, then let it bubble up
                    event.hikemap = d.properties;
                });

                const bbox = text.getBBox ();
                rect.attr ('width',  bbox.width  + 4);
                rect.attr ('height', bbox.height + 4);
                rect.attr ('x', -bbox.width  / 2 - 2);
                rect.attr ('y', -bbox.height / 2 - 3);

                quad.add ([pt.x, pt.y]); // mark place as occupied
                l += step; // place the next shield a good distance further along
            };
        });
    },
})

L.Layer_Lines = L.D3_geoJSON.extend ({
    onAdd (map) {
        L.D3_geoJSON.prototype.onAdd.call (this, map);

        this.g_lines = this.g.append ('g').classed ('lines', true);

        this.on_zoom_end ();
    },
    d3_reset () {
        this.g_lines.selectAll ('path').remove ();
    },
    d3_update (geojson) {
        const that = this;

        const u = that.g_lines
              .selectAll ('path')
              .data (geojson.features, d => d.properties.geo_id);

        u.exit ().remove ();

        const e = u.enter ()
              .append ('path')
              .style ('stroke', that.my_options.color)
              .classed ('route', true)
              .attr ('data-route-ref', d => d.properties.tags.ref);

        e.merge (u)
            .attr ('d', d => {
                // smooth the path
                const context = d3.path ();
                const curve = d3.curveCardinal.tension (0.5) (context);
                curve.lineStart ();
                d3.geoPath (that.transform, curveContext (curve)) (d);
                curve.lineEnd ();
                return context;
            });
    },
})

L.Control.Info_Pane = L.Control.extend ({
    onAdd (map) {
	    this._div = L.DomUtil.create ('div', 'info-pane-control');
        L.DomEvent.disableClickPropagation (this._div);
        L.DomEvent.disableScrollPropagation (this._div);
	    $ (this._div).append ($ ('div.info-panels'));
	    return this._div;
    },

    onRemove (map) {
	},
});

export default {
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
        ])
    },
    'watch' : {
        'xhr_params' : function () {
        },
        'tile_layers' : function (new_val) {
            this.init_layers (new_val);
        },
        $route (to, from) {
            this.set_view (to.hash);
        },
    },
    'methods' : {
        init_layers () {
            const vm = this;

            for (const layer_info of vm.tile_layers.layers) {
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

            for (const layer_info of vm.geo_layers.layers) {
                const sublayers = [];
                for (const sublayer_info of layer_info.layers) {
                    const sublayer = (sublayer_info.type === 'shields') ?
                          new L.Layer_Shields (
                              null, // geojson object
                              {
                                  'interactive'         : true,
                                  'bubblingMouseEvents' : false,
                                  'attribution'         : layer_info.attribution,
                              }
                          ) :
                          new L.Layer_Lines (
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
                        'class'    : layer_info.classes,
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

            if (!vm.set_view (this.$route.hash)) {
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
        set_view (hash) {
            const re = new RegExp ('^#map=([0-9]+)/([.0-9]+)/([.0-9]+)');
            const m = re.exec (hash);
            if (m) {
                const ll = new L.LatLng (m[2], m[3]);
                this.map.setView (ll, parseFloat (m[1]));
            }
            return m;
        },
        on_move_end (event) {
            // adjust the url in the navigation bar
            // after scrolling or zooming
            const zoom  = this.map.getZoom ();
            const c     = this.map.getCenter ();
            const lat   = c.lat.toFixed (5);
            const lng   = c.lng.toFixed (5);
            const hash  = `#map=${zoom}/${lat}/${lng}`;

            if (hash != this.$route.hash) {
                this.$router.replace ({
                    'name' : 'map',
                    'hash' : hash,
                });
            }
            this.$emit ('move_zoom', this.map);
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

        vm.set_view (vm.$route.hash);
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

    g.lines {
        opacity: 0.2;
    }

    text {
        dominant-baseline: middle;
        text-anchor: middle;
    }

    path.shield-helper {
        stroke: transparent;
        fill: transparent;
    }

    path.route {
        fill: transparent;
        stroke-width: 20px;
        stroke-linecap: round;
        stroke-linejoin: round;
        shape-rendering: geometricPrecision;
    }

    rect.shield {
        cursor: pointer;
        fill: #eee;
        stroke-width: 1px;
        rx: 2pt;
        ry: 2pt;
    }

    text.shield {
        pointer-events: none;
        font: bold 12px sans-serif;
        text-align: center;
        fill: black;
    }
}

</style>
