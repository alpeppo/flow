# POC Scripts

Validierungs-Skripte für die kritischen Annahmen des worknetic-flow Specs.

## POC 1: mlx-whisper Latenz-Benchmark

### Setup: Test-Fixtures erzeugen

Du brauchst 4 WAV-Files unter `poc/fixtures/`:
- `1s.wav` — kurzer Satz (~1s) wie "Hallo Kevin"
- `3s.wav` — mittlerer Satz (~3s) wie "Schreib mir bitte eine kurze Mail"
- `5s.wav` — etwas länger (~5s)
- `15s.wav` — Absatz (~15s)

**Variante A: QuickTime Player**
1. Neue Audioaufnahme → aufnehmen → stoppen
2. Datei → Exportieren → AAC (oder im Finder → "Audiodatei kopieren als WAV")
3. **Wichtig:** Im Terminal in 16kHz mono konvertieren:
   ```bash
   afconvert -f WAVE -d LEI16@16000 -c 1 input.m4a output.wav
   ```

**Variante B: sox (falls installiert via `brew install sox`)**
```bash
sox -d -r 16000 -c 1 -b 16 3s.wav trim 0 3
# Spricht direkt einen 3s Clip auf
```

### Benchmark ausführen

```bash
cd ~/Developer/worknetic-flow
uv run python poc/poc_mlx_whisper.py
```

**Erwartung:**
- Erste Ausführung lädt das Modell (~1.6 GB Download bei erstem Mal, danach gecached)
- Dann Tabelle mit Median/Min/Max-Latenz pro File
- PASS-Kriterien werden am Ende gecheckt

### Bei FAIL

Falls 3s-File >700ms oder 15s-File >1500ms:
- Probiere `mlx-community/whisper-large-v3-turbo` (FP16) statt q4
- Oder `mlx-community/whisper-medium-mlx`
- Wenn alle versagen: Reality-Check mit Claude

## POC 2: Hotkey-Detection

### Setup

Beim ersten Lauf fragt macOS nach **Input-Monitoring**-Permission. Erlauben.
Falls Script danach trotzdem nichts loggt: Permission im System-Settings für Terminal/iTerm aktivieren und Script neu starten.

### Ausführen

```bash
cd ~/Developer/worknetic-flow
uv run python poc/poc_hotkey.py
```

### Test-Szenarien (alle manuell)

**Szenario 1 — Right-Cmd 5s halten:**
- Erwartung: 1× PRESS, 1× RELEASE
- FAIL wenn: missed events, TIS/TSM-Warnings im Output

**Szenario 2 — Right-Cmd 5× doppel-tippen (schnell, <350ms):**
- Erwartung: 10× PRESS, 10× RELEASE
- FAIL wenn: weniger als 10 events detected

**Szenario 3 — KRITISCH: Right-Cmd halten + Terminal aktiv + 'abc' tippen:**
- Erwartung A (PASS): 'abc' erscheint im Terminal-Prompt
- Erwartung B (FAIL): Cmd-Shortcuts triggern (z.B. Cmd+A markiert alles, Cmd+W schließt Terminal-Tab, Cmd+C kopiert)
- **Wenn FAIL → wir wechseln Default-Hotkey auf `right_shift` oder `f13`**

**Szenario 4 — Wiederhole 1-3 mit Right-Shift (`shift_r`):**
- Generell stabiler als cmd_r
- Aber: Shift-Halten + Tippen erzeugt Großbuchstaben (kein System-Shortcut-Problem)

**Szenario 5 (falls F-Tasten dediziert sind, MacBook Air hat über Globe+F-Reihe):**
- F13/F14 testen falls dein Setup das hat
- Diese sind komplett konfliktfrei (kein System-Shortcut)

### ESC zum Beenden, dann Ergebnisse in RESULTS.md schreiben
