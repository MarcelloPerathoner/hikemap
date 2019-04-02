@line-color-path:         red;
@line-color-track-casing: @track-casing;
@line-color-track:        @track-fill;

@line-width-path: 1;

@line-simplify-z14: 64;
@line-simplify-z16: 16;
@line-simplify-z18: 4;
@line-simplify-algorithm: visvalingam-whyatt;

@line-dasharray-sac-unknown:                   8,4,2,4;
@line-dasharray-sac-hiking:                    none;
@line-dasharray-sac-mountain-hiking:           8,4;
@line-dasharray-sac-demanding-mountain-hiking: 4,8;
@line-dasharray-sac-alpine-hiking:             none; /* hatched */
@line-dasharray-sac-demanding-alpine-hiking:   none;
@line-dasharray-sac-difficult-alpine-hiking:   none;

@hatch-dasharray-sac: 1, 9;
@hatch-dasharray-sac-alpine-hiking-hatch:           @hatch-dasharray-sac;
@hatch-dasharray-sac-demanding-alpine-hiking-hatch: @hatch-dasharray-sac;
@hatch-dasharray-sac-difficult-alpine-hiking-hatch: @hatch-dasharray-sac;

@text-fill-ref:    #c22;
@text-spacing-ref: 500;

/* draw a halo under highways that are hiking routes */

#hiking-routes-halo {
    opacity: 0.2;
    [route_refs != null] {
        line-color: @line-color-path;

        line-simplify-algorithm: @line-simplify-algorithm;
        [zoom >= 14] {
            line-width: 6 * @line-width-path + @tertiary-width-z14;
        }
        [zoom >= 16] {
            line-width: 6 * @line-width-path + @tertiary-width-z16;
        }
        [zoom >= 18] {
            line-width: 6 * @line-width-path + @tertiary-width-z18;
        }
        line-join: round;
        line-cap: round;

        /* these highways are drawn by ourselves in a smoothed fashion,
           all the rest are drawn by openstreetmap in an edgy fashion.
           the halo must follow the smooth line too. */
        line-smooth: 0;
        line-simplify: none;
        [highway = 'path'],
        [highway = 'footway'],
        [highway = 'track'],
        [highway = 'via_ferrata'] {
            [zoom >= 14] {
                line-smooth: 1;
                line-simplify: @line-simplify-z14;
            }
            [zoom >= 16] {
                line-smooth: 1;
                line-simplify: @line-simplify-z16;
            }
            [zoom >= 18] {
                line-smooth: 1;
                line-simplify: @line-simplify-z18;
            }
        }
    }
}

#hiking-path-casing {
    [highway = 'track'] {
        [zoom >= 13] {
            line-color: @line-color-track-casing;
            line-opacity: 1;
            line-join: round;
            line-cap: round;
            [zoom >= 13] {
                line-width: @track-width-z13 + 2 * @paths-background-width;
            }
            [zoom >= 15] {
                line-width: @track-width-z15 + 2 * @paths-background-width;
            }

            line-smooth: 0;
            line-simplify: none;
            line-simplify-algorithm: @line-simplify-algorithm;
            [zoom >= 14] {
                line-smooth: 1;
                line-simplify: @line-simplify-z14;
            }
            [zoom >= 16] {
                line-smooth: 1;
                line-simplify: @line-simplify-z16;
            }
            [zoom >= 18] {
                line-smooth: 1;
                line-simplify: @line-simplify-z18;
            }

            [sac_scale = ''] {
                line-dasharray: @line-dasharray-sac-unknown;
            }
            [sac_scale = 'hiking'] {
                line-dasharray: @line-dasharray-sac-hiking;
            }
            [sac_scale = 'mountain_hiking'] {
                line-dasharray: @line-dasharray-sac-mountain-hiking;
            }
            [sac_scale = 'demanding_mountain_hiking'] {
                line-dasharray: @line-dasharray-sac-demanding-mountain-hiking;
            }
        }
    }
}

#hiking-path-fill {
    [highway = 'via_ferrata'],
    [highway = 'footway'],
    [highway = 'path'] {
        line-color: @line-color-path;
        [zoom >= 13] {
            line-width: @footway-width-z14;
        }
        [zoom >= 15] {
            line-width: @footway-width-z15;
        }
    }
    [highway = 'track'] {
        line-color: @line-color-track;
        [zoom >= 13] {
            line-width: @track-width-z13;
        }
        [zoom >= 15] {
            line-width: @track-width-z15;
        }
    }

    [highway = 'via_ferrata'],
    [sac_scale = 'alpine_hiking'],
    [sac_scale = 'demanding_alpine_hiking'],
    [sac_scale = 'difficult_alpine_hiking'] {
        ::hatch {
            /* hatch the line to fake a look like crosses */
            line-width:     7 * @line-width-path;
            line-color:     @line-color-path;
            line-dasharray: @hatch-dasharray-sac;
            line-dash-offset: 4;

            line-smooth: 0;
            line-simplify: none;
            line-simplify-algorithm: @line-simplify-algorithm;
            [zoom >= 14] {
                line-smooth: 1;
                line-simplify: @line-simplify-z14;
            }
            [zoom >= 16] {
                line-smooth: 1;
                line-simplify: @line-simplify-z16;
            }
            [zoom >= 18] {
                line-smooth: 1;
                line-simplify: @line-simplify-z18;
            }
        }
    }

    line-smooth: 0;
    line-simplify: none;
    line-simplify-algorithm: @line-simplify-algorithm;
    [zoom >= 14] {
        line-smooth: 1;
        line-simplify: @line-simplify-z14;
    }
    [zoom >= 16] {
        line-smooth: 1;
        line-simplify: @line-simplify-z16;
    }
    [zoom >= 18] {
        line-smooth: 1;
        line-simplify: @line-simplify-z18;
    }

    /* FIXME: Do this in SQL */

    [sac_scale = ''] {
        line-dasharray: @line-dasharray-sac-unknown;
    }
    [sac_scale = 'hiking'] {
        line-dasharray: @line-dasharray-sac-hiking;
    }
    [sac_scale = 'mountain_hiking'] {
        line-dasharray: @line-dasharray-sac-mountain-hiking;
    }
    [sac_scale = 'demanding_mountain_hiking'] {
        line-dasharray: @line-dasharray-sac-demanding-mountain-hiking;
    }
    [sac_scale = 'alpine_hiking'] {
        line-dasharray: @line-dasharray-sac-alpine-hiking;
    }
    [sac_scale = 'demanding_alpine_hiking'] {
        line-dasharray: @line-dasharray-sac-demanding-alpine-hiking;
    }
    [sac_scale = 'difficult_alpine_hiking'] {
        line-dasharray: @line-dasharray-sac-difficult-alpine-hiking;
    }

    [trail_visibility = ''] {
    }
    [trail_visibility = 'excellent'] {
    }
    [trail_visibility = 'good'] {
    }
    [trail_visibility = 'intermediate'] {
    }
    [trail_visibility = 'bad'] {
    }
    [trail_visibility = 'horrible'] {
    }
    [trail_visibility = 'no'] {
    }
}

#hiking-routes-ref {
    text-name: "[route_refs]";
    text-size: 12;
    text-dy: 6;

    [zoom >= 16] {
        text-size: 14;
        text-dy: 7;
    }
    [zoom >= 17] {
        text-size: 16;
        text-dy: 8;
    }

    text-clip: false;
    text-fill: @text-fill-ref;
    text-face-name: @book-fonts;
    text-halo-radius: @standard-halo-radius;
    text-halo-fill: @standard-halo-fill;
    text-margin: 10;
    text-placement: line;
    text-spacing: @text-spacing-ref;
    text-vertical-alignment: bottom;
}
