#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BRAND_DIR="$SCRIPT_DIR/brand"
SVG="$BRAND_DIR/wnflow_icon.svg"

if [ ! -f "$SVG" ]; then
    echo "ERROR: SVG nicht gefunden: $SVG"
    exit 1
fi

# Probiere rsvg-convert (brew install librsvg) oder ImageMagick
if command -v rsvg-convert &> /dev/null; then
    echo "Verwende rsvg-convert..."
    rsvg-convert -w 16 -h 16 "$SVG" -o "$BRAND_DIR/wnflow_icon_16.png"
    rsvg-convert -w 22 -h 22 "$SVG" -o "$BRAND_DIR/wnflow_icon_22.png"
    rsvg-convert -w 64 -h 64 "$SVG" -o "$BRAND_DIR/wnflow_icon_64.png"
elif command -v magick &> /dev/null || command -v convert &> /dev/null; then
    MAGICK_CMD=$(command -v magick || command -v convert)
    echo "Verwende ImageMagick ($MAGICK_CMD)..."
    "$MAGICK_CMD" -background none -density 384 "$SVG" -resize 16x16 "$BRAND_DIR/wnflow_icon_16.png"
    "$MAGICK_CMD" -background none -density 384 "$SVG" -resize 22x22 "$BRAND_DIR/wnflow_icon_22.png"
    "$MAGICK_CMD" -background none -density 384 "$SVG" -resize 64x64 "$BRAND_DIR/wnflow_icon_64.png"
else
    echo "ERROR: rsvg-convert oder ImageMagick benötigt."
    echo "  brew install librsvg"
    echo "  oder: brew install imagemagick"
    exit 1
fi

echo "Logo-PNGs erstellt:"
ls -la "$BRAND_DIR"/*.png
