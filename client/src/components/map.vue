<template>
  <div id="map" />
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

function ensure_ref (tags) {
    if (!tags.ref && tags.name) {
        const re = /\p{Lu}/gu;
        tags.ref = tags.name.match (re).join ('') || '???';
    }
}

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

function getPointAtLength (coordinates, length) {
    // find the point at distance length from the start of the linestring
    const l = length / 6371; // geoDistance returns radians

    const z = _.zip (coordinates.slice (0, -1), coordinates.slice (1));
    let s = 0;
    for (const [p1, p2] of z) {
        s += d3.geoDistance (p1, p2);
        if (s >= l) {
            return p1;
        }
    }
    return coordinates[coordinates.length -1];
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
            .classed ('d3 hikemap ' + this.my_options.classes, true)
            .style ('--hikemap-color', this.my_options.color);

        this.g = this.svg.append ('g')
            .classed ('leaflet-zoom-hide', true);

        this.project_x_y = (x, y) => {
            return map.latLngToLayerPoint (new L.LatLng (y, x));
        }

        this.project_pt = (pt) => {
            return map.latLngToLayerPoint (new L.LatLng (pt.y, pt.x));
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

            const url  = new URL (this.url);
            const url2 = `${that.my_options.vm.$root.api_url}geo/altimetry/`;
            const bb   = this.map.getBounds ();

            const params = [bb.getWest (), bb.getSouth (), bb.getEast (), bb.getNorth ()];

            url.searchParams.set ('extent', params.map (p => p.toFixed (6)).join (','));

            d3.json (url).then (function (json) {
                // the routes that intersect the bbox
                const requests = json.data.map (d => d3.json (url2 + d.geo_id));
                Promise.all (requests).then (function (responses) {
                    const features = responses.map (d => d.features[0]);
                    that.addData ({ 'features' : features });
                });
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

L.Layer_Shields = L.D3_geoJSON.extend ({
    // a shield layer
    onAdd (map) {
        const that = this;

        L.D3_geoJSON.prototype.onAdd.call (this, map);
        this.svg.style ('z-index', 1000);

        this.g_lines     = this.g.append ('g').classed ('lines',     true);
        this.g_highlight = this.g.append ('g').classed ('highlight', true);
        this.g_shields   = this.g.append ('g').classed ('shields',   true);

        // a circle to highlight a position on the path
        this.g_highlight.append ('circle').classed ('highlight', true);

        this.svg.on ('click', function (event, d) {
            // event bubbled up from rect thru g.route to svg
            // select the clicked route, deselect all other routes
            // and bubble further up
            if (event.hikemap) {
                const p = event.hikemap.properties;
                that.g_lines.selectAll ('g.selected').classed ('selected', false);
                const g = that.g_lines.select (`g.route[data-relation-id="${p.geo_id}"]`);
                g.classed ('selected', true);

                event.hikemap.unselect = () => {
                    g.classed ('selected', false);
                };
                event.hikemap.set_highlight = (length) => {
                    const highlight = Number.isFinite (length);
                    const circle = that.g_highlight.select ('circle.highlight');
                    if (highlight) {
                        const geom = event.hikemap.geometry;
                        const pt   = getPointAtLength (geom.coordinates, length);
                        const pt2  = that.project_x_y (pt[0], pt[1]);
                        circle
                            .attr ('cx', pt2.x)
                            .attr ('cy', pt2.y);
                    }
                    circle.classed ('active', highlight);
                }

                event.hikemap.g_lines_g_route = g;
                event.hikemap.g_lines     = that.g_lines;
                event.hikemap.g_highlight = that.g_highlight;
                event.hikemap.g_shields   = that.g_shields;
            }
        });
        this.on_zoom_end ();
    },
    d3_reset () {
        this.g_lines.selectAll   ('g').remove ();
        this.g_shields.selectAll ('g').remove ();
    },
    d3_update (geojson) {
        const that = this;

        // Lines (all lines must lay below shields)

        const ul = that.g_lines
              .selectAll ('g.route')
              .data (geojson.features, d => d.properties.geo_id);

        ul.exit ().remove (); // routes that aren't in bbox any more

        const el = ul.enter ()
              .append ('g')
              .classed ('route', true)
              .attr ('data-route-ref',   d => d.properties.tags.ref)
              .attr ('data-relation-id', d => d.properties.geo_id);

        // we string up the shields at regular intervals along this path
        el.append ('path');

        el.merge (ul).each (function (d, i, nodes) {
            const d3g = d3.select (this);
            const path = d3g.select ('path');

            path.attr ('d', d => {
                // smooth the path
                const context = d3.path ();
                const curve = d3.curveCardinal.tension (0.5) (context);
                curve.lineStart ();
                d3.geoPath (that.transform, curveContext (curve)) (d);
                curve.lineEnd ();
                return context;
            });
        });

        // Shields (all shields must lay above lines)

        // for each route in this view => g
        const u = that.g_shields
              .selectAll ('g.route')
              .data (geojson.features, d => d.properties.geo_id);

        u.exit ().remove (); // shields of routes that don't cross bbox any more

        const e = u.enter ()
              .append ('g')
              .classed ('route', true)
              .attr ('data-route-ref',   d => d.properties.tags.ref)
              .attr ('data-relation-id', d => d.properties.geo_id);

        e.on ('click', function (event, d) {
            // event bubbled up from shield rect to g.route.
            // note the g and bubble further up
            if (event.hikemap) {
                event.hikemap.g_shields_g_route = d3.select (this);
            }
        });

        const quad = d3.quadtree ();
        const step    = that.my_options.step;
        const epsilon = step / 10;

        e.merge (u).each (function (d, i, nodes) {
            const p = d.properties;
            ensure_ref (p.tags);

            if (d.geometry.type === 'LineString') {
                const coords = d.geometry.coordinates.map (pt => {
                    return that.project_x_y (pt[0], pt[1]);
                });

                const d3this = d3.select (this);

                // remove current shields
                d3this.selectAll ('g.shield').remove ();

                // get the path to follow from the g.lines
                const path = that.g_lines.select (`g.route[data-relation-id="${p.geo_id}"] path`);

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
                        const g = d3this.append ('g')
                              .classed ('shield', true)
                              .attr ('transform', `translate(${p2.x},${p2.y})`);
                        const rect = g.append ('rect');
                        const text = g.append ('text')
                              .text (d => p.tags.ref);

                        g.on ('click', function (event, d) {
                            // set this in event, then let it bubble up
                            event.hikemap = d;
                            event.hikemap.highlight = null;
                        });

                        const bbox = text.node ().getBBox ();
                        rect.attr ('width',  bbox.width  + 4);
                        rect.attr ('height', bbox.height + 4);
                        rect.attr ('x', -bbox.width  / 2 - 2);
                        rect.attr ('y', -bbox.height / 2 - 3);

                        quad.add ([p2.x, p2.y]); // mark place as occupied
                        l += step; // place the next shield a good distance further along
                    }
                };
            } else {
                if (process.env.NODE_ENV !== 'production') {
                    console.warn (`Error: geometry of type ${d.geometry.type} in ${p.tags.ref}`);
                }
            }
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
    'props' : {
        'selected' : Object,
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
        'selected' : function () {
            this.on_selected ();
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

        vm.set_view (vm.$route.hash);

        vm.$watch (function () {
            return vm.selected && vm.selected.highlight;
        }, function () {
            const sel = vm.selected;
            sel.set_highlight (sel.highlight);
        });
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

    text {
        dominant-baseline: middle;
        text-anchor: middle;
    }

    g.lines {
        opacity: 0.2;

        path {
            stroke: var(--hikemap-color);
            stroke-width: 10px;
            fill: transparent;
            stroke-linecap: round;
            stroke-linejoin: round;
            shape-rendering: geometricPrecision;
        }

        g.route.selected path {
            stroke-width: 20px;
        }
    }

    g.highlight {
        circle.highlight {
            stroke: var(--hikemap-color);
            stroke-width: 5px;
            fill: transparent;
            r: 20px;
            opacity: 0;
            &.active {
                opacity: 1;
            }
        }
    }

    g.shields {
    }

    g.shield {
        rect {
            stroke: var(--hikemap-color);
            fill: #eee;
            stroke-width: 1px;
            cursor: pointer;
            rx: 2pt;
            ry: 2pt;
        }

        text {
            fill: var(--hikemap-color);
            pointer-events: none;
            font: bold 12px sans-serif;
            text-align: center;
        }
    }
}

</style>
