<template>
  <router-view />
</template>

<script>
/**
 * The Vue.js application
 *
 * @component app
 * @author Marcello Perathoner
 */

import Vue          from 'vue';
import VueRouter    from 'vue-router';
import Vuex         from 'vuex';
import BootstrapVue from 'bootstrap-vue';

import _            from 'lodash';
import * as d3      from 'd3';
import url          from 'url';

import maps         from 'maps.vue';

Vue.use (VueRouter);
Vue.use (Vuex);
Vue.use (BootstrapVue);

const routes = [
    { 'path' : '/maps', 'component' : maps, },
];

const router = new VueRouter ({
    'mode'   : 'history',
    'routes' : routes,
});

const store = new Vuex.Store ({
    'state' : {
        'layers_shown' : [],                 // geo layers shown
        'geo_layers'   : { 'layers' : [] },  // geo layers available
        'tile_layers'  : { 'layers' : [] },  // tile layers
    },
    'mutations' : {
        toolbar_range (state, data) {
            _.merge (state, {
            });
        },
        toolbar_layers_shown (state, data) {
            this.state.layers_shown = data.layers_shown;
        },
    },
    'getters' : {
        'xhr_params' : state => ({
        }),
        'layers_shown' : state => state.layers_shown,
        'geo_layers'   : state => state.geo_layers,
        'tile_layers'  : state => state.tile_layers,
    },
});

export default {
    'router' : router,
    'store'  : store,
    'el': app,
    data () {
        return {
        };
    },
    'computed' : {
        api_url () { return api_base_url; },
    },
    mounted () {
        const vm = this;
        const xhrs = [
            d3.json (vm.build_full_api_url ('geo/'),  { 'credentials' : 'include' }),
            d3.json (vm.build_full_api_url ('tile/'), { 'credentials' : 'include' }),
        ];
        Promise.all (xhrs).then (function (responses) {
            const [json_geo, json_tile] = responses;
            vm.$store.state.geo_layers  = json_geo;
            vm.$store.state.tile_layers = json_tile; // last! triggers map.vue.init
        });
    },
};

</script>

<style lang="scss">
@import "bootstrap-custom";

/* bootstrap */
@import "../../node_modules/bootstrap/scss/bootstrap";
@import "../../node_modules/bootstrap-vue/dist/bootstrap-vue.css";

/* List of icons at: http://astronautweb.co/snippet/font-awesome/ */
@import "../../node_modules/@fortawesome/fontawesome-free/css/fontawesome.css";
@import "../../node_modules/@fortawesome/fontawesome-free/scss/solid.scss";

</style>
