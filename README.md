# worknetic-flow

Lokaler Wispr-Flow-Klon für macOS Apple Silicon. Push-to-Talk-Diktat via globalen Hotkey.

## Setup
1. `uv sync`
2. `cp .env.template .env && open .env` (Groq API Key eintragen)
3. `uv run python -m wnflow`

## Permissions (First Run)
- Microphone (Systemdialog beim ersten Recording)
- Accessibility (Systemeinstellungen → Datenschutz → Bedienungshilfen)
- Input Monitoring (Systemeinstellungen → Datenschutz → Input Monitoring)
