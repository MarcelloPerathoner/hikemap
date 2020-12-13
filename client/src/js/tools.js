/**
 * This module implements helper functions and is a container for all stuff
 * that doesn't fit elsewhere.
 *
 * @module client/tools
 * @author Marcello Perathoner
 */

import * as d3  from 'd3';
import _        from 'lodash';


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

export function getIndexAtPoint (coordinates, latlng) {
    // inverse of getPointAtLength
    // needs an M dimension

    const p0 = [ latlng.lng, latlng.lat ]; // mouse pointer is here
    let min_distance = Infinity;           // the smallest so far
    let index = null;

    for (const [i, pt] of coordinates.entries ()) {
        const distance = d3.geoDistance (p0, pt);
        if (distance < min_distance) {
            min_distance = distance;
            index = i;
        }
    }
    return index;
}

export function sort_lines (geometry) {
    // reverses the linestrings in the input multilinestring that are inverted
    // so that every linestring starts where the previous one ended.

    if (geometry.type === 'LineString') {
        return;
    }

    if (geometry.type !== 'MultiLineString') {
        throw `Error: cannot not reverse geometry of type ${geometry.type}`;
    }

    // just one line, no processing required
    if (geometry.coordinates.length < 2) {
        return;
    }

    function eq (a, b) {
        return (a[0] === b[0]) && (a[1] === b[1]);
    }

    let le = null;  // last way's end
    let first_way = geometry.coordinates[0]; // temp store of first way

    for (const way of geometry.coordinates) {
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
    // into one linestring
    // This is a better stitcher than ST_MakeLine because it groks
    // reversed ways.
    // This is a better stitcher than ST_LineMerge because it handles
    // duplicated ways (forward and backward ways of a route).

    if (geometry.type === 'LineString') {
        return geometry;
    }

    if (geometry.type !== 'MultiLineString') {
        throw `Error: cannot not stitch geometry of type ${geometry.type}`;
    }

    // just one line, no stitching required
    if (geometry.coordinates.length === 1) {
        return {
            'type' : 'LineString',
            'coordinates' : geometry.coordinates[0],
        }
    }

    function eq (a, b) {
        return (a[0] === b[0]) && (a[1] === b[1]);
    }

    // determine the orientation of the first linestring
    let linestring;

    let w1 = geometry.coordinates[0];
    let w2 = geometry.coordinates[1];

    let n11 = w1[0];
    let n12 = w1[w1.length - 1];
    let n21 = w2[0];
    let n22 = w2[w2.length - 1];

    if (eq (n11, n21) || eq (n11, n22)) {
        w1.reverse ();
    }
    linestring = w1;

    for (w2 of geometry.coordinates.slice (1)) {
        const n1 = linestring[linestring.length - 1];
        n21 = w2[0];
        n22 = w2[w2.length - 1];

        if (eq (n1, n21) || eq (n1, n22)) {
            if (eq (n1, n22)) {
                w2.reverse ();
            }
            linestring = linestring.concat (w2.slice (1));
        } else {
            throw 'Error: could not stitch MultiLineString';
        }
    }

    return {
        'type'        : 'LineString',
        'coordinates' : linestring,
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

export function osmc_symbol (osmc_symbol, elem = 'svg:symbol') {
    // Convert osmc:symbol into an SVG symbol
    //
    // @param osmc_symbol The osmc:symbol string.
    //
    // @return The SVG symbol element.
    //
    // osmc:symbol = waycolor:background[:foreground][[:foreground2]:text:textcolor]

    let waycolor    = null,
        background  = '#fff',
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