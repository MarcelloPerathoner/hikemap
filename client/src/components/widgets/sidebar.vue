<template>
<b-sidebar right no-header shadow lazy
           id="sidebar-right" class="vm-sidebar"
           :no-close-on-route-change="true" v-model="is_open"
           @hidden="$emit ('hidden')">
  <template v-slot:default="{ hide }">

    <div class="px-3">

      <div class="d-flex justify-content-between py-3">
        <b-button-close @click="hide"><b-icon-x /></b-button-close>
        <div class="d-flex flex-column justify-content-center">
          <span class="role">{{ props.member_role }}</span>
        </div>
        <my-shield :osmc_symbol="osmc_symbol" />
      </div>

      <p class="subtitle">{{ props.tags.name }}</p>

      <div class="py-2">
        <my-chart id="0" :data='chart_data' :height='250' :marker="marker" />

        <div class="d-flex justify-content-between py-2">
          <p class="my-0">
            Length: {{ format_km (length) }}<br>
            Height: {{ format_ele (height) }}
          </p>
          <b-button class="reverse" variant="none" size="sm" @click="reverse">
            <b-icon-caret-left />
            <b-icon-caret-right />
          </b-button>
        </div>

        <p>
          Total Length: {{ format_km (ad.length) }}<br>
          Ascent: {{ format_ele (ad.ascent) }}<br>
          Descent: {{ format_ele (-ad.descent) }}
        </p>

        <h3 class="mt-3">Route Data</h3>

        <b-table small :items="table_items" :fields="['tag', 'value']">
          <template v-slot:cell(value)="{ item }">
            <template v-if="item.url">
              <a :href="item.url">{{ item.value }}</a>
            </template>
            <template v-else>
              {{ item.value }}
            </template>
          </template>

        </b-table>
      </div>
    </div>
  </template>
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

import chart      from './chart.vue';
import shield     from './shield.vue';
import * as tools from '../../js/tools.js';

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
            'length'     : 0,     // the current length at crosshair cursor
            'height'     : 0,     // the current height at crosshair cursor
            'is_open'    : false, // v-model
            'ad'         : {},
        };
    },
    'computed' : {
        'props' : function () {
            return (this.selected && this.selected.features[0].properties) || {};
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
                    if (d[0] === 'url' || d[0] === 'website') {
                        return { 'tag' : d[0], 'value' : d[1], 'url' : d[1] };
                    }
                    if (d[0] === 'wikidata') {
                        return { 'tag' : d[0], 'value' : d[1], 'url' : `https://www.wikidata.org/wiki/${d[1]}` };
                    }
                    if (d[0] === 'wikipedia') {
                        const m = d[1].match (/^(?:(\w+):)?\s*(.+)$/);
                        if (m) {
                            const lang = m[1] || 'en';
                            return {
                                'tag'   : d[0],
                                'value' : m[2],
                                'url'   : `https://${lang}.wikipedia.org/wiki/${m[2]}`
                            };
                        }
                    }
                    return { 'tag' : d[0], 'value' : d[1], 'url' : null };
                });
                const osm_id = feature.id.split ('/')[0];
                o.push ({
                    'tag'   : 'osm:id' ,
                    'value' : osm_id,
                    'url'   : `https://www.openstreetmap.org/relation/${osm_id}`,
                });
                return o;
            }
            return [];
        },
    },
    'watch' : {
        'selected' : function () {
            const vm = this;
            vm.update_chart ();
            vm.is_open = !!vm.selected;
        },
        'marker' : function () {
            const vm = this;
            if (vm.selected && vm.marker) {
                const geom = vm.selected.features[0].geometry;
                if (geom) {
                    vm.length = geom.coordinates[vm.marker][3]; // M
                    vm.height = geom.coordinates[vm.marker][2]; // Z
                    return;
                }
            }
            vm.height = null;
            vm.length = null;
        },
    },
    'methods' : {
        update_chart () {
            const vm = this;
            if (vm.selected) {
                const geom = vm.selected.features[0].geometry;
                if (geom) {
                    tools.add_m_dimension (geom.coordinates);
                    vm.ad = tools.accumulate_ascent_descent (geom.coordinates);
                    vm.ad.length = geom.coordinates[geom.coordinates.length - 1][3];
                    vm.chart_data = geom.coordinates;
                    return;
                }
            }
            vm.ad = {};
            vm.chart_data = [];
        },
        reverse () {
            const vm = this;
            if (vm.selected) {
                const geom = vm.selected.features[0].geometry;
                if (geom) {
                    geom.coordinates.reverse ();
                    vm.update_chart ();
                }
            }
        },
        format_km (length) {
            if (Number.isFinite (length)) {
                return length.toFixed (1) + ' km';
            }
            return '';
        },
        format_ele (height) {
            if (Number.isFinite (height)) {
                return height.toFixed (0) + ' m';
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
        font-weight: bold;
    }
    .reverse {
        color: white;
        background: var(--hikemap-background);
        border-color: var(--hikemap-color);
    }
}

</style>
