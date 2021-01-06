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

import VueRouter     from 'vue-router';
import { BootstrapVue, BootstrapVueIcons } from 'bootstrap-vue';

import _            from 'lodash';
import * as d3      from 'd3';
import url          from 'url';

import maps         from './maps.vue';

const routes = [
    {
        'path'      : '/',
        'name'      : 'map',
        'component' : maps,
    },
];

const router = new VueRouter ({
    'mode'   : 'history',
    'routes' : routes,
});

export default {
    'router' : router,
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
            d3.json (vm.build_full_api_url ('info/'),  { 'credentials' : 'include' }),
        ];
        Promise.all (xhrs).then (function (responses) {
            const [json_info] = responses;
            vm.$store.state.geo_layers  = json_info.geo_layers;
            vm.$store.state.wms_layers  = json_info.wms_layers;
            vm.$store.state.tile_layers = json_info.tile_layers; // last! triggers map.vue.init_layers
        });
    },
};

</script>

<style lang="scss">
@import "~/src/css/bootstrap-custom";

/* bootstrap */
@import '~bootstrap';
@import '~bootstrap-vue/src/index';

/* List of icons at: http://astronautweb.co/snippet/font-awesome/ */
/* Fontawesome Font */

$fa-font-path:    '~@fortawesome/fontawesome-free/webfonts';
$fa-font-display: 'block';

/*!
 * Font Awesome Free 5.14.0 by @fontawesome - https://fontawesome.com
 * License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License)
 */

@font-face {
    font-family: 'Font Awesome 5 Free';
    font-style: normal;
    font-weight: 900;
    font-display: $fa-font-display;
    src: url('#{$fa-font-path}/fa-solid-900.woff2') format('woff2'),
        url('#{$fa-font-path}/fa-solid-900.woff') format('woff'),
        url('#{$fa-font-path}/fa-solid-900.ttf') format('truetype');
}

.fa,
%fa,
.fas,
%fas {
    font-family: 'Font Awesome 5 Free';
    font-weight: 900;
}

/*!
 * Font Awesome Free 5.14.0 by @fontawesome - https://fontawesome.com
 * License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License)
 */

@font-face {
    font-family: 'Font Awesome 5 Free';
    font-style: normal;
    font-weight: 400;
    font-display: $fa-font-display;
    src: url('#{$fa-font-path}/fa-regular-400.woff2') format('woff2'),
        url('#{$fa-font-path}/fa-regular-400.woff') format('woff'),
        url('#{$fa-font-path}/fa-regular-400.ttf') format('truetype');
}

.far,
%far {
    font-family: 'Font Awesome 5 Free';
    font-weight: 400;
}

</style>
