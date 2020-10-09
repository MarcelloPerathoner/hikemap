<template>
  <div class="vm-shield"></div>
</template>

<script>

// Small wrapper for extrenal SVG.

import * as tools from '../../js/tools.js';

export default {
    props: {
        'osmc_symbol' : {
            required: true,
            type: String,
        },
    },
    watch: {
        'osmc_symbol' : function () {
            this.update (this.osmc_symbol);
        },
    },
    methods: {
        update (osmc_symbol) {
            const [d3svg, size] = tools.osmc_symbol (osmc_symbol, 'svg:svg');
            const svg = d3svg.node ();
            svg.setAttribute ('width',  2 * size.width);
            svg.setAttribute ('height', 2 * size.height);

            while (this.$el.firstChild) {
                this.$el.firstChild.remove ();
            }
            this.$el.appendChild (svg);
        },
    },
    mounted () {
        this.update (this.osmc_symbol);
    },
}
</script>

<style lang="scss">
/* shield.vue */

@import "~/src/css/bootstrap-custom";

div.vm-shield {
    display: inline-block;
}

</style>
