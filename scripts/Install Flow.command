#!/bin/bash
# Install Flow.command — One-Click-Installer fuers Flow-DMG.
#
# Macht zwei Dinge:
#   1) Kopiert Flow.app aus dem DMG nach /Applications
#   2) Entfernt das Gatekeeper-Quarantine-Flag (xattr -cr)
#
# Damit umgeht der Nutzer die "Flow is damaged" / "Apple konnte nicht
# pruefen ob frei von Schadsoftware"-Meldungen — ohne Apple-Developer-Account.

set -e

DMG_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SRC="$DMG_DIR/Flow.app"
APP_DST="/Applications/Flow.app"

# Schoene Ausgabe
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
RED="\033[1;31m"
RESET="\033[0m"

clear
cat <<'EOF'
  ┌─────────────────────────────────────────┐
  │                                         │
  │           Flow — Installer              │
  │                                         │
  └─────────────────────────────────────────┘

EOF

if [ ! -d "$APP_SRC" ]; then
  echo -e "${RED}Fehler:${RESET} Flow.app nicht im selben Ordner wie dieses Skript gefunden."
  echo "Stelle sicher, dass du das Skript aus dem geöffneten DMG ausführst."
  echo
  read -p "Drücke Enter zum Schließen..."
  exit 1
fi

# Existing install entfernen falls vorhanden
if [ -d "$APP_DST" ]; then
  echo -e "${YELLOW}Eine ältere Version von Flow ist bereits installiert.${RESET}"
  echo "Sie wird durch die neue ersetzt."
  echo
  # Laufende Instanz beenden
  pkill -f "/Applications/Flow.app/Contents/MacOS/Flow" 2>/dev/null || true
  sleep 1
  # Backup statt rm (sicher)
  BAK_DIR="/tmp/Flow.app.bak.$(date +%Y%m%d-%H%M%S)"
  mv "$APP_DST" "$BAK_DIR"
  echo "  → Alte Version nach $BAK_DIR verschoben (kann später gelöscht werden)."
  echo
fi

echo "Kopiere Flow.app nach /Applications/ ..."
cp -R "$APP_SRC" "$APP_DST"
echo -e "  ${GREEN}✓${RESET} Kopiert."
echo

echo "Entferne Gatekeeper-Quarantine-Flag ..."
xattr -cr "$APP_DST"
echo -e "  ${GREEN}✓${RESET} Quarantine entfernt."
echo

echo "Registriere Flow bei macOS LaunchServices ..."
/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "$APP_DST" 2>/dev/null || true
echo -e "  ${GREEN}✓${RESET} Registriert."
echo

cat <<EOF
${GREEN}✓ Installation fertig.${RESET}

Nächste Schritte:

  1) Öffne Flow.app aus deinem Programme-Ordner
     (oder klicke direkt hier: ${YELLOW}open /Applications/Flow.app${RESET})

  2) macOS fragt nach zwei Berechtigungen:
       • Mikrofon → erlauben
       • Bedienungshilfen → System­einstellungen → Datenschutz
         & Sicherheit → Bedienungshilfen → Flow einschalten

  3) (Optional) Trage in der App unter "Einstellungen" deinen
     Groq-API-Key ein, um Formal-/Anti-Wut-Modus zu nutzen.
     Key holen: https://console.groq.com/keys

Doppel-Tap auf fn startet die Aufnahme.

EOF

read -p "Drücke Enter zum Schließen..."

# Optional: Flow direkt starten? Schoene letzte Geste.
open "$APP_DST" 2>/dev/null || true
