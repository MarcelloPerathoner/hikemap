@local-names-fill: #222;
@local-names-fill-light: #777;

#local-names::valley {
    [natural = 'arete'],
    [natural = 'ridge'],
    [natural = 'valley'] {
        [zoom >= 16][way_length >=  1000],
        [zoom >= 14][way_length >=  5000],
        [zoom >= 12][way_length >= 10000] {
            text-name: "[name]";

            text-face-name: @book-fonts;
            text-halo-fill: @standard-halo-fill;
            text-halo-radius: @standard-halo-radius * 1.5;

            text-spacing: 500;
            line-smooth: 1;
            line-opacity: 0;

            text-clip: false;
            text-placement: line;
            text-vertical-alignment: middle;
            text-max-char-angle-delta: 45;

            [zoom >= 12] {
                text-fill: @local-names-fill;
                text-size: 10;
                text-character-spacing: 10;
            }
            [zoom >= 14] {
                text-fill: @local-names-fill-light;
                text-size: 16;
                text-character-spacing: 16;
            }
            [zoom >= 16] {
                text-fill: @local-names-fill-light;
                text-size: 24;
                text-character-spacing: 24;
            }
        }
    }
}
