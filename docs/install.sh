#!/bin/bash
# Flow online installer — kein Apple-Developer-Account-Notar-Quatsch.
#
# Nutzung:
#   curl -fsSL https://alpeppo.github.io/flow/install.sh | bash
#
# Macht:
#   1) Prüfe macOS + Apple Silicon
#   2) Laedt die neueste DMG via curl (kein Quarantine vom Browser)
#   3) Mountet das DMG
#   4) Kopiert Flow.app nach /Applications
#   5) Entfernt das Quarantine-Flag
#   6) Unmountet, raeumt auf
#   7) Startet Flow

set -e

REPO="alpeppo/flow"

# ANSI colors
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
BLUE="\033[1;34m"
DIM="\033[2m"
RESET="\033[0m"

print_step() {
  echo
  echo -e "${BLUE}▸${RESET} $1"
}

print_done() {
  echo -e "  ${GREEN}✓${RESET} $1"
}

print_fail() {
  echo -e "${RED}✗ $1${RESET}" >&2
  exit 1
}

cat <<EOF

  ${BLUE}═══════════════════════════════════════════${RESET}
  ${BLUE}            Flow — Installer${RESET}
  ${BLUE}═══════════════════════════════════════════${RESET}

  Local-first dictation for macOS.
  Repository: https://github.com/${REPO}

EOF

# ----- Preflight -----
print_step "Prüfe System"

if [ "$(uname)" != "Darwin" ]; then
  print_fail "Flow laeuft nur auf macOS."
fi
print_done "macOS erkannt"

ARCH="$(uname -m)"
if [ "$ARCH" != "arm64" ]; then
  print_fail "Flow benötigt Apple Silicon (M1/M2/M3/M4). Dieser Mac ist $ARCH."
fi
print_done "Apple Silicon ($ARCH)"

OS_VERSION="$(sw_vers -productVersion)"
print_done "macOS $OS_VERSION"

# ----- Find latest DMG -----
print_step "Suche neuestes Release"

RELEASE_JSON=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" 2>/dev/null || true)
if [ -z "$RELEASE_JSON" ]; then
  print_fail "Konnte Release-Info nicht laden. Prüfe Internet-Verbindung."
fi

DMG_URL=$(echo "$RELEASE_JSON" | grep '"browser_download_url"' | grep -oE 'https://[^"]+\.dmg' | head -1)
if [ -z "$DMG_URL" ]; then
  print_fail "Kein DMG im neuesten Release gefunden."
fi

VERSION=$(echo "$RELEASE_JSON" | grep '"tag_name"' | head -1 | sed -E 's/.*"v?([^"]+)".*/\1/')
print_done "Version $VERSION gefunden"

# ----- Download -----
print_step "Lade DMG (~260 MB)"
DMG_PATH="/tmp/Flow-installer-$$.dmg"
trap "rm -f '$DMG_PATH'" EXIT

curl -fL --progress-bar -o "$DMG_PATH" "$DMG_URL" \
  || print_fail "Download fehlgeschlagen."

xattr -cr "$DMG_PATH" 2>/dev/null || true
print_done "Heruntergeladen"

# ----- Mount -----
print_step "Mounte DMG"

hdiutil detach "/Volumes/Flow" -force 2>/dev/null || true

MOUNT_INFO=$(hdiutil attach "$DMG_PATH" -nobrowse -plist -readonly 2>/dev/null)
MOUNT_POINT=$(echo "$MOUNT_INFO" | grep -A 1 "mount-point" | tail -1 | sed -E 's/.*<string>(.*)<\/string>.*/\1/')

if [ -z "$MOUNT_POINT" ] || [ ! -d "$MOUNT_POINT" ]; then
  print_fail "DMG-Mount fehlgeschlagen."
fi
print_done "Gemountet unter $MOUNT_POINT"

trap "hdiutil detach '$MOUNT_POINT' -force >/dev/null 2>&1 || true; rm -f '$DMG_PATH'" EXIT

# ----- Install -----
APP_SRC="$MOUNT_POINT/Flow.app"
APP_DST="/Applications/Flow.app"

if [ ! -d "$APP_SRC" ]; then
  print_fail "Flow.app nicht im DMG gefunden."
fi

print_step "Installiere Flow.app"

if pgrep -f "/Applications/Flow.app/Contents/MacOS/Flow" >/dev/null 2>&1; then
  pkill -f "/Applications/Flow.app/Contents/MacOS/Flow" 2>/dev/null || true
  sleep 1
  print_done "Laufende Flow-Instanz beendet"
fi

if [ -d "$APP_DST" ]; then
  BAK_DIR="/tmp/Flow.app.bak.$(date +%Y%m%d-%H%M%S)"
  mv "$APP_DST" "$BAK_DIR"
  print_done "Alte Version nach $BAK_DIR verschoben"
fi

ditto "$APP_SRC" "$APP_DST"
print_done "Flow.app nach /Applications/ kopiert"

xattr -cr "$APP_DST"
print_done "Gatekeeper-Quarantine entfernt"

/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "$APP_DST" 2>/dev/null || true
print_done "Bei macOS registriert"

# ----- Cleanup -----
print_step "Raeume auf"
hdiutil detach "$MOUNT_POINT" -force >/dev/null 2>&1 || true
rm -f "$DMG_PATH"
trap - EXIT
print_done "Temp-Files entfernt"

# ----- Done -----
cat <<EOF

  ${GREEN}═══════════════════════════════════════════${RESET}
  ${GREEN}            ✓ Installation fertig${RESET}
  ${GREEN}═══════════════════════════════════════════${RESET}

  Naechste Schritte:

    ${YELLOW}1)${RESET} Flow startet gleich automatisch.
    ${YELLOW}2)${RESET} macOS fragt nach zwei Berechtigungen:
         • Mikrofon → erlauben
         • Bedienungshilfen → Systemeinstellungen
           öffnet sich automatisch, schalte ${BLUE}Flow${RESET} an.
    ${YELLOW}3)${RESET} ${DIM}(Optional)${RESET} Trage in der App deinen Groq-API-Key
       ein für Formal-/Anti-Wut-Modus:
         https://console.groq.com/keys

  ${DIM}Doppel-Tap auf fn startet die Aufnahme.${RESET}

EOF

open "$APP_DST" 2>/dev/null || true
