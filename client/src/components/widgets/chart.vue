<template>
  <div class="vm-chart">
    <div :id="'chart-'+ id" class="chart"
         @mousemove="on_mousemove"
         @mouseout="on_mouseout">
    </div>
  </div>
</template>

<script>
 /*
  * Rool our own chart because:
  *
  * c3 doesn't support d3 v6
  * frappe doesn't have a linear x-axis.
  * chart.js is bullshit
  */

import _       from 'lodash';
import * as d3 from 'd3';

import * as tools from '../../js/tools.js';

export default {
    props: {
        'id' : {
            required: true,
            type: String,
        },
        'data' : {
            required: true,
            type: Array,
        },
        'marker' : Number,
        'height' : {
            'required' : false,
            'type'     : Number,
            'default'  : 200,
        },
        'width' : {
            'required' : false,
            'type'     : Number,
            'default'  : 250,
        },
    },
    data () {
        return {
            'margin' : {
                'left'   : 50,
                'right'  :  5,
                'top'    :  5,
                'bottom' : 20,
            },
        }
    },
    watch: {
        'data'   : function () { this.update (); },
        'marker' : function () { this.marker_style (); },
    },
    computed: {
        'w' : function () { return this.width  - this.margin.left - this.margin.right; },
        'h' : function () { return this.height - this.margin.top - this.margin.bottom; },
    },
    methods: {
        on_mousemove (event) {
            const vm = this;
            const rect = event.currentTarget.getBoundingClientRect ();
            const x = (event.clientX - rect.left) / rect.width * vm.width;

            const length = vm.x_axis.invert (x);
            let index = tools.getIndexAtLength (vm.data, length);
            if (length < 0) {
                index = 0;
            }
            if (length > vm.data[vm.data.length - 1][3]) {
                index = vm.data.length - 1;
            }
            event.hikechart = {
                'index' : index,
            };
        },
        on_mouseout (event) {
            event.hikechart = {
                'index' : null,
            };
        },
        marker_style () {
            const vm = this;
            const marker = vm.marker;
            if (marker !== null) {
                const x     = vm.x_axis (vm.data[marker][3]); // M
                const y     = vm.y_axis (vm.data[marker][2]); // Z
                const xrange = vm.x_axis.range ();
                const yrange = vm.y_axis.range ();

                vm.xline
                    .attr ('x1', x)
                    .attr ('x2', x)
                    .attr ('y1', yrange[1])
                    .attr ('y2', yrange[0])
                    .style ('display', null);
                vm.yline
                    .attr ('x1', xrange[0])
                    .attr ('x2', xrange[1])
                    .attr ('y1', y)
                    .attr ('y2', y)
                    .style ('display', null);
            } else {
                vm.xline.style ('display', 'none');
                vm.yline.style ('display', 'none');
            }
        },
        update () {
            const vm = this;
            if (vm.data.length) {
                vm.g.selectAll ('g').remove ();
                vm.g.selectAll ('path').remove ();

                // the x-axis

                vm.x_axis = d3.scaleLinear ()
                      .domain ([0, vm.data[vm.data.length - 1][3]]) // last M
                      .range ([vm.margin.left, vm.width - vm.margin.right]);
                vm.g.append ('g')
                    .attr ('transform', `translate(0,${vm.height - vm.margin.bottom})`)
                    .call (d3.axisBottom (vm.x_axis));

                // the y-axis

                vm.y_axis = d3.scaleLinear ()
                      .domain (d3.extent (vm.data, d => d[2])).nice ().clamp (true)
                    .range ([vm.height - vm.margin.bottom, vm.margin.top]);

                vm.g.append ('g')
                    .attr ('transform', `translate(${vm.margin.left},0)`)
                    .call (d3.axisLeft (vm.y_axis));

                // the data

                vm.g.append ('path')
                    .classed ('data', true)
                    .datum (vm.data)
                    .attr ('d', d3.area ()
                          .x (function (d) { return vm.x_axis (d[3]) }) // M
                          .y0 (vm.y_axis (0))
                          .y1 (function (d) { return vm.y_axis (d[2]) }) // Z
                          );

                // the crossline

                vm.xline = vm.g.append ('line')
                    .classed ('marker marker-x', true)
                    .style ('display', 'none');
                vm.yline = vm.g.append ('line')
                    .classed ('marker marker-y', true)
                    .style ('display', 'none');

                vm.svg
                    .on ('mouseover', function (event) {
                        vm.on_mousemove (event);
                    })
                    .on ('mousemove', function (event) {
                        vm.on_mousemove (event);
                    })
                    .on ('mouseout',  function (event) {
                        vm.on_mouseout (event);
                    });
            }
        },
    },
    mounted () {
        const vm = this;

        vm.svg = d3.select (`#chart-${vm.id}`)
            .append ('svg')
            .attr ('viewBox', [0, 0, vm.width, vm.height]);

        vm.g = vm.svg.append ('g');

        vm.update ();
    },
}
</script>

<style lang="scss">
/* chart_js.vue */

@import "~/src/css/bootstrap-custom";

div.vm-chart {
    margin-bottom: ($spacer * 0.5);

    div.chart {
        position: relative;
        path.data {
            pointer-events: none;
            stroke: var(--hikemap-color);
            fill: var(--hikemap-background);
            stroke-width: 1.5;
        }
    }
    line.marker {
        pointer-events: none;
        fill: none;
        stroke: black;
        stroke-width: 0.5;
    }
}

</style>
