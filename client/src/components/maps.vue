<template>
  <div class="maps-vm">
    <div id="content">
      <slippy-map ref="map" :selected="selected" @click.native="on_click" />
    </div>

    <my-sidebar :selected="selected" @hidden="on_sidebar_hidden" />

    <header>
      <nav ref="tb" class="maps-vm-toolbar">
        <b-button-toolbar class="justify-content-between">
          <b-dropdown lazy split text="Edit" class="m-2" @click="edit_map_with ('iD')">
            <b-dropdown-item v-for="b in editors" :key="b.id"
                             @click="edit_map_with (b.id)">{{ b.text }}</b-dropdown-item>
          </b-dropdown>
        </b-button-toolbar>
      </nav>
    </header>

  </div>
</template>

<script>
/**
 * This module implements a map with some controls to query the database.
 *
 * @component maps
 * @author Marcello Perathoner
 */

import { mapGetters } from 'vuex'

import _         from 'lodash';
import axios     from 'axios';

import map      from './map.vue';
import sidebar  from './widgets/sidebar.vue';

const EDITORS = [
    {
        'id'    : 'iD',
        'text'  : 'Edit with iD',
        'href'  : 'https://www.openstreetmap.org/edit?editor=id',
        'local' : false,
    },
    {
        'id'    : 'Potlach2',
        'text'  : 'Edit with Potlatch 2',
        'href'  : 'https://www.openstreetmap.org/edit?editor=potlatch2',
        'local' : false,
    },
    {
        'id'    : 'JOSM',
        'text'  : 'Edit with JOSM',
        'href'  : 'http://localhost:8111/load_and_zoom',
        'local' : true,
    },
];

export default {
    'components' : {
        'slippy-map' : map,
        'my-sidebar' : sidebar,
    },
    'data'  : function () {
        return {
            'toolbar' : {
                'layers_shown' : ['hikemap'],
            },
            'info_panels' : [],
            'next_id'     : 1,
            'editors'     : EDITORS,
            'selected'    : null,
        };
    },
    'computed' : {
        ... mapGetters ([
            'geo_layers',
            'tile_layers',
        ])
    },
    'watch' : {
        'toolbar.layers_shown' : function () {
            this.$store.commit ('toolbar_layers_shown', this.toolbar);
        },
    },
    'methods' : {
        on_click (event) {
            if (event.hikemap) {
                this.selected = event.hikemap;
            }
        },
        on_sidebar_hidden (event) {
            this.selected.unselect ();
            this.selected = null;
        },
        edit_map_with (id) {
            for (const item of EDITORS) {
                if (item.id === id) {
                    if (item.local) {
                        const b = this.$refs.map.map.getBounds ();
                        const josm = 'http://127.0.0.1:8111/load_and_zoom';
                        const params = {
                            'left'   : b.getWest (),
                            'right'  : b.getEast (),
                            'top'    : b.getNorth (),
                            'bottom' : b.getSouth (),
                        };
                        axios.get (item.href, { 'params' : params })
                            .catch (function (error) {
                                alert ('Could not open JOSM: ' + error);
                            });
                    } else {
                        window.location = item.href + this.$route.hash;
                    }
                    break;
                }
            }
        },
    },
};
</script>

<style lang='scss'>
/* maps.vue */
@import '~/src/css/bootstrap-custom';

div.maps-vm {

    div.info-panels {
        height: 0;
        width: 30em;
    }

    nav.maps-vm-toolbar {
        position: absolute;
        top: 0;
        z-index: 10000;
        background: transparent; // $card-cap-bg;
    }

    #content {
        position: absolute;
        top: 0;
        bottom: 0;
        width: 100%;
    }

}
</style>
