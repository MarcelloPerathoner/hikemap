<template>
  <nav class="toolbar-vm" @button-group-click="on_click">
    <b-button-toolbar class="justify-content-between">
      <slot></slot>
    </b-button-toolbar>
  </nav>
</template>

<script>
/**
 * This module implements the toolbar that is on most of the cards.
 *
 * Most of the functionality here resides in widgets.  See the widgets
 * subdirectory.
 *
 * @component toolbar
 *
 * @author Marcello Perathoner
 */

import $ from 'jquery';
import 'bootstrap';

export default {
    'props' : {
        'toolbar' : {
            'type'     : Object,
            'required' : true,
        },
    },
    'data' : function () {
        return {
        };
    },
    'methods' : {
        on_click (event) {
            this.toolbar[event.detail.data] ();
        },
    },
    mounted () {
        $ (this.$el).find ('.dropdown-toggle').dropdown ();
    },
};
</script>

<style lang="scss">
/* widgets/toolbar.vue */
@import "~/src/css/bootstrap-custom";

div.btn-toolbar {
    margin-bottom: $spacer * -0.5;
    margin-right: $spacer * -0.5;

    div.btn-group, div.form-group {
        margin-right: $spacer * 0.5;
        margin-bottom: $spacer * 0.5;
    }

    div.dropdown-menu {
        border: 0;
        padding: 0;
        background: transparent;
        min-width: 20rem;

        div.btn-group {
            flex-wrap: wrap;
        }

        button.btn {
            min-width: 2rem;
        }
    }

    .btn-group > .btn.active {
        z-index: 0;
    }

    label.btn.active {
        @media print {
            color: black !important;
        }
    }
}

</style>
