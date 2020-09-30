@text-fill-ref:    #c22;
@text-spacing-ref: 300;

#hiking-routes-ref {
    text-name: "[route_refs]";

    text-size: 12;
    [zoom >= 16] {
        text-size: 14;
    }
    [zoom >= 18] {
        text-size: 16;
    }

    text-clip: false;
    text-fill: @text-fill-ref;
    text-face-name: @book-fonts;
    text-halo-radius: 2 * @standard-halo-radius;
    text-halo-fill: @standard-halo-fill;
    text-placement: line;
    text-spacing: @text-spacing-ref;
    text-label-position-tolerance: 30;
    text-vertical-alignment: middle;
}

#hiking-routes-name {
    text-name: "[route_names]";

    text-size: 10;
    [zoom >= 16] {
        text-size: 12;
    }
    [zoom >= 18] {
        text-size: 14;
    }

    text-clip: false;
    text-fill: @text-fill-ref;
    text-face-name: @book-fonts;
    text-halo-radius: 2 * @standard-halo-radius;
    text-halo-fill: @standard-halo-fill;
    text-placement: line;
    text-spacing: @text-spacing-ref;
    text-label-position-tolerance: 30;
    text-vertical-alignment: middle;
}

#hiking-roads-text-ref {
  [highway = 'track'] {
    [zoom >= 15] {
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
      text-fill: blue; /* #222; */
      text-face-name: @book-fonts;
      text-halo-radius: @standard-halo-radius;
      text-halo-fill: @standard-halo-fill;
      text-margin: 10;
      text-placement: line;
      text-spacing: 760;
      text-repeat-distance: @major-highway-text-repeat-distance;
      text-vertical-alignment: middle;
    }
  }
}

#hiking-paths-text-name {
  [highway = 'track'] {
    [zoom >= 15] {
      text-name: "[names]";
      text-fill: blue; /* #222; */
      text-size: 8;
      text-halo-radius: @standard-halo-radius;
      text-halo-fill: @standard-halo-fill;
      text-spacing: 300;
      text-clip: false;
      text-placement: line;
      text-face-name: @book-fonts;
      text-vertical-alignment: middle;
      text-dy: 5;
      text-repeat-distance: @major-highway-text-repeat-distance;
    }
    [zoom >= 16] {
      text-size: 9;
      text-dy: 7;
    }
    [zoom >= 17] {
      text-size: 11;
      text-dy: 9;
    }
  }

  [highway = 'via_ferrata'],
  [highway = 'footway'],
  [highway = 'path'] {
    [zoom >= 16] {
      text-name: "[names]";
      text-fill: blue; /* #222; */
      text-size: 9;
      text-halo-radius: @standard-halo-radius;
      text-halo-fill: @standard-halo-fill;
      text-spacing: 300;
      text-clip: false;
      text-placement: line;
      text-face-name: @book-fonts;
      text-vertical-alignment: middle;
      text-dy: 7;
      text-repeat-distance: @major-highway-text-repeat-distance;
    }
    [zoom >= 17] {
      text-size: 11;
      text-dy: 9;
    }
  }
}
