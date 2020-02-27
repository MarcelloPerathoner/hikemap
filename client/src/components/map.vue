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
 */

import { mapGetters } from 'vuex'

import $        from 'jquery';
import * as d3  from 'd3';
import L        from 'leaflet';
import _        from 'lodash';

import options  from 'toolbar_options.js';

import '../../node_modules/leaflet/dist/leaflet.css';

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
              .classed (this.options.class, true);

        this.g = this.svg.append ('g')
            .classed ('leaflet-zoom-hide', true)
            .on ('mousedown', function (d) {
                that.last_pos = { 'x' : d3.event.x, 'y' : d3.event.y };
            })
            .on ('mouseup', function (d) {
                that.last_pos = { 'x' : 0, 'y' : 0 };
            });

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
            && (this.map.getZoom () >= this.map.getMinZoom ())
            && (this.map.getZoom () <= this.map.getMaxZoom ())) {

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
    is_dragging () {
        if (this.last_pos) {
            const dx = d3.event.x - this.last_pos.x;
            const dy = d3.event.y - this.last_pos.y;
            return Math.sqrt (dx * dx + dy * dy) > 5;
        } else {
            return true;
        }
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
            curve.lineStart ();
            curve.point (x, y);
        },
        lineTo (x, y) {
            curve.point (x, y);
        },
    };
}

L.Layer_Lines = L.D3_geoJSON.extend ({
    onAdd (map) {
        L.D3_geoJSON.prototype.onAdd.call (this, map);

        this.g_lines = this.g.append ('g').classed ('lines', true);

        this.on_zoom_end ();
    },
    d3_reset () {
        this.g_lines.selectAll ('g').remove ();
    },
    d3_update (geojson) {
        const that = this;
        const vm = this.options.vm;

        const u = that.g_lines
              .selectAll ('g')
              .data (geojson.features, d => d.properties.geo_id);

        u.exit ().remove ();

        const e = u.enter ().append ('g');

        e.append ('path')
            .classed ('hike', true)
            // .attr ('d', d3.geoPath (that.transform));
            .attr ('d', d => {
                // smooth the path
                const context = d3.path ();
                const curve = d3.curveCardinal.tension (0.5) (context);
                d3.geoPath (that.transform, curveContext (curve)) (d);
                curve.lineEnd ();
                return context;
            });

        e.each (function (d, i, nodes) {
            const d3this = d3.select (this);
            const path = d3this.select ('path');
            // d3this.selectAll ('text').remove ();
            const totlen = path.node ().getTotalLength ();
            const step = 200;
            for (let l = step; l < totlen; l += step) {
                d3this.append ('text')
                    .text (d => d.properties.route_refs)
                    // .call (wrap, 150)
                    .classed ('shield', true)
                    .attr ('transform', d => {
                        const p = path.node ().getPointAtLength (l);
                        return `translate(${p.x},${p.y})`;
                    });
            };
        });
    },
})

L.Layer_Points = L.D3_geoJSON.extend ({
    onAdd (map) {
        L.D3_geoJSON.prototype.onAdd.call (this, map);
        this.load_data ();
    },
    d3_update (geojson) {
        const that = this;
        const vm = this.options.vm;

        const t = d3.transition ()
            .duration (500)
            .ease (d3.easeLinear);

        const g = this.g.selectAll ('g').data (geojson.features, d => d.properties.geo_id);

        g.exit ().transition (t).style ('opacity', 0).remove ();

        const entered = g.enter ()
              .append ('g')
              .attr ('class', 'place')
              .style ('opacity', 0);

        entered.append ('circle')
            .attr ('class', 'count');

        entered.append ('text')
            .attr ('class', 'count');

        entered.append ('text')
            .attr ('class', 'name')
            .attr ('y', '16px')
            .text (function (d) {
                return d.properties.geo_name;
            });

        entered.on ('mouseup', function (d) {
            if (that.is_dragging ()) {
                return;
            }
            vm.$trigger ('mss-tooltip-open', d);
        });

        entered.merge (g).attr ('transform', (d) => {
            const [x, y] = d.geometry.coordinates;
            const point = this.map.latLngToLayerPoint (new L.LatLng (y, x));
            return `translate(${point.x},${point.y})`;
        }).each (function (d) {
            const g = d3.select (this);
            g.selectAll ('circle.count').transition (t).attr ('r', 10 * Math.sqrt (d.properties.count));
            g.selectAll ('text.count').text (d.properties.count);
        });

        entered.transition (t).style ('opacity', 1);
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
    'props' : {
        'toolbar' : {
            'type'     : Object,
            'required' : true,
        },
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
        ])
    },
    'watch' : {
        'xhr_params' : function () {
        },
        'tile_layers' : function (new_val) {
            this.init_layers (new_val);
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
                const layer = new L.Layer_Lines (
                    null, // geojson object
                    {
                        'class'               : 'hikemap',
                        'vm'                  : vm,
                        'interactive'         : true,
                        'bubblingMouseEvents' : false,
                        'attribution'         : layer_info.attribution,
                    }
                );
                layer.setDatasource (layer_info.url.replace ('{api}', vm.$root.api_url));
                if (layer_info.type === 'overlay') {
                    // vector layers should always be overlays
                    vm.overlay_layers[layer_info.title] = layer;
                }
            }

            L.control.layers (vm.base_layers, vm.overlay_layers, { 'collapsed' : true }).addTo (vm.map);

            vm.map.options.minZoom = vm.tile_layers.min_zoom;
            vm.map.options.maxZoom = vm.tile_layers.max_zoom;

            vm.zoom_extent ();
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
    },
    'mounted' : function () {
        const vm = this;

        vm.map = L.map ('map', {
            'renderer'    : L.svg (),
            'zoomControl' : false,
        });
        new L.Control.Info_Pane ({ position: 'topleft' }).addTo (vm.map);

        vm.$store.commit ('toolbar_layers_shown', vm.toolbar);
    },
};
</script>

<style lang="scss">
/* map.vue */
@import "bootstrap-custom";

#map {
    position: absolute;
    overflow: hidden;
    width: 100%;
    top: 55px;
    bottom: 0;
}

.leaflet-control-layers-toggle {
	background-image: url(/images/layers.png);
}

.leaflet-retina .leaflet-control-layers-toggle {
	background-image: url(/images/layers-2x.png);
}

svg {
    &.d3 {
        overflow: visible;
        pointer-events: none;

        &.areas {
            z-index: 200;
        }

        &.places {
            z-index: 400;
        }

        path {
            stroke-width: 1px;
        }

        g.areas {
            opacity: 0.5;
            path {
                cursor: pointer;
                pointer-events: all;
                stroke-width: 2px;
                stroke: $country-color;
                &:hover {
                    fill: $country-color;
                }
            }
        }

        g.labels {
            text {
                font: bold 16px sans-serif;
                text-align: center;
                fill: black;
                text-shadow: 1px 1px 0 white, 1px -1px 0 white, -1px 1px 0 white, -1px -1px 0 white;
            }
        }

        circle.count {
            stroke: white;
            stroke-width: 1.5px;
            fill-opacity: 0.5;
            pointer-events: all;
            cursor: pointer;

            fill: $place-color;
            &:hover {
                fill-opacity: .7;
            };
        }

        text {
            pointer-events: none;
            dominant-baseline: middle;
            text-anchor: middle;
            &.count {
                font: bold 16px sans-serif;
                fill: black;
                text-shadow: 1px 1px 0 white, 1px -1px 0 white, -1px 1px 0 white, -1px -1px 0 white;
            }
            &.name {
                x: 0;
                y: 24px;
                font: bold 12px sans-serif;
                fill: black;
                text-shadow: 1px 1px 0 white, 1px -1px 0 white, -1px 1px 0 white, -1px -1px 0 white;
            }
        }

        path.hike {
            stroke: red;
            fill: transparent;
            stroke-width: 2px;
        }

        text.shield {
            font: bold 12px sans-serif;
            text-align: center;
            fill: red;
            text-shadow: -2px -2px white, -2px 2px white, 2px 2px white, 2px -2px white;
        }
    }
}

</style>
