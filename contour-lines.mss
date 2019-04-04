@contour-color: brown;

@contour-lines-color: @contour-color;
@contour-lines-20-color: @contour-lines-color;
@contour-lines-100-color: @contour-lines-color;
@contour-lines-20-opacity: 0.15;
@contour-lines-100-opacity: 0.3;

@contour-text-color: @contour-color;
@contour-text-opacity: 0.5;
@contour-text-spacing: 500;

#contour-lines-25 {
    ::lines {
        [zoom >= 15] {
            line-smooth: 1;
            line-color: @contour-lines-20-color;
            line-opacity: @contour-lines-20-opacity;
        }
    }
}

#contour-lines-100 {
    ::lines {
        [zoom >= 13] {
            line-smooth: 1;
            line-color: @contour-lines-100-color;
            line-opacity: @contour-lines-100-opacity;
        }
    }
    ::figures {
        [zoom >= 13] {
            text-name: "[ELEVATION]";
            text-size: 8;
            text-dy: 0;

            [zoom >= 16] {
                text-size: 9;
            }
            [zoom >= 17] {
                text-size: 11;
            }

            text-fill: @contour-text-color;
            text-clip: false;
            text-face-name: @book-fonts;
            text-halo-radius: @standard-halo-radius;
            text-halo-fill: @standard-halo-fill;
            text-margin: 10;
            text-placement: line;
            text-spacing: @contour-text-spacing;
            text-vertical-alignment: middle;
            text-opacity: @contour-text-opacity;
        }
    }
}
