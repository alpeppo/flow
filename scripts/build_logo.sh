#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BRAND_DIR="$SCRIPT_DIR/brand"
MENUBAR_SVG="$BRAND_DIR/wnflow_icon.svg"
APP_SVG="$BRAND_DIR/wnflow_appicon.svg"

if [ ! -f "$MENUBAR_SVG" ]; then
    echo "ERROR: SVG nicht gefunden: $MENUBAR_SVG"
    exit 1
fi
if [ ! -f "$APP_SVG" ]; then
    echo "ERROR: SVG nicht gefunden: $APP_SVG"
    exit 1
fi

# Renderer auswaehlen
if command -v rsvg-convert &> /dev/null; then
    RENDER_CMD="rsvg-convert"
elif command -v magick &> /dev/null; then
    RENDER_CMD="magick"
elif command -v convert &> /dev/null; then
    RENDER_CMD="convert"
else
    echo "ERROR: rsvg-convert oder ImageMagick benötigt."
    echo "  brew install librsvg"
    echo "  oder: brew install imagemagick"
    exit 1
fi
echo "Renderer: $RENDER_CMD"

render() {
    local svg="$1"
    local size="$2"
    local out="$3"
    case "$RENDER_CMD" in
        rsvg-convert)
            rsvg-convert -w "$size" -h "$size" "$svg" -o "$out"
            ;;
        magick|convert)
            "$RENDER_CMD" -background none -density 384 "$svg" -resize "${size}x${size}" "$out"
            ;;
    esac
}

# Menubar-Icons mit Retina-Versionen (@2x). macOS sucht automatisch
# nach <name>@2x.<ext> wenn das Hauptbild geladen wird und der Screen Retina ist.
echo ""
echo "Menubar-PNGs..."
render "$MENUBAR_SVG" 16 "$BRAND_DIR/wnflow_icon_16.png"
render "$MENUBAR_SVG" 32 "$BRAND_DIR/wnflow_icon_16@2x.png"
render "$MENUBAR_SVG" 22 "$BRAND_DIR/wnflow_icon_22.png"
render "$MENUBAR_SVG" 44 "$BRAND_DIR/wnflow_icon_22@2x.png"
render "$MENUBAR_SVG" 64 "$BRAND_DIR/wnflow_icon_64.png"
render "$MENUBAR_SVG" 128 "$BRAND_DIR/wnflow_icon_64@2x.png"

# App-Icon-PNGs (mit Squircle-Hintergrund)
echo ""
echo "App-Icon-PNGs..."
ICONSET_DIR="$BRAND_DIR/wnflow.iconset"
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

# macOS .icns Standardgrößen
render "$APP_SVG" 16   "$ICONSET_DIR/icon_16x16.png"
render "$APP_SVG" 32   "$ICONSET_DIR/icon_16x16@2x.png"
render "$APP_SVG" 32   "$ICONSET_DIR/icon_32x32.png"
render "$APP_SVG" 64   "$ICONSET_DIR/icon_32x32@2x.png"
render "$APP_SVG" 128  "$ICONSET_DIR/icon_128x128.png"
render "$APP_SVG" 256  "$ICONSET_DIR/icon_128x128@2x.png"
render "$APP_SVG" 256  "$ICONSET_DIR/icon_256x256.png"
render "$APP_SVG" 512  "$ICONSET_DIR/icon_256x256@2x.png"
render "$APP_SVG" 512  "$ICONSET_DIR/icon_512x512.png"
render "$APP_SVG" 1024 "$ICONSET_DIR/icon_512x512@2x.png"

# iconutil ist macOS-only — erstellt .icns aus dem Iconset
if command -v iconutil &> /dev/null; then
    iconutil -c icns "$ICONSET_DIR" -o "$BRAND_DIR/wnflow.icns"
    echo "App-Bundle-Icon: $BRAND_DIR/wnflow.icns"
else
    echo "WARN: iconutil nicht gefunden (macOS-only) — .icns übersprungen"
fi

echo ""
echo "Brand-Assets erzeugt:"
ls -la "$BRAND_DIR"/*.png "$BRAND_DIR"/*.icns 2>/dev/null || ls -la "$BRAND_DIR"/*.png
