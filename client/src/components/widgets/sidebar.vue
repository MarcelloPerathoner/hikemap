<template>
  <b-sidebar right shadow lazy
             id="sidebar-right" class="vm-sidebar" :title="title"
             :no-close-on-route-change="true" v-model="is_open"
             @hidden="$emit ('hidden')">
    <div class="px-3 py-2">
      <h3>Height Profile</h3>

      <my-chart :data='chart_data' :height='250' @chart="on_chart" />

      <p>Length: {{ format_km () }}</p>

      <h3 class="mt-3">Route Data</h3>

      <b-table small :items="table_items"></b-table>
    </div>
  </b-sidebar>
</template>

<script>
/**
 * This module implements the sidebar with route info.
 *
 * @component sidebar
 * @author Marcello Perathoner
 */

import { mapGetters } from 'vuex'

import * as d3 from 'd3';
import chart   from './chart_js.vue';

export default {
    'components' : {
        'my-chart' : chart,
    },
    'props' : {
        'feature' : {
            'type' : Object,
        },
    },
    'data'  : function () {
        return {
            'chart_data' : [],
            'length'     : 0,     // the length of the route in km
            'is_open'    : false, // v-model
        };
    },
    'computed' : {
        'title' : function () {
            const props = this.feature && this.feature.properties;
            if (props) {
                return props.tags.ref;
            }
            return '';
        },
        'table_items' : function () {
            const props = this.feature && this.feature.properties;
            if (props) {
                const o = Object.entries (props.tags).map (d => {
                    return { 'tag' : d[0], 'value' : d[1] };
                });
                o.push ({ 'tag' : 'osm:id' , 'value' : props.geo_id });
                return o;
            }
            return [];
        },
    },
    'watch' : {
        'feature' : function () {
            if (this.feature) {
                this.update_chart ();
            }
            this.is_open = !!this.feature;
        }
    },
    'methods' : {
        update_chart () {
            const vm = this;
            const geom = vm.feature && vm.feature.geometry;
            if (geom) {
                vm.chart_data = geom.coordinates;
                vm.length = d3.geoLength (geom) * 6371;
            } else {
                vm.chart_data = {};
                vm.length = 0;
            }
        },
        format_km (data) {
            if (this.length) {
                return this.length.toFixed (1) + ' km';
            }
            return '';
        },
        on_chart (highlight) {
            this.feature.highlight = highlight;
        }
    },
};
</script>

<style lang="scss">
/* maps.vue */
@import "~/src/css/bootstrap-custom";

.vm-sidebar {
}

</style>
