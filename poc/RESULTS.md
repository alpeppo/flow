# POC Results

## POC 1: mlx-whisper Latenz

**Datum:** 2026-05-26
**Hardware:** MacBook Air M4, 16 GB RAM
**Modell:** mlx-community/whisper-large-v3-turbo-q4
**Warmup:** 23794ms (einmalig, inkl. Modell-Download ~16s)

### Latenz-Tabelle (3 Runs pro File, Median)

| File | Median | Min | Max | Target | Status |
|---|---|---|---|---|---|
| 1s.wav | 2259ms | 2095ms | 2372ms | — | 🔴 |
| 3s.wav | 3653ms | 3357ms | 3787ms | <700ms | ❌ FAIL |
| 5s.wav | 3814ms | 3296ms | 4008ms | — | 🔴 |
| 15s.wav | 2858ms | 2742ms | 2979ms | <1500ms | ❌ FAIL |

### Transcription-Qualität

- 1s.wav: "Hallo Kevin" ✅
- 3s.wav: "Schreibt mir bitte eine kurze Mail an Kevin." ✅
- 5s.wav: "Heute habe ich mit Tim über das Worknetic Projekt gesprochen." ✅ (Hotword "Worknetic" korrekt erkannt)
- 15s.wav: Etwas verworren wenn abgelesen statt natürlich gesprochen

### Beobachtungen

- mlx-whisper hat ~2s Fixed-Overhead pro Inferenz (Audio-Load, JIT, Setup)
- 15s ist schneller als 3s+5s → ungewöhnlich, vermutlich JIT-Effekt
- Qualität ist gut, Hotwords funktionieren
- **Reviewer hatte Recht:** anvanvan-Benchmark ~1s war zu optimistisch für die echte Codepath-Latenz

### Entscheidung

**ACCEPT mit Trade-off:** Tim akzeptiert ~3-4s Tail-Latenz für jetzt.
Tool ist daily-driver-tauglich für Mails/längere Diktate, weniger für ultra-kurze Befehle.

**Future-Hebel falls nötig:**
- whisper.cpp mit Metal-Bindings (pywhispercpp) → 4-8x schneller
- `stt/engine.py` ist als Modul isoliert → Backend-Swap später möglich

### Entscheidung: PROCEED zu POC 2

## POC 2: Hotkey
_Tim füllt nach dem Run_

## POC 3: E2E Pipeline
_Tim füllt nach dem Run_
