<template>
  <canvas class="vm-chart-js" :height="height" />
</template>

<script>
import _       from 'lodash';
import * as d3 from 'd3';
import Chart   from 'chart.js';
import 'chartjs-plugin-crosshair';

export default {
    props: {
        'data' : {
            required: true,
            type: Array,
        },
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
        'data' : function () { this.update (); },
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
                        'data'            : data.map (d => { return { x : d[1], y : d[0][2] }; } ),
                        'borderWidth'     : 1,
                        'borderColor'     : '#ff0000',
                        'backgroundColor' : '#ff0000',
                        'fill'            : 'origin',
                        'pointRadius'     : 0,
                    },
                ],
            };
        },
        add_cum_distance (data) {
            // add the cumulative 2D distance along the path
            const z = _.zip (data.slice (0, -1), data.slice (1));
            let s = 0;
            return [[data[0], 0]].concat (z.map (d => {
                return [d[1], s += d3.geoDistance (d[0], d[1]) * 6371];
            }));
        },
        on_hover (event, active_elems) {
            if (event.type === 'mouseout') {
                this.$emit ('chart', null);
            }
        },
        update () {
            if (this.data.length) {
                const data = this.add_cum_distance (this.data);
                this.chart.data = this.cook_for_scatter (data);
                this.chart.options.scales.xAxes[0].ticks.suggestedMax = data[this.data.length - 1][1];
                this.chart.update ();
            }
        },
    },
    mounted () {
        const vm = this;
        const ctx = vm.$el.getContext ('2d');

        vm.chart = new Chart (ctx, {
            type: 'line',
            data: {
                'datasets' : [{
                    'data'  : {},
                }],
            },
            options : {
                legend: {
                    display: false,
                },
                events: ['mousemove', 'mouseout'],
                onHover: vm.on_hover,
                tooltips: {
                    mode: 'index',
                    axis: 'x',
                    intersect: false,
                    // Disable the on-canvas tooltip
                    enabled: false,
                    // This tooltip emits events, the argument being the
                    // distance along the route that the mouse pointer is
                    // hovering.
                    custom: function (tooltipModel) {
                        if (tooltipModel.dataPoints) {
                            const length = tooltipModel.dataPoints[0].xLabel;
                            vm.$emit ('chart', length);
                        }
                    }
                },
                plugins: {
                    crosshair: {
                        line: {
                            color: '#000',  // crosshair line color
                            width: 1        // crosshair line width
                        },
                        sync: {
                            enabled: false,
                        },
                        zoom: {
                            enabled: false,
                        },
                    },
                },
                scales: {
                    xAxes: [{
                        type: 'linear',
                        position: 'bottom',
                        ticks: {
                            precision: 0,
                        }
                    }],
                    yAxes: [{
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

div.vm-c3-charts {
    margin-bottom: ($spacer * 0.5);
}

</style>
