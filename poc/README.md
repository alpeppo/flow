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
