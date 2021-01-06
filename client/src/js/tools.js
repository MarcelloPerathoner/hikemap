/**
 * This module implements helper functions and is a container for all stuff
 * that doesn't fit elsewhere.
 *
 * @module client/tools
 * @author Marcello Perathoner
 */

import * as d3            from 'd3';
import _                  from 'lodash';
import nearestPointOnLine from '@turf/nearest-point-on-line';

// alias: openstreetmap-carto/symbols
const symbols = require.context ('osm_carto_symbols', true, /\.svg$/);

function load_symbol (path) {
    try {
        const module = symbols (path);
        if (module !== null)
            return module.default;
    } catch (e) {
    }
    return null;
}

export function get_poi_icon (feature) {
    const tags = feature.properties.tags;
    if (tags.type === 'route')
        return null;

    if (tags.place)
        return load_symbol ('./place/place-4.svg');

    if (tags.mountain_pass === 'yes')
        return load_symbol (`./natural/saddle.svg`);
    if (tags.natural)
        return load_symbol (`./natural/${tags.natural}.svg`);

    if (tags.historic)
        return load_symbol (`./historic/${tags.historic}.svg`);

    if (tags.tourism === 'alpine_hut')
        return load_symbol (`./tourism/alpinehut.svg`);
    if (tags.tourism === 'wilderness_hut')
        return load_symbol (`./tourism/wilderness_hut.svg`);

    if (tags.amenity === 'restaurant')
        return load_symbol (`./amenity/restaurant.svg`);
    if (tags.amenity === 'parking')
        return load_symbol (`./amenity/parking.svg`);

    if (tags.public_transport)
        return load_symbol ('./highway/bus_stop.12.svg');

    return null;
}

export function is_feature_poi (feature) {
    const tags = feature.properties.tags;

    if (tags.type === 'route')
        return false;

    if (tags.place || tags.natural || tags.historic || tags.public_transport)
        return true;

    if (tags.mountain_pass === 'yes' ||
        tags.tourism === 'alpine_hut' ||
        tags.tourism === 'wilderness_hut' ||
        tags.amenity === 'restaurant' ||
        tags.amenity === 'parking')
        return true;

    return false;
}

function eq (a, b) {
    return (a[0] === b[0]) && (a[1] === b[1]);
}

export function empty_feature_collection () {
    return { 'type' : 'FeatureCollection', 'features' : [] };
};

export function ensure_ref (d) {
    if (!d.tags) {
        d.tags = {};
    }
    if (!d.tags.ref) {
        if (d.tags.name) {
            let m = d.tags.name.match (/\p{Lu}/gu);
            if (m && m.length > 1) {
                d.tags.ref = m.slice (0, 3).join ('');
            } else {
                m = d.tags.name.split ();
                if (m && m.length > 1) {
                    d.tags.ref = m.slice (0, 3).map (w => w[1]).join ('');
                } else {
                    d.tags.ref = d.tags.name.substring (0, 3);
                }
            }
        }
    }
    if (!d.tags.ref) {
        d.tags.ref = '?';
    }
    return d;
}

export function localize (tags, key) {
    for (const language of navigator.languages) {
        const lang = language.split ('-')[0];
        const value = tags[`${key}:${lang}`];
        if (value) return value;
    }
    return tags[key];
}

/**
 * Format a string in python fashion.  "{count} items found"
 *
 * @function format
 *
 * @param {String} s  - The string to format
 * @param {dict} data - A dictionary of key: value
 *
 * @returns {String} The formatted string
 */

export function format (s, data) {
    return s.replace (/\{([_\w][_\w\d]*)\}/gm, (match, p1) => data[p1]);
}

export function format_km (length) {
    if (Number.isFinite (length)) {
        return length.toFixed (1) + ' km';
    }
    return '';
}

export function format_ele (height) {
    if (Number.isFinite (height)) {
        return height.toFixed (0) + ' m';
    }
    return '';
}

export function is_feature_route (feature) {
    const tags = feature.properties.tags;
    return tags.type === 'route';
}

export function curveContext (curve) {
    // https://observablehq.com/@d3/context-to-curve
    return {
        moveTo (x, y) {
            curve.lineEnd ();
            curve.lineStart ();
            curve.point (x, y);
        },
        lineTo (x, y) {
            curve.point (x, y);
        },
    };
}

export function add_m_dimension (coordinates) {
    // adds an M dimension to XYZ coordinates

    if (coordinates.length === 0) {
        return coordinates;
    }

    let m = 0;
    let last_pt = coordinates[0];

    for (const pt of coordinates) {
        m += d3.geoDistance (last_pt, pt) * 6371;
        pt[3] = m;
        last_pt = pt;
    }
    return coordinates;
}

export function accumulate_ascent_descent (coordinates) {
    // accumulate ascent and descent

    let asc  = 0;
    let desc = 0;

    if (coordinates.length > 0) {
        let last_pt = coordinates[0];

        for (const pt of coordinates) {
            const delta = pt[2] - last_pt[2];
            if (delta > 0) {
                asc += delta;
            } else {
                desc += delta;
            }
            last_pt = pt;
        }
    }
    return { 'ascent' : asc, 'descent' : desc };
}

export function add_poi_index (route, pois) {
    const feature0 = route.features[0];
    for (const feature of pois.features) {
        const p = feature.properties;
        p.index  = null;
        p.icon   = null;
        p.height = null;
        if (is_feature_poi (feature)) {
            p.icon = get_poi_icon (feature);
            const geom = feature.geometry;
            let pt = null;
            if (geom.type === 'Point') {
                pt = geom.coordinates;
            }
            if (geom.type === 'LineString') {
                pt = geom.coordinates[0]; // just pick the first point
            }
            if (pt) {
                p.height = pt[2];
                const snapped = nearestPointOnLine (feature0, pt);
                if (snapped.properties.dist < 0.1) { // in km
                    p.index = snapped.properties.index;
                    p.length = feature0.geometry.coordinates[0][p.index][3]; // M
                }
            }
        }
    }
}

export function getIndexAtLength (coordinates, length) {
    // Find index of the point at distance length from the start of the
    // linestring.  Needs coordinates with an M dimension.
    return _.sortedIndexBy (coordinates, [0, 0, 0, length], i => i[3]);
}

export function getPointAtLength (coordinates, length) {
    // Find the point at distance length from the start of the linestring.
    // Needs coordinates with an M dimension.
    return coordinates[getIndexAtLnegth (length)];
}

export function getIndexAtPoint (geom, latlng) {
    // inverse of getPointAtLength

    const p0 = [ latlng.lng, latlng.lat ]; // mouse pointer is here
    let min_distance = Infinity;           // the smallest so far
    let index = null;

    for (const [i, pt] of geom.coordinates[0].entries ()) {
        const distance = Math.sqrt (((pt[0] - p0[0]) ** 2) + ((pt[1] - p0[1]) ** 2));
        if (distance < min_distance) {
            min_distance = distance;
            index = i;
        }
    }
    return index;
}

export function getIndexAtPointTurf (geom, latlng) {
    // Find the index of the point nearest to latlng

    const pt = [ latlng.lng, latlng.lat ]; // mouse pointer is here
    const snapped = nearestPointOnLine (geom, pt);

    if (snapped.properties.dist < 0.1) { // in km
        return snapped.properties.index;
    }
    return null;
}

export function clip (geometry, bbox) {
    // clips geometry keeping only linestrings that intersect bbox

    function touches (linestring) {
        for (const pt in linestring.coordinates) {
            if (pt[0] >= bbox.left && pt[0] <= bbox.right &&
                pt[1] >= bbox.top  && pt[1] <= bbox.bottom) {
                return true
            }
        }
        return false;
    }

    if (geometry.type === 'MultiLineString') {
        return geometry.coordinates.filter (d => touches (d));
    }

    throw `Error: cannot clip geometry of type ${geometry.type}`;
}

export function sort_lines (geometry) {
    // make all linestrings in the input multilinestring
    // go in the same direction

    if (geometry.type !== 'MultiLineString') {
        return;
    }

    // just one line, no processing required
    if (geometry.coordinates.length < 2) {
        return;
    }

    let le = null;  // last way's end
    let first_way = geometry.coordinates[0]; // temp store of first way

    for (const way of geometry.coordinates.slice (1)) {
        let s = way[0];
        let e = way[way.length - 1];

        if (first_way) {
            // special treatment of first way
            // we can only do this once the second way is known
            if (eq (first_way[0], s) || eq (first_way[0], e)) {
                first_way.reverse ();
            }
            le = first_way[first_way.length - 1];
            first_way = null;
        }

        if (eq (le, s)) {
            le = way[way.length - 1];
        } else {
            if (eq (le, e)) {
                way.reverse ();
                le = way[way.length - 1];
            } else {
                // a new string of ways has started
                first_way = way;
                le = null;
            }
        }
    }
}

export function stitch (geometry) {
    // stitches the linestrings in the input multilinestring
    // into as few linestring as possible
    // Always returns a MultiLineString.
    // This is a better stitcher than ST_MakeLine because it groks
    // reversed ways.
    // This is a better stitcher than ST_LineMerge because it handles
    // duplicated ways (ways taken forward and backward).

    if (geometry.type !== 'MultiLineString') {
        return;
    }

    // just one line, no stitching required
    if (geometry.coordinates.length < 2) {
        return geometry;
    }

    sort_lines (geometry);

    const linestrings = [];
    let endpoint = [null, null];
    let linestring = null;

    for (const way of geometry.coordinates) {
        if (eq (way[0], endpoint)) {
            // stitch linestrings
            linestring = linestring.concat (way.slice (1));
        } else {
            // start another linestring
            if (linestring !== null) {
                linestrings.push (linestring.slice ()); // make a copy
            }
            endpoint = [null, null];
            linestring = way;
        }
        endpoint = way[way.length - 1];
    }

    linestrings.push (linestring.slice ());

    return {
        'type'        : 'MultiLineString',
        'coordinates' : linestrings,
    }
}

export function wrap (text, width) {
    // Credit: adapted from https://bl.ocks.org/mbostock/7555321
    text.each (function () {
        var text = d3.select (this),
            words = text.text ().split (/\s+/).reverse (),
            word,
            line = [],
            lineNumber = 0,
            lineHeight = 1.3, // ems
            y = text.attr ("y"),
            dy = parseFloat (text.attr ("dy") || '0');
        let tspan = text.text (null)
            .append ("tspan")
            .attr ("x", 0)
            .attr ("y", y)
            .attr ("dy", dy + "em");
        while (word = words.pop ()) {
            line.push (word);
            tspan.text (line.join (" "));
            if (tspan.node ().getComputedTextLength () > width) {
                line.pop ();
                tspan.text (line.join (" "));
                line = [word];
                tspan = text.append ("tspan")
                    .attr ("x", 0)
                    .attr ("y", y)
                    .attr ("dy", (++lineNumber * lineHeight + dy) + "em")
                    .text (word);
            }
        }
    });
}

export function ensure_osmc_symbol (d, layer_info) {
    if (!d.tags['osmc:symbol']) {
        d.tags['osmc:symbol'] = `${layer_info.color}:white:${layer_info.color}_frame:${d.tags.ref}:${layer_info.color}`;
    }
    return d;
}

function draw_osmc_symbol (ground, size) {
    if (!ground) return null;

    let [color, what, mode] = ground.split ('_');
    const g = d3.create ('svg:g')
          .attr ('stroke', 'none')
          .attr ('fill',   color);
    g.append ('desc').text (ground);

    if (!what) {
        what = 'rectangle';
    }
    if (what === 'frame') {
        what = 'rectangle';
        mode = 'line';
    }
    if (what === 'circle') {
        what = 'round';
        mode = 'line';
    }

    if (what === 'rectangle') {
        g.append ('rect')
            .classed ('rounded', true)
            .attr ('x', -size.width / 2)
            .attr ('y', -size.height / 2)
            .attr ('width',  size.width)
            .attr ('height', size.height);
    }

    if (what == 'bar') { // --
        g.append ('rect')
            .attr ('x', -size.width / 2)
            .attr ('y', -size.height / 2)
            .attr ('width',  size.width)
            .attr ('height', size.height);
        size.height *= 2;
    }

    if (what == 'stripe') { // |
        g.append ('rect')
            .attr ('x', -size.width / 2)
            .attr ('y', -size.height / 2)
            .attr ('width',  size.width)
            .attr ('height', size.height);
        size.width *= 2;
    }

    if (what === 'round') {
        const d = Math.max (size.width, size.height);
        g.append ('circle')
            .attr ('r', d / 2);
        size.width  = d;
        size.height = d;
    }

    if (what === 'dot') {
        const d = Math.max (size.width, size.height) / 2;
        g.append ('circle')
            .attr ('r', d / 2);
        size.width  = d;
        size.height = d;
    }

    if (what === 'triangle') {
        const r = Math.max (size.width, size.height);
        const x = r * 0.866;
        const y = r * 0.5;
        g.append ('path')
            .attr ('d', `M0,${-r}L${-x},${y}H${x}Z`);
        size.width  = 2 * x;
        size.height = 2 * r;
    }

    if (mode === 'line') {
        g   .attr ('stroke', color)
            .attr ('stroke-width', 2)
            .attr ('fill', 'transparent');
        size.width  += 2;
        size.height += 2;
    }
    return g.node ();
}

export function osmc_waycolor (osmc_symbol) {
    // Convert osmc:symbol into a way color
    //
    // @param osmc_symbol The osmc:symbol string.
    //
    // @return The way color
    //
    // osmc:symbol = waycolor:background[:foreground][[:foreground2]:text:textcolor]

    const components = osmc_symbol.split (':');
    return components.length > 1 ? components[0] : 'red';
}


export function osmc_symbol (osmc_symbol, elem = 'svg:symbol') {
    // Convert osmc:symbol into an SVG symbol
    //
    // @param osmc_symbol The osmc:symbol string.
    //
    // @return The SVG symbol element.
    //
    // osmc:symbol = waycolor:background[:foreground][[:foreground2]:text:textcolor]

    let waycolor    = null,
        background  = null,
        foreground  = null,
        foreground2 = null,
        text        = null,
        textcolor   = '#000';

    const components = osmc_symbol.split (':');
    if (components.length === 6) {
        [waycolor, background, foreground, foreground2, text, textcolor] = components;
    }
    if (components.length === 5) {
        [waycolor, background, foreground, text, textcolor] = components;
    }
    if (components.length === 4) {
        [waycolor, background, text, textcolor] = components;
    }
    if (components.length === 3) {
        [waycolor, background, foreground] = components;
    }
    if (components.length === 2) {
        [waycolor, background] = components;
    }
    if (components.length === 1) {
        [background] = components;
    }

    text = text || '';

    const sym = d3.create (elem);

    sym.append ('desc').text (osmc_symbol);

    const g = sym.append ('g')
          .classed ('shield', true);

    // This forces a layout !!!
    // You need to attach it to the DOM first.
    // Firefox does not compute it in symbols.
    //   const bb = text.node ().getBBox ();
    // Fuck this! Lets go for an estimate instead.

    const dx = 10,
          dy = 14;

    const digits  = [... text.matchAll (/\p{N}/gu)].length;
    const letters = [... text.matchAll (/\p{L}/gu)].length;

    const size = {
        'width'  : digits * dx + letters * (dx + 2) + 4,
        'height' : dy + 2,
        'dx'     : dx,
        'dy'     : dy,
    };

    const nodes = [foreground2, foreground, background].map ((ground) => {
        return draw_osmc_symbol (ground, size);
    }).reverse ();

    for (const n of nodes) {
        if (n) g.node ().appendChild (n);
    }

    if (text) {
        g.append ('text')
            .attr ('fill', textcolor)
            .attr ('y', 1)
            .text (text);
    }

    sym.attr ('viewBox', `${-size.width/2} ${-size.height/2} ${size.width} ${size.height}`);

    return [sym, size];
}
