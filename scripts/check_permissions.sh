#!/bin/bash
# Öffnet die drei macOS Privacy-Panels die worknetic-flow braucht.

echo "worknetic-flow Permission-Check"
echo "==============================="
echo ""
echo "Öffne nacheinander folgende Privacy-Panels:"
echo "  1. Accessibility (für Hotkey + Paste)"
echo "  2. Input Monitoring (für globale Key-Events)"
echo "  3. Microphone (für Audio-Capture)"
echo ""
echo "Stelle sicher dass folgende App aktiviert ist:"
echo "  - Terminal (oder dein Code-Editor falls du via 'uv run' startest)"
echo "  - Falls als .app gebaut: worknetic-flow.app"
echo ""
read -p "Drueck Enter um die Panels zu oeffnen..."

open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
sleep 1
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
sleep 1
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"

echo ""
echo "Panels geöffnet. Aktiviere die App in JEDEM Panel."
echo "Danach worknetic-flow neu starten."
