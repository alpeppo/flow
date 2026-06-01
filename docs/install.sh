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

# i18n: macOS uses LC_ALL > LC_MESSAGES > LANG, in that override order.
# Curl-piped bash often has none set; default to en_US so non-German
# users get English.
LANG_RAW="${LC_ALL:-${LC_MESSAGES:-${LANG:-en_US.UTF-8}}}"
if [[ "$LANG_RAW" == de* ]]; then
  LOC="de"
else
  LOC="en"
fi

# Translation function. Picks the EN literal as fallback for missing keys.
i18n() {
  local key="$1"
  case "$LOC.$key" in
    en.title)            echo "Flow — Installer" ;;
    de.title)            echo "Flow — Installer" ;;
    en.intro)            echo "Local-first dictation for macOS." ;;
    de.intro)            echo "Lokales Diktat für macOS." ;;
    en.system_check)     echo "Checking system" ;;
    de.system_check)     echo "Prüfe System" ;;
    en.not_macos)        echo "Flow only runs on macOS." ;;
    de.not_macos)        echo "Flow läuft nur auf macOS." ;;
    en.macos_ok)         echo "macOS detected" ;;
    de.macos_ok)         echo "macOS erkannt" ;;
    en.not_arm64)        echo "Flow requires Apple Silicon (M1/M2/M3/M4). This Mac is $ARCH." ;;
    de.not_arm64)        echo "Flow benötigt Apple Silicon (M1/M2/M3/M4). Dieser Mac ist $ARCH." ;;
    en.arm64_ok)         echo "Apple Silicon ($ARCH)" ;;
    de.arm64_ok)         echo "Apple Silicon ($ARCH)" ;;
    en.search_release)   echo "Looking for latest release" ;;
    de.search_release)   echo "Suche neuestes Release" ;;
    en.release_failed)   echo "Could not load release info. Check your internet connection." ;;
    de.release_failed)   echo "Konnte Release-Info nicht laden. Prüfe Internet-Verbindung." ;;
    en.no_dmg)           echo "No DMG in the latest release." ;;
    de.no_dmg)           echo "Kein DMG im neuesten Release gefunden." ;;
    en.version_found)    echo "Version $VERSION found" ;;
    de.version_found)    echo "Version $VERSION gefunden" ;;
    en.downloading)      echo "Downloading DMG (~260 MB)" ;;
    de.downloading)      echo "Lade DMG (~260 MB)" ;;
    en.download_failed)  echo "Download failed." ;;
    de.download_failed)  echo "Download fehlgeschlagen." ;;
    en.downloaded)       echo "Downloaded" ;;
    de.downloaded)       echo "Heruntergeladen" ;;
    en.mounting)         echo "Mounting DMG" ;;
    de.mounting)         echo "Mounte DMG" ;;
    en.mount_failed)     echo "DMG mount failed." ;;
    de.mount_failed)     echo "DMG-Mount fehlgeschlagen." ;;
    en.mounted_at)       echo "Mounted at $MOUNT_POINT" ;;
    de.mounted_at)       echo "Gemountet unter $MOUNT_POINT" ;;
    en.installing)       echo "Installing Flow.app" ;;
    de.installing)       echo "Installiere Flow.app" ;;
    en.app_not_found)    echo "Flow.app not found in DMG." ;;
    de.app_not_found)    echo "Flow.app nicht im DMG gefunden." ;;
    en.killed_existing)  echo "Stopped running Flow instance" ;;
    de.killed_existing)  echo "Laufende Flow-Instanz beendet" ;;
    en.moved_backup)     echo "Old version moved to $BAK_DIR" ;;
    de.moved_backup)     echo "Alte Version nach $BAK_DIR verschoben" ;;
    en.copied)           echo "Flow.app copied to /Applications/" ;;
    de.copied)           echo "Flow.app nach /Applications/ kopiert" ;;
    en.quarantine)       echo "Gatekeeper quarantine cleared" ;;
    de.quarantine)       echo "Gatekeeper-Quarantine entfernt" ;;
    en.registered)       echo "Registered with macOS" ;;
    de.registered)       echo "Bei macOS registriert" ;;
    en.cleanup)          echo "Cleaning up" ;;
    de.cleanup)          echo "Räume auf" ;;
    en.temp_removed)     echo "Temp files removed" ;;
    de.temp_removed)     echo "Temp-Files entfernt" ;;
    en.done_title)       echo "✓ Installation complete" ;;
    de.done_title)       echo "✓ Installation fertig" ;;
    en.next_steps)       echo "Next steps:" ;;
    de.next_steps)       echo "Nächste Schritte:" ;;
    en.step_launch)      echo "Flow will start automatically." ;;
    de.step_launch)      echo "Flow startet gleich automatisch." ;;
    en.step_perms)       echo "macOS will ask for two permissions:" ;;
    de.step_perms)       echo "macOS fragt nach zwei Berechtigungen:" ;;
    en.perm_mic)         echo "Microphone → allow" ;;
    de.perm_mic)         echo "Mikrofon → erlauben" ;;
    en.perm_a11y)        echo "Accessibility → System Settings → Privacy & Security → Accessibility → enable Flow" ;;
    de.perm_a11y)        echo "Bedienungshilfen → Systemeinstellungen → Datenschutz & Sicherheit → Bedienungshilfen → Flow einschalten" ;;
    en.step_groq)        echo "(Optional) Enter your Groq API key in the app for Formal / Anti-Rage mode:" ;;
    de.step_groq)        echo "(Optional) Trage in der App deinen Groq-API-Key ein für Formal-/Anti-Wut-Modus:" ;;
    en.fn_tip)           echo "Double-tap fn starts the recording." ;;
    de.fn_tip)           echo "Doppel-Tap auf fn startet die Aufnahme." ;;
    *)                   echo "[$key]" ;;
  esac
}

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

echo
echo -e "  ${BLUE}═══════════════════════════════════════════${RESET}"
echo -e "  ${BLUE}            $(i18n title)${RESET}"
echo -e "  ${BLUE}═══════════════════════════════════════════${RESET}"
echo
echo "  $(i18n intro)"
echo "  Repository: https://github.com/${REPO}"
echo

# ----- Preflight -----
print_step "$(i18n system_check)"

if [ "$(uname)" != "Darwin" ]; then
  print_fail "$(i18n not_macos)"
fi
print_done "$(i18n macos_ok)"

ARCH="$(uname -m)"
if [ "$ARCH" != "arm64" ]; then
  print_fail "$(i18n not_arm64)"
fi
print_done "$(i18n arm64_ok)"

OS_VERSION="$(sw_vers -productVersion)"
print_done "macOS $OS_VERSION"

# ----- Find latest DMG -----
print_step "$(i18n search_release)"

RELEASE_JSON=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" 2>/dev/null || true)
if [ -z "$RELEASE_JSON" ]; then
  print_fail "$(i18n release_failed)"
fi

DMG_URL=$(echo "$RELEASE_JSON" | grep '"browser_download_url"' | grep -oE 'https://[^"]+\.dmg' | head -1)
if [ -z "$DMG_URL" ]; then
  print_fail "$(i18n no_dmg)"
fi

VERSION=$(echo "$RELEASE_JSON" | grep '"tag_name"' | head -1 | sed -E 's/.*"v?([^"]+)".*/\1/')
print_done "$(i18n version_found)"

# ----- Download -----
print_step "$(i18n downloading)"
DMG_PATH="/tmp/Flow-installer-$$.dmg"
trap "rm -f '$DMG_PATH'" EXIT

curl -fL --progress-bar -o "$DMG_PATH" "$DMG_URL" \
  || print_fail "$(i18n download_failed)"

xattr -cr "$DMG_PATH" 2>/dev/null || true
print_done "$(i18n downloaded)"

# ----- Mount -----
print_step "$(i18n mounting)"

hdiutil detach "/Volumes/Flow" -force 2>/dev/null || true

MOUNT_INFO=$(hdiutil attach "$DMG_PATH" -nobrowse -plist -readonly 2>/dev/null)
MOUNT_POINT=$(echo "$MOUNT_INFO" | grep -A 1 "mount-point" | tail -1 | sed -E 's/.*<string>(.*)<\/string>.*/\1/')

if [ -z "$MOUNT_POINT" ] || [ ! -d "$MOUNT_POINT" ]; then
  print_fail "$(i18n mount_failed)"
fi
print_done "$(i18n mounted_at)"

trap "hdiutil detach '$MOUNT_POINT' -force >/dev/null 2>&1 || true; rm -f '$DMG_PATH'" EXIT

# ----- Install -----
APP_SRC="$MOUNT_POINT/Flow.app"
APP_DST="/Applications/Flow.app"

if [ ! -d "$APP_SRC" ]; then
  print_fail "$(i18n app_not_found)"
fi

print_step "$(i18n installing)"

if pgrep -f "/Applications/Flow.app/Contents/MacOS/Flow" >/dev/null 2>&1; then
  pkill -f "/Applications/Flow.app/Contents/MacOS/Flow" 2>/dev/null || true
  sleep 1
  print_done "$(i18n killed_existing)"
fi

if [ -d "$APP_DST" ]; then
  BAK_DIR="/tmp/Flow.app.bak.$(date +%Y%m%d-%H%M%S)"
  mv "$APP_DST" "$BAK_DIR"
  print_done "$(i18n moved_backup)"
fi

ditto "$APP_SRC" "$APP_DST"
print_done "$(i18n copied)"

xattr -cr "$APP_DST"
print_done "$(i18n quarantine)"

/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "$APP_DST" 2>/dev/null || true
print_done "$(i18n registered)"

# ----- Cleanup -----
print_step "$(i18n cleanup)"
hdiutil detach "$MOUNT_POINT" -force >/dev/null 2>&1 || true
rm -f "$DMG_PATH"
trap - EXIT
print_done "$(i18n temp_removed)"

# ----- Done -----
echo
echo -e "  ${GREEN}═══════════════════════════════════════════${RESET}"
echo -e "  ${GREEN}            $(i18n done_title)${RESET}"
echo -e "  ${GREEN}═══════════════════════════════════════════${RESET}"
echo
echo "  $(i18n next_steps)"
echo
echo -e "    ${YELLOW}1)${RESET} $(i18n step_launch)"
echo -e "    ${YELLOW}2)${RESET} $(i18n step_perms)"
echo "       • $(i18n perm_mic)"
echo "       • $(i18n perm_a11y)"
echo -e "    ${YELLOW}3)${RESET} ${DIM}(Optional)${RESET} $(i18n step_groq)"
echo "       https://console.groq.com/keys"
echo
echo -e "  ${DIM}$(i18n fn_tip)${RESET}"
echo

open "$APP_DST" 2>/dev/null || true
