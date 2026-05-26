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

**Datum:** 2026-05-26
**Initial-Test mit pynput:** FAIL — Tim wollte Fn-Taste, pynput kann Fn auf macOS nicht erkennen.

### Pivot zu pyobjc

Neuer POC `poc_fn_key.py` mit `NSEvent.addGlobalMonitorForEventsMatchingMask`
und `NSEventModifierFlagFunction` (0x800000).

**Validiert:**
- ✅ Fn-Press / Fn-Release Events werden erkannt
- ✅ Doppel-Tipp-Detection (350ms Window) funktioniert
- ✅ TOGGLE_ON/TOGGLE_OFF-Logik im POC funktioniert

### Entscheidung

**Default-Hotkey: Fn-Taste via pyobjc NSEvent** (statt pynput).

Implikation für Spec/Plan v4:
- `hotkey.py` wird mit pyobjc statt pynput implementiert
- pynput bleibt nur für die `cmd+V` Output-Injection drin (das funktioniert dort)
- Plan v3 muss überarbeitet werden

### Entscheidung: PROCEED zu POC 3

---

## POC 3: E2E Pipeline

**Datum:** 2026-05-26
**Setup:** GROQ_API_KEY in `.env`, Mikro-Permission erteilt.

### Erste E2E-Messung (5s Aufnahme)

| Komponente | Latenz |
|---|---|
| Warmup (einmalig) | 3119ms |
| **STT (mlx-whisper)** | **2166ms** |
| Cleanup (Groq Llama 3.3 70b) | 362ms |
| Clipboard | 106ms |
| **Tail-Latenz** | **2634ms** |

### Output-Qualität

- **Raw STT:** "Hallo, äh, schreibt mir bitte kurz eine Mail."
- **Cleaned:** "Hallo, schreibt mir bitte kurz eine Mail."
- Cleanup hat "äh" sauber entfernt, Rest erhalten ✅

### Bewertung

- ❌ Tail-Latenz über Spec-Ziel (≤1200ms) → **akzeptiert, kein Showstopper**
- ✅ Cleanup funktioniert exzellent (362ms, qualitativ sauber)
- ✅ E2E-Pipeline ist solide — alle Komponenten arbeiten zusammen
- ⚠️ mlx-whisper STT dominiert die Latenz (82% der Tail-Time)

### Entscheidung: PROCEED zu Phase 1

Mit folgenden Anpassungen am Plan:
1. `hotkey.py` mit pyobjc statt pynput (POC 2 Pivot)
2. Latenz-Ziel in Spec/Plan auf ~2.5-3.5s revidiert (akzeptiert)
3. Modell-Swap (whisper.cpp + Metal) bleibt als Future-Hebel dokumentiert
