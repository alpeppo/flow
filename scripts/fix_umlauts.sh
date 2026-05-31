#!/bin/bash
# Replace ASCII-fallback umlauts with their proper Unicode forms.
# Run from repo root. Safe to re-run.
set -e
TARGETS=(
  "src/wnflow"
  "docs/install.sh"
  "scripts"
)
# Pair: from -> to. Self-exclude so the script's own search strings don't get rewritten.
declare -a PAIRS=(
  "fuer:für"
  "ueber:über"
  "naechste:nächste"
  "koennen:können"
  "muessen:müssen"
  "loeschen:löschen"
  "oeffnen:öffnen"
  "schliessen:schließen"
  "aendern:ändern"
  "moeglich:möglich"
  "noetig:nötig"
  "hoeren:hören"
  "spaeter:später"
  "prueft:prüft"
  "zusaetzlich:zusätzlich"
  "raeume:räume"
  "Pruefe:Prüfe"
  "Loesche:Lösche"
  "Aendere:Ändere"
)
for target in "${TARGETS[@]}"; do
  [ ! -e "$target" ] && continue
  for pair in "${PAIRS[@]}"; do
    from="${pair%%:*}"
    to="${pair##*:}"
    grep -rlE "$from" "$target" \
      --include="*.py" --include="*.html" --include="*.sh" \
      --exclude="fix_umlauts.sh" --exclude-dir=".git" 2>/dev/null \
      | xargs -I{} sed -i '' -E "s/$from/$to/g" {} 2>/dev/null || true
  done
done
echo "✓ Umlauts normalized. Review with: git diff --stat"
