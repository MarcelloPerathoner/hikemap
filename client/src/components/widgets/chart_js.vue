<template>
  <div class="vm-chart-js" :style="`height: ${height}px`">
    <canvas :id="'chart-'+ id"    class="chart"></canvas>
    <div    :id="'overlay-' + id" class="overlay" :style="overlay_style"
            @mousemove="on_mousemove"
            @mouseout="on_mouseout">
      <div class="marker" :style="marker_style" />
    </div>
  </div>
</template>

<script>
import _       from 'lodash';
import Chart   from 'chart.js';

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
    },
    data () {
        return {
            'chart' : null,
        }
    },
    watch: {
        'data'   : function () { this.update (); },
    },
    computed: {
        'overlay_style' : function () {
            const vm = this;
            if (vm.chart && vm.chart.canvas) {
                const canvas = vm.chart.canvas;
                return `width: ${canvas.clientWidth}px; height: ${canvas.clientHeight}px`;
            }
            return '';
        },
        'marker_style' : function () {
            const vm = this;
            const marker = vm.marker;
            if (marker !== null) {
                const x    = vm.chart.scales.length.getPixelForValue (vm.data[marker][3]);
                const rect = vm.chart.chartArea;
                return `left: ${x}px; top: ${rect.top}px; height: ${rect.bottom - rect.top}px;`;
            } else {
                return `display: none`;
            }
        },
    },
    methods: {
        cook_for_line () {
            return {
                'labels'   : this.data.map ( d => d[0] / 1000 ),
                'datasets' : [
                    {
                        'data'            : this.data.map (d => d[1]),
                        'borderWidth'     : 1,
                        'borderColor'     : '#ff0000',
                        'backgroundColor' : '#ff0000',
                        'fill'            : 'origin',
                        'pointRadius'     : 0,
                    },
                ],
            };
        },
        cook_for_scatter (data) {
            return {
                'datasets' : [
                    {
                        'data'            : data.map (d => { return { x : d[3], y : d[2] }; } ), // XYZM
                        'borderWidth'     : 1,
                        'borderColor'     : '#ff0000',
                        'backgroundColor' : '#ff0000',
                        'fill'            : 'origin',
                        'pointRadius'     : 0,
                    },
                ],
            };
        },
        on_mousemove (event) {
            const vm = this;
            const rect = event.target.getBoundingClientRect ();
            const x = event.clientX - rect.left;
            const length = vm.chart.scales.length.getValueForPixel (x);
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
        update () {
            if (this.data.length) {
                this.chart.data = this.cook_for_scatter (this.data);
                this.chart.options.scales.xAxes[0].ticks.suggestedMax = this.data[this.data.length - 1][3];
                this.chart.update ();
            }
        },
    },
    mounted () {
        const vm = this;
        const ctx = document.getElementById ('chart-' + vm.id);

        vm.chart = new Chart (ctx, {
            type: 'line',
            data: {
                'datasets' : [{
                    'data'  : {},
                }],
            },
            options : {
                maintainAspectRatio: false,
                legend: {
                    display: false,
                },
                events: ['mousemove', 'mouseout'],
                scales: {
                    xAxes: [{
                        type: 'linear',
                        id: 'length',
                        ticks: {
                            suggestedMin :  0,
                            suggestedMax : 10,
                            precision    :  0,
                        }
                    }],
                    yAxes: [{
                        type: 'linear',
                        id: 'height',
                        ticks: {
                            precision: 0,
                        }
                    }],
                },
            },
        });

        vm.update ();
    },
}
</script>

<style lang="scss">
/* chart_js.vue */

@import "~/src/css/bootstrap-custom";

div.vm-chart-js {
    position: relative;
    margin-bottom: ($spacer * 0.5);

    canvas.chart,
    div.overlay {
        position: absolute;
        top: 0;
        left: 0;
    }
    div.marker {
        position: absolute;
        top: 0;
        left: 0;
        bottom: 0;
        border: 1px solid black;
        pointer-events: none;
    }
}

</style>
