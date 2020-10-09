<template>
  <b-sidebar right shadow lazy
             id="sidebar-right" class="vm-sidebar"
             :no-close-on-route-change="true" v-model="is_open"
             @hidden="$emit ('hidden')">

    <template v-slot:title="">
      <span class="subtitle">{{ subtitle }}</span>
      <my-shield :osmc_symbol="osmc_symbol" />
    </template>

    <div class="px-3 py-2">
      <h3>Height Profile</h3>

      <my-chart id="0" :data='chart_data' :height='250' :marker="marker" />

      <p>Height: {{ format_height (height) }}</p>

      <p>Total Length: {{ format_km (length) }}</p>

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
import shield  from './shield.vue';

export default {
    'components' : {
        'my-chart'  : chart,
        'my-shield' : shield,
    },
    'props' : {
        'selected' : {
            'type' : Object,
        },
        'marker' : {
            'type' : Number,
        },
    },
    'data'  : function () {
        return {
            'chart_data' : [],
            'length'     : 0,     // the length of the route in km
            'is_open'    : false, // v-model
            'height'     : 0,
        };
    },
    'computed' : {
        'subtitle' : function () {
            const props = this.selected && this.selected.features[0].properties;
            if (props) {
                return props.tags.name;
            }
            return '';
        },
        'osmc_symbol' : function () {
            const props = this.selected && this.selected.features[0].properties;
            if (props) {
                return props.tags ['osmc:symbol'];
            }
            return '';
        },
        'table_items' : function () {
            const feature = this.selected && this.selected.features[0];
            if (feature) {
                const o = Object.entries (feature.properties.tags).map (d => {
                    return { 'tag' : d[0], 'value' : d[1] };
                });
                o.push ({ 'tag' : 'osm:id' , 'value' : feature.id });
                return o;
            }
            return [];
        },
    },
    'watch' : {
        'selected' : function () {
            if (this.selected) {
                this.update_chart ();
            }
            this.is_open = !!this.selected;
        },
        'marker' : function () {
            if (this.marker === null) {
                this.height = null;
            } else {
                if (this.selected) {
                    this.height = this.selected.features[0].geometry.coordinates[this.marker][2]; // Z
                }
            }
        },
    },
    'methods' : {
        update_chart () {
            const vm = this;
            const geom = vm.selected && vm.selected.features[0].geometry;
            if (geom) {
                vm.chart_data = geom.coordinates;
                vm.length = geom.coordinates[geom.coordinates.length - 1][3];
            } else {
                vm.chart_data = {};
                vm.length = 0;
            }
        },
        format_km (length) {
            if (Number.isFinite (length)) {
                return length.toFixed (1) + ' km';
            }
            return '';
        },
        format_height (height) {
            if (Number.isFinite (height)) {
                return height.toFixed (0);
            }
            return '';
        },
    },
};
</script>

<style lang="scss">
/* maps.vue */
@import "~/src/css/bootstrap-custom";

.vm-sidebar {
    .subtitle {
        display: inline-block;
        font-size: smaller;
        margin-right: 0.5em;
    }
}

</style>
