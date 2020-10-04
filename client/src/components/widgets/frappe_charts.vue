<template>
  <div class="vm-frappe-charts"></div>
</template>

<script>
// import frappe from "frappe-charts";
import { Chart } from "frappe-charts/dist/frappe-charts.min.esm";

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
            'options' : {
                data   : {},
                type   : 'line',
                height : this.height,
                colors : ['red'],
                lineOptions : {
                    regionFill : 1,
                    hideDots   : 1,
                    spline     : 1,
                    xIsSeries  : true,
                },
            }
        }
    },
    watch: {
        'data' : function () { this.update_chart (); },
    },
    methods: {
        cook (data) {
            return {
                data.map (d => {
                    return { key: d[0], value: d[1] };
                });
            };
        },
        update_chart () {
            this.options.data = this.cook (this.data);
            this.chart.update (this.options.data);
        },
    },
    mounted () {
        this.options.data = this.cook (this.data);
        this.chart = new Chart (this.$el, this.options)
    },
}
</script>

<style lang="scss">
/* frappe_charts.vue */

@import "~frappe-charts/dist/frappe-charts.min.css";
</style>
