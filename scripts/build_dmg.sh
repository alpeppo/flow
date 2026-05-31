#!/bin/bash
# build_dmg.sh — Erzeugt das Distributions-DMG mit One-Click-Installer.
#
# Verwendung:
#   ./scripts/build_dmg.sh [VERSION]
#
# Erwartet: dist/Flow.app muss bereits gebaut sein (uv run pyinstaller wnflow.spec).
#
# Erzeugt: dist/Flow-<VERSION>.dmg mit Inhalt:
#   - Flow.app
#   - Install Flow.command  (One-Click-Installer)
#   - Applications  (Symlink)
#
# Der Installer entfernt das Gatekeeper-Quarantine-Flag automatisch,
# damit der Nutzer nicht durch System-Einstellungen klicken muss.

set -e

VERSION="${1:-0.3.4}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_PATH="$REPO_ROOT/dist/Flow.app"
INSTALLER_PATH="$REPO_ROOT/scripts/Install Flow.command"
STAGE_DIR="/tmp/flow-dmg-stage"
DMG_PATH="$REPO_ROOT/dist/Flow-${VERSION}.dmg"

if [ ! -d "$APP_PATH" ]; then
  echo "Fehler: $APP_PATH nicht gefunden." >&2
  echo "Bitte zuerst bauen: uv run pyinstaller wnflow.spec --noconfirm" >&2
  exit 1
fi

if [ ! -f "$INSTALLER_PATH" ]; then
  echo "Fehler: Installer-Skript fehlt: $INSTALLER_PATH" >&2
  exit 1
fi

# Staging aufräumen
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

# Inhalte rein
cp -R "$APP_PATH" "$STAGE_DIR/"
cp "$INSTALLER_PATH" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

# Installer ausfuehrbar (sollte schon sein, aber sicher ist sicher)
chmod +x "$STAGE_DIR/Install Flow.command"

# Quarantine-Flag vorab löschen (damit der Installer selbst nicht erst
# entkarantaeniert werden muss)
xattr -cr "$STAGE_DIR/Install Flow.command" 2>/dev/null || true
xattr -cr "$STAGE_DIR/Flow.app" 2>/dev/null || true

# DMG bauen
rm -f "$DMG_PATH"
hdiutil create \
  -volname "Flow" \
  -srcfolder "$STAGE_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

# Staging weg
rm -rf "$STAGE_DIR"

echo
echo "✓ Fertig: $DMG_PATH"
ls -lh "$DMG_PATH"
