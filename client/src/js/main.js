/** @module client/main */

/**
 * Main entry point.
 *
 * @file
 *
 * @author Marcello Perathoner
 */

// import { createApp } from 'vue' // Vue3
import Vue           from 'vue'
import VueRouter     from 'vue-router';
import Vuex          from 'vuex';
import { BootstrapVue, BootstrapVueIcons } from 'bootstrap-vue';

import axios         from 'axios';

// const app = createApp (my_app); // Vue3
const app = Vue;

app.use (VueRouter);
app.use (Vuex);
app.use (BootstrapVue);
app.use (BootstrapVueIcons);

import my_app from '../components/app.vue';

/** @class Vue */

const store = new Vuex.Store ({
    'state' : {
        'layers_shown' : [],                 // geo layers shown
        'geo_layers'   : { 'layers' : [] },  // geo layers available
        'tile_layers'  : { 'layers' : [] },  // tile layers
        'wms_layers'   : { 'layers' : [] },  // wms layers
        'routes'       : {}, // cached route data: dictionary of FeatureCollections
        'selected_id'  : null,
    },
    'mutations' : {
        toolbar_layers_shown (state, data) {
            state.layers_shown = data.layers_shown;
        },
        add_route (state, o) {
            state.routes[o.id] = o.data;
        },
        delete_route (state, id) {
            delete state.routes[id];
        },
        select_route (state, id) {
            state.selected_id = id;
        },
    },
    'getters' : {
        'xhr_params' : state => ({
        }),
        'layers_shown' : state => state.layers_shown,
        'geo_layers'   : state => state.geo_layers,
        'tile_layers'  : state => state.tile_layers,
        'wms_layers'   : state => state.wms_layers,
        'routes'       : state => state.routes,
        'selected_id'  : state => state.selected_id,
        'selected'     : state => state.routes[state.selected_id] || null,
    },
});

/**
 * Ascend the VM tree until you find an api_url and use it as prefix to build
 * the full API url.
 *
 * @param {Object} vm  - The Vue instance
 * @param {String} url - Url suffix
 *
 * @returns {String} Full API url
 */

app.prototype.build_full_api_url = function (url) {
    let vm = this;
    /* eslint-disable-next-line no-constant-condition */
    while (true) {
        if (vm.api_url) {
            return vm.api_url + url;
        }
        if (!vm.$parent) {
            break;
        }
        vm = vm.$parent;
    }
    return url;
};

/**
 * Make a GET request to the API server.
 *
 * @param {String} url  - Url suffix
 * @param {Object} data - Params for axios call
 *
 * @returns {Promise}
 */

app.prototype.get = function (url, data = {}) {
    return axios.get (this.build_full_api_url (url), data);
};

app.prototype.post = function (url, data = {}) {
    return axios.post (this.build_full_api_url (url), data);
};

app.prototype.put = function (url, data = {}) {
    return axios.put (this.build_full_api_url (url), data);
};


/**
 * Trigger a native event.
 *
 * vue.js custom `events´ do not bubble, so they are useless.  Trigger a real
 * event that bubbles and can be caught by vue.js.
 *
 * @param {string} name - event name
 * @param {array}  data - data
 */

app.prototype.$trigger = function (name, data) {
    const event = new CustomEvent (name, {
        'bubbles' : true,
        'detail'  : { 'data' : data },
    });
    this.$el.dispatchEvent (event);
};

my_app.store = store;
// app.mount ('#app'); // Vue3
new app (my_app);
