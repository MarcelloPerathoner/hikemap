@footway-fill: red;

@cycleway-width-z14: 0.8;
@footway-width-z13:  0.8;

@line-width-path: 1;

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

@line-simplify-z14: 64;
@line-simplify-z16: 16;
@line-simplify-z18: 4;
@line-simplify-algorithm: visvalingam-whyatt;

#roads-extra-fill {
  ::casing {
    line: none;

    [highway = 'via_ferrata'],
    [highway = 'footway'],
    [highway = 'path'][bicycle != 'designated'][horse != 'designated'] {
      line-color: @footway-casing;
      line-cap: round;
      line-join: round;
      line-width: @footway-width-z15 + 2 * @paths-background-width;
      line-opacity: 0.4;

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

      [zoom >= 16] {
        line-width: @footway-width-z16 + 2 * @paths-background-width;
      }
      [zoom >= 18] {
        line-width: @footway-width-z18 + 2 * @paths-background-width;
      }
      [zoom >= 19] {
        line-width: @footway-width-z19 + 2 * @paths-background-width;
      }
    }
  }
  ::fill {
    line: none;

    [highway = 'via_ferrata'],
    [highway = 'footway'],
    [highway = 'path'][bicycle != 'designated'][horse != 'designated'] {
      line-color: @footway-fill;
      /* [access = 'no'] { line-color: @footway-fill-noaccess; } */
      line-join: round;
      line-cap: round;
      line-width: @footway-width-z14;

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
  }
  ::hatch {
    line: none;

    [highway = 'via_ferrata'],
    [highway = 'footway'],
    [highway = 'path'][bicycle != 'designated'][horse != 'designated'] {

      /* hatch difficult ways */
      [sac_scale = 'alpine_hiking'],
      [sac_scale = 'demanding_alpine_hiking'],
      [sac_scale = 'difficult_alpine_hiking'] {

        line-width:     7 * @line-width-path;
        line-color:     @footway-fill;
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
  }
}
