#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$PROJECT_DIR/scripts/launchd.plist.template"
TARGET="$HOME/Library/LaunchAgents/de.worknetic.flow.plist"
UV_PATH="$(which uv)"

if [ -z "$UV_PATH" ]; then
    echo "ERROR: uv not found. Install: https://docs.astral.sh/uv/"
    exit 1
fi

echo "Installing worknetic-flow launchd agent..."
echo "  Project: $PROJECT_DIR"
echo "  uv:      $UV_PATH"
echo "  Target:  $TARGET"

mkdir -p "$HOME/.worknetic-flow/logs"
mkdir -p "$HOME/Library/LaunchAgents"

sed \
    -e "s|__UV_PATH__|$UV_PATH|g" \
    -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
    -e "s|__HOME__|$HOME|g" \
    "$TEMPLATE" > "$TARGET"

echo ""
echo "Installed. Lade Agent:"
launchctl unload "$TARGET" 2>/dev/null || true
launchctl load "$TARGET"

echo ""
echo "worknetic-flow startet jetzt automatisch beim Login."
echo ""
echo "Manuelle Commands:"
echo "  Stop:     launchctl unload $TARGET"
echo "  Start:    launchctl load $TARGET"
echo "  Logs:     tail -f $HOME/.worknetic-flow/logs/wnflow.log"
echo "  Uninstall: launchctl unload $TARGET && rm $TARGET"
