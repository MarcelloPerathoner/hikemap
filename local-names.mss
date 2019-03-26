@local-names-fill: #222;
@local-names-fill-light: #777;

#local-names::valley {
    [natural = 'valley'],
    [natural = 'ridge'] {
        text-name: "[name]";

        text-face-name: @book-fonts;
        text-halo-fill: @standard-halo-fill;
        text-halo-radius: @standard-halo-radius * 1.5;

        text-spacing: 500;

        text-clip: false;
        text-placement: line;
        text-vertical-alignment: middle;
        text-max-char-angle-delta: 45;

        [zoom >= 12][km_length >= 10] {
            text-fill: @local-names-fill;
            text-size: 10;
            text-character-spacing: 10;
        }
        [zoom >= 14][km_length >= 5] {
            text-fill: @local-names-fill-light;
            text-size: 16;
            text-character-spacing: 16;
        }
        [zoom >= 16][km_length >= 1] {
            text-fill: @local-names-fill-light;
            text-size: 24;
            text-character-spacing: 24;
        }
    }
}
