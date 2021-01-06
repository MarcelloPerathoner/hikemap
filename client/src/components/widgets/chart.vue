<template>
<svg class="vm-chart"
     :viewBox="`${viewbox.left}, ${viewbox.top}, ${viewbox.right - viewbox.left}, ${viewbox.bottom - viewbox.top}`"
     @mouseover="on_mousemove"
     @mousemove="on_mousemove"
     @mouseout="on_mouseout"
     @click="on_click">
  <g class="graph" />
  <g v-if="marker_visible" class="crosshairs">
    <line class="marker marker-x"
          :x1="marker_x"
          :x2="marker_x"
          :y1="yrange[1]"
          :y2="yrange[0]"
          />
    <line class="marker marker-y"
          :x1="xrange[0]"
          :x2="xrange[1]"
          :y1="marker_y"
          :y2="marker_y" />
  </g>
</svg>
</template>

<script>
 /*
  * Roll our own chart because:
  *
  * c3 doesn't support d3 v6,
  * frappe doesn't have a linear x-axis,
  * and chart.js is bullshit.
  */

import { mapGetters } from 'vuex'

import _       from 'lodash';
import * as d3 from 'd3';
import L       from 'leaflet';

import * as tools from '../../js/tools.js';


export default {
    props: {
        'selected_id' : String,
        'marker'      : L.LatLng,
        'backward'    : Number,

        // the inner height (the height of y-axis)
        // the whole widget will be adding margins + padding for the POI text
        'height' : {
            'required' : false,
            'type'     : Number,
            'default'  : 250,
        },
        'width' : {
            'required' : false,
            'type'     : Number,
            'default'  : 250,
        },
    },
    data () {
        return {
            'viewbox' : {
                'left'   :  0,
                'right'  :  0,
                'top'    :  0,
                'bottom' :  0,
            },
            'padding' : { // padding around d3.area
                'left'   :  7,
                'right'  :  5,
                'top'    :  5,
                'bottom' :  5,
            },
            'marker_x' : 0,
            'marker_y' : 0,
            'xrange'   : [],
            'yrange'   : [],
            'marker_visible' : false,
        }
    },
    'computed' : {
        ... mapGetters ([
            'selected',
        ]),
    },
    'watch' : {
        'selected_id' : function () { this.update (); },
        'backward'    : function () { this.update (); },
        'marker'      : function () { this.update_marker (); },
    },
    'methods' : {
        on_click (event) {
            event.hikechart = this.get_event_index_latlng (event);
        },
        on_mousemove (event) {
            event.hikechart = this.get_event_index_latlng (event);
        },
        on_mouseout (event) {
            event.hikechart = {
                'index'  : null,
                'latlng' : null,
            };
        },
        get_event_index_latlng (event) {
            const vm = this;
            const rect = event.currentTarget.getBoundingClientRect ();
            const vb = vm.viewbox;
            const x = ((event.clientX - rect.left) / rect.width * (vb.right - vb.left)) + vb.left;
            const length = vm.x_scale.invert (x);

            const geom = vm.selected && vm.selected.route.features[0].geometry;
            if (geom) {
                const coords = geom.coordinates[0];

                let index = tools.getIndexAtLength (coords, length);
                if (length < 0) {
                    index = 0;
                }
                if (length > coords[coords.length - 1][3]) {
                    index = coords.length - 1;
                }
                return {
                    'index'  : index,
                    'latlng' : new L.latLng (coords[index][1], coords[index][0]),
                };
            }
            return {
                'index'  : null,
                'latlng' : null,
            };
        },
        update_marker () {
            const vm = this;
            if (vm.selected && vm.marker !== null) {
                const geom = vm.selected && vm.selected.route.features[0].geometry;
                if (geom) {
                    const index = tools.getIndexAtPoint (geom, vm.marker);
                    if (index !== null) {
                        const coords = geom.coordinates[0];
                        vm.xrange   = vm.x_scale.range ();
                        vm.yrange   = vm.y_scale.range ();
                        vm.marker_x = vm.x_scale (coords[index][3]), // M
                        vm.marker_y = vm.y_scale (coords[index][2]); // Z
                        vm.marker_visible = true;
                    }
                }
            } else {
                vm.marker_visible = false;
            }
        },
        update () {
            const vm = this;
            if (vm.selected) {
                vm.g.selectAll ('g').remove ();
                vm.g.selectAll ('path').remove ();
                vm.g.selectAll ('.marker').remove ();
                vm.g.selectAll ('.poi').remove ();

                for (const feature of vm.selected.route.features) {
                    const geom = feature.geometry;
                    if (geom) {
                        const coords = geom.coordinates[0];

                        // the y-axis

                        vm.y_scale = d3.scaleLinear ()
                            .domain (d3.extent (coords, d => d[2])).nice ().clamp (true)
                            .range ([0, -vm.height]);

                        vm.g.append ('g')
                            .classed ('axis axis-y', true)
                            .attr ('transform', `translate(${-vm.padding.left}, 0)`)
                            .call (d3.axisLeft (vm.y_scale));

                        // the x-axis

                        vm.x_scale = d3.scaleLinear ()
                            .domain ([0, coords[coords.length - 1][3]]) // last M
                            .range ([0, vm.width]);
                        vm.g.append ('g')
                            .classed ('axis axis-x', true)
                            .attr ('transform', `translate(0, ${vm.padding.bottom})`)
                            .call (d3.axisBottom (vm.x_scale));

                        // the altimetry data

                        vm.g.append ('path')
                            .classed ('data', true)
                            .datum (coords)
                            .attr ('d', d3.area ()
                                  .x (function (d) { return vm.x_scale (d[3]) }) // M
                                  .y0 (vm.y_scale (0))
                                  .y1 (function (d) { return vm.y_scale (d[2]) }) // Z
                                  );
                    }
                }
                for (const feature of vm.selected.pois.features) {
                    // the POIs (vertical lines on top of mountains)
                    if (feature.properties.index !== null) {
                        const feature0 = vm.selected.route.features[0];
                        const pt = feature0.geometry.coordinates[0][feature.properties.index];
                        const x = vm.x_scale (pt[3]);
                        const y = vm.y_scale (pt[2]);

                        const sym_size     = 10; // pixel
                        const line_length  = 20; // pixel
                        const line_padding =  4; // pixel
                        const text = tools.localize (feature.properties.tags, 'name');
                        const icon = feature.properties.icon;

                        let offset = line_padding; // pixel

                        if (text || icon) {
                            vm.g.append ('line')
                                .classed ('poi', true)
                                .attr ('x1', x)
                                .attr ('x2', x)
                                .attr ('y1', y - offset)
                                .attr ('y2', y - offset - line_length);
                            offset += line_length + line_padding;
                        }
                        if (icon) {
                            vm.g.append ('image')
                                .classed ('poi', true)
                                .attr ('x', `${-sym_size / 2}px`)
                                .attr ('y', `${-sym_size}px`)
                                .attr ('width',  `${sym_size}px`)
                                .attr ('height', `${sym_size}px`)
                                .attr ('href', feature.properties.icon)
                                .attr ('transform', `translate(${x},${y - offset})`);
                            offset += sym_size + line_padding;
                        }
                        if (text) {
                            vm.g.append ('text')
                                .classed ('poi', true)
                                .text (text)
                                .attr ('transform', `translate(${x},${y - offset}) rotate(270)`);
                        }
                    }
                }

                // adjust viewbox
                const bb  = vm.g.node ().getBBox ();
                const vb  = vm.viewbox;
                vb.top    =  bb.y - vm.padding.top;
                vb.right  =  bb.x + bb.width  + vm.padding.right;
                vb.left   =  bb.x;
                vb.bottom =  bb.y + bb.height;
            }
        }
    },
    mounted () {
        const vm = this;
        vm.g = d3.select (vm.$el).select ('g.graph');
        vm.update ();
    },
}
</script>

<style lang="scss">
/* chart_js.vue */

@import "~/src/css/bootstrap-custom";

svg.vm-chart {
    path.data {
        pointer-events: none;
        stroke: var(--hikemap-color);
        fill: var(--hikemap-background);
        stroke-width: 1.5;
    }
    .poi {
        pointer-events: none;
    }
    g.tick {
        font-size: 8px;
    }
    text.poi {
        fill: black;
        font-size: 8px;
        alignment-baseline: middle;
        text-anchor: start;
    }
    image.poi {
    }
    line.poi {
        stroke: black;
        stroke-width: 0.5;
    }
    line.marker {
        pointer-events: none;
        stroke: black;
        stroke-width: 0.5;
    }
    .halo {
        text-shadow: -1px -1px white,
                     -1px  1px white,
                      1px  1px white,
                      1px -1px white;
    }
}

</style>
