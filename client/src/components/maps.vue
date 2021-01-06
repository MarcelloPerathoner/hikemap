<template>
  <div class="maps-vm">
    <div id="content">
      <slippy-map ref="map"
                  :marker="marker"
                  @click.native="on_click"
                  @mousemove.native="on_mousemove"
                  @mouseout.native="on_mouseout"
                  />
    </div>

    <my-sidebar v-bind:style="sidebar_style"
                :marker="marker"
                @hidden="on_sidebar_hidden"
                @click.native="on_click"
                @mousemove.native="on_mousemove"
                @mouseout.native="on_mouseout"
                />

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

import * as tools from '../js/tools.js';

const EDITORS = [
    {
        'id'    : 'iD',
        'text'  : 'Edit with iD',
        'href'  : 'https://www.openstreetmap.org/edit?editor=id{hash}',
        'local' : false,
    },
    {
        'id'    : 'Potlach2',
        'text'  : 'Edit with Potlatch 2',
        'href'  : 'https://www.openstreetmap.org/edit?editor=potlatch2{hash}',
        'local' : false,
    },
    {
        'id'    : 'JOSM',
        'text'  : 'Edit with JOSM',
        'href'  : 'http://localhost:8111/load_and_zoom?left={w}&right={e}&top={n}&bottom={s}',
        'local' : true,
    },
    {
        'id'    : 'JOSMrel',
        'text'  : 'Edit relation with JOSM',
        'href'  : 'http://localhost:8111/load_and_zoom?left={w}&right={e}&top={n}&bottom={s}&select=relation{osm_id}',
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
            'sidebar_style' : {},
            'info_panels'   : [],
            'next_id'       : 1,
            'editors'       : EDITORS,
            'marker'        : null,
        };
    },
    'computed' : {
        ... mapGetters ([
            'geo_layers',
            'tile_layers',
            'selected',
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
                // click on shield
                // event bubbled up with extra info attached
                const vm = this;
                vm.$store.commit ('select_route', event.hikemap.id);

                const feature = vm.selected.route.features[0];
                try {
                    feature.geometry = tools.stitch (feature.geometry);
                } catch (e) {
                    if (process.env.NODE_ENV !== 'production') {
                        console.warn (`${e} in route ${feature.properties.tags.ref} (${feature.id})`);
                    }
                }
                vm.sidebar_style = {
                    '--hikemap-color'      : event.hikemap.layer.my_options.color,
                    '--hikemap-background' : event.hikemap.layer.my_options.background,
                };
            }
            if (event.hikechart) {
                // click on elevation chart
                // event bubbled up with extra info attached
                const vm = this;
                vm.marker = event.hikechart.latlng;
                vm.$nextTick (() => vm.$refs.map.pan_to_marker ());
            }
        },
        on_mousemove (event) {
            if (event.hikemarker) {
                this.marker = event.hikemarker.latlng;
            }
            if (event.hikechart) {
                this.marker = event.hikechart.latlng;
            }
        },
        on_mouseout (event) {
            if (event.hikemarker) {
                this.marker = null;
            }
            if (event.hikechart) {
                this.marker = null;
            }
        },
        on_sidebar_hidden (event) {
            this.$store.commit ('select_route', null);
        },
        edit_map_with (editor_id) {
            const b = this.$refs.map.map.getBounds ();
            const params = {
                'n' : b.getNorth (),
                's' : b.getSouth (),
                'w' : b.getWest (),
                'e' : b.getEast (),
                'hash'   : this.$route.hash,
                'osm_id' : this.selected && this.selected.route.features[0].id.split ('/')[0],
            };

            for (const item of EDITORS) {
                if (item.id === editor_id) {
                    const href = tools.format (item.href, params);
                    if (item.local) {
                        axios.get (href)
                            .catch (function (error) {
                                alert ('Could not open JOSM: ' + error);
                            });
                    } else {
                        window.location = href;
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
