@line-color-sac-unknown: grey;
@line-color-sac-hiking: red;
@line-color-sac-mountain-hiking: red;
@line-color-sac-demanding-mountain-hiking: red;
@line-color-sac-alpine-hiking: blue;
@line-color-sac-demanding-alpine-hiking: blue;
@line-color-sac-difficult-alpine-hiking: blue;

@line-dasharray-sac-unknown: none;
@line-dasharray-sac-hiking:  none;
@line-dasharray-sac-mountain-hiking: 8,8;
@line-dasharray-sac-demanding-mountain-hiking: 2,8;
@line-dasharray-sac-alpine-hiking: none;
@line-dasharray-sac-demanding-alpine-hiking: 8,8;
@line-dasharray-sac-difficult-alpine-hiking: 2,8;

@hiking-ref-fill: #c22;
@hiking-path-text-spacing: 500;
@hiking-path-line-width: 1;

#hiking-path-fill {
    ::halo {
        opacity: 0.2;
        [ref != null] {
            line-width: 10 * @hiking-path-line-width;
            line-join: round;
            line-cap: round;

            [sac_scale = ''] {
                line-color:     @line-color-sac-unknown;
                line-dasharray: @line-dasharray-sac-unknown;
            }
            [sac_scale = 'hiking'] {
                line-color:     @line-color-sac-hiking;
                line-dasharray: @line-dasharray-sac-hiking;
            }
            [sac_scale = 'mountain_hiking'] {
                line-color:     @line-color-sac-mountain-hiking;
                line-dasharray: @line-dasharray-sac-mountain-hiking;
            }
            [sac_scale = 'demanding_mountain_hiking'] {
                line-color:     @line-color-sac-demanding-mountain-hiking;
                line-dasharray: @line-dasharray-sac-demanding-mountain-hiking;
            }
            [sac_scale = 'alpine_hiking'] {
                line-color:     @line-color-sac-alpine-hiking;
                line-dasharray: @line-dasharray-sac-alpine-hiking;
            }
            [sac_scale = 'demanding_alpine_hiking'] {
                line-color:     @line-color-sac-demanding-alpine-hiking;
                line-dasharray: @line-dasharray-sac-demanding-alpine-hiking;
            }
            [sac_scale = 'difficult_alpine_hiking'] {
                line-color:     @line-color-sac-difficult-alpine-hiking;
                line-dasharray: @line-dasharray-sac-difficult-alpine-hiking;
            }
        }
    }

    line-width: @hiking-path-line-width;
    [highway = 'track'] {
        line-width: 2 * @hiking-path-line-width;
    }

    [sac_scale = ''] {
        line-color:     @line-color-sac-unknown;
        line-dasharray: @line-dasharray-sac-unknown;
    }
    [sac_scale = 'hiking'] {
        line-color:     @line-color-sac-hiking;
        line-dasharray: @line-dasharray-sac-hiking;
    }
    [sac_scale = 'mountain_hiking'] {
        line-color:     @line-color-sac-mountain-hiking;
        line-dasharray: @line-dasharray-sac-mountain-hiking;
    }
    [sac_scale = 'demanding_mountain_hiking'] {
        line-color:     @line-color-sac-demanding-mountain-hiking;
        line-dasharray: @line-dasharray-sac-demanding-mountain-hiking;
    }
    [sac_scale = 'alpine_hiking'] {
        line-color:     @line-color-sac-alpine-hiking;
        line-dasharray: @line-dasharray-sac-alpine-hiking;
    }
    [sac_scale = 'demanding_alpine_hiking'] {
        line-color:     @line-color-sac-demanding-alpine-hiking;
        line-dasharray: @line-dasharray-sac-demanding-alpine-hiking;
    }
    [sac_scale = 'difficult_alpine_hiking'] {
        line-color:     @line-color-sac-difficult-alpine-hiking;
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

/* this comes from route = hiking */

#hiking-text-ref {
    text-name: "[refs]";
    text-size: 8;
    text-dy: 5;

    [zoom >= 16] {
        text-size: 9;
        text-dy: 7;
    }
    [zoom >= 17] {
        text-size: 11;
        text-dy: 9;
    }

    text-clip: false;
    text-fill: @hiking-ref-fill;
    text-face-name: @book-fonts;
    text-halo-radius: @standard-halo-radius;
    text-halo-fill: @standard-halo-fill;
    text-margin: 10;
    text-placement: line;
    text-spacing: @hiking-path-text-spacing;
    text-vertical-alignment: middle;
}
