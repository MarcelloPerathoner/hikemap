<template>
<b-sidebar right no-header shadow lazy
           id="sidebar-right" class="vm-sidebar"
           width="400px"
           :no-close-on-route-change="true" v-model="is_open"
           @hidden="$emit ('hidden')">
  <template v-slot:default="{ hide }">

    <div class="px-3">

      <div class="d-flex justify-content-between py-3">
        <b-button-close @click="hide"><b-icon-x /></b-button-close>
        <div class="d-flex flex-column justify-content-center">
          <span class="role">{{ props.member_role }}</span>
        </div>
        <my-shield :osmc_symbol="props.tags ['osmc:symbol']" />
      </div>

      <p class="subtitle">{{ props.tags.name }}</p>
      <p>
        Total Length: {{ format_km (ad.length) }}<br>
        Ascent: {{ format_ele (ad.ascent) }}<br>
        Descent: {{ format_ele (-ad.descent) }}
      </p>

      <div class="my-2">
        <div class="d-flex mt-2">
          <b-button block flex-grow-1 v-b-toggle.ele>Elevation Profile</b-button>
          <b-button class="ml-2 w-25" @click="backward ^= true">
            <b-icon-caret-left /><b-icon-caret-right />
          </b-button>
        </div>
        <b-collapse id="ele" class="mt-2" role="tabpanel" visible>
          <b-card no-body>
            <div class="p-2">
              <my-chart :selected_id='selected_id' :backward="backward" :marker="marker" />
            </div>
          </b-card>
        </b-collapse>

        <b-button class="mt-2" block v-b-toggle.pois>POI</b-button>
        <b-collapse id="pois" class="mt-2" role="tabpanel" visible>
          <b-card no-body>
            <b-table-simple small striped hover>
              <b-tbody>
                <b-tr v-for="f in pois" :key="f.properties.id" class="poi"
                      @click="on_click_poi ($event, f)">
                  <b-td>
                    <img class="icon" :src="f.properties.icon" />
                  </b-td>
                  <b-td>
                    {{ localize (f.properties.tags, 'name')  }}
                  </b-td>
                  <b-td>
                    {{ format_ele (+f.properties.height) }}
                  </b-td>
                </b-tr>
                <b-tr v-if="pois.length === 0" :key="0" class="poi">
                  <b-td>There are no POIs in this route.</b-td>
                </b-tr>
              </b-tbody>
            </b-table-simple>
          </b-card>
        </b-collapse>

        <b-button class="mt-2" block v-b-toggle.osm-data>OSM Data</b-button>
        <b-collapse id="osm-data" class="mt-2" role="tabpanel">
          <b-card no-body>
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
          </b-card>
        </b-collapse>

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
import L       from 'leaflet';

import chart      from './chart.vue';
import shield     from './shield.vue';
import * as tools from '../../js/tools.js';

export default {
    'components' : {
        'my-chart'  : chart,
        'my-shield' : shield,
    },
    'props' : {
        'marker'   : L.LatLng,
    },
    'data'  : function () {
        return {
            'is_open'  : false, // v-model
            'backward' : 0, // forward or backward
            'ad'       : {},
            'pois'     : [],
        };
    },
    'computed' : {
        ... mapGetters ([
            'routes',
            'selected',
            'selected_id',
        ]),
        'props' : function () {
            const vm = this;
            return (vm.selected && vm.selected.route.features[0].properties) || {};
        },
        'table_items' : function () {
            const vm = this;
            const feature = vm.selected && vm.selected.route.features[0];
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
        'selected_id' : function () {
            const vm = this;
            vm.update ();
            vm.is_open = !!vm.selected_id;
        },
        'backward' : function () {
            const vm = this;
            vm.reverse ();
            vm.update ();
        },
    },
    'methods' : {
        update () {
            const vm = this;
            vm.ad = {};

            const geom = vm.selected && vm.selected.route.features[0].geometry;
            if (geom) {
                const coords = geom.coordinates[0];
                tools.add_m_dimension (coords);
                tools.add_poi_index (vm.selected.route, vm.selected.pois);
                vm.ad = tools.accumulate_ascent_descent (coords);
                vm.ad.length = coords[coords.length - 1][3];
            }
            const pois = vm.selected && vm.selected.pois.features;
            if (pois) {
                vm.pois = pois
                    .filter (f => f.properties.index !== null)
                    .sort ((a, b) => a.properties.index - b.properties.index);
            }
            const chart = vm.$refs.chart;
        },
        reverse () {
            const vm = this;
            const geom = vm.selected && vm.selected.route.features[0].geometry;
            if (geom) {
                const coords = geom.coordinates[0];
                coords.reverse ();
                vm.selected.pois.features.reverse ();
            }
        },
        on_click_poi (event, feature) {
            const geom = feature.geometry;
            let latlng = null;
            if (geom.type === 'Point') {
                latlng = L.latLng (geom.coordinates[1], geom.coordinates[0]);
            }
            if (geom.type === 'LineString') {
                const pt = d3.geoCentroid (geom);
                latlng = L.latLng (pt[1], pt[0]);
            }
            event.hikechart = {
                'index'  : feature.properties.index,
                'latlng' : latlng,
            };
        },
        localize   : tools.localize,
        format_km  : tools.format_km,
        format_ele : tools.format_ele,
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
    tr.poi {
        cursor: pointer;
    }
    img.icon {
        height: 1em;
        vertical-align: baseline;
    }
    div.card table {
        margin-bottom: 0;
    }
}

</style>
