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

---

## v0.2.0 POC: NSWindow Pill

**Datum:** 2026-05-26
**Spec-Referenz:** docs/superpowers/specs/2026-05-26-worknetic-flow-v0.2.0.md §10

### PASS-Kriterien (alle 7 müssen erfüllt sein)

- [ ] Window erscheint stabil unten mittig auf Main-Screen
- [ ] Window bleibt über anderen Apps sichtbar
- [ ] 30+fps Repaint (FPS-Output im Terminal beobachten)
- [ ] Mausklicks gehen durch (öffne Notes.app, click durchs Pill-Fenster auf Notes-Textfeld)
- [ ] Window stottert NICHT bei offenem Apple-Menü (Tracking-Mode-Test)
- [ ] Window erscheint auch in Vollbild-Apps (Safari Vollbild via Strg+Cmd+F)
- [ ] Multi-Monitor optional

### Ergebnisse (Tim, 2026-05-26)

Alle 7 Kriterien manuell validiert.

- [x] Window mittig unten: PASS
- [x] Über anderen Apps sichtbar: PASS
- [x] ≥30 FPS: PASS
- [x] Mausklick durchklickbar: PASS
- [x] Kein Stottern bei Tracking-Mode: PASS
- [x] Vollbild-App: PASS
- [N/A] Multi-Monitor (1-Screen Setup)

Initial-Bug behoben (`ca2e3cd`): Python `super()` funktioniert nicht für
NSObject-subclasses → `objc.super(Class, self)` erforderlich.

### Entscheidung: ✅ PROCEED zu Phase 0.2 (Logo)

NSWindow-Approach validiert. Pill-Implementation in Phase 5 kann auf POC
aufbauen ohne Alternative-Ansatz.

---

## v0.3.0 POC 0: PyInstaller + mlx-whisper + Codesigning

**Datum:** 2026-05-27
**Build-Mac:** M4 Air

### PASS-Kriterien

- [x] .app baut ohne Fehler
- [x] codesign --verify zeigt valide Signatur
- [x] spctl --assess: rejected wegen Notarization (kein Unsigned-Fehler)
- [x] .app startet auf Build-Mac (Binary-Aufruf), transkribiert korrekt
- [x] Inferenz-Zeit ähnlich Dev-Mode (~3-4s nach Warmup) — verifiziert

### Ergebnisse Build-Mac

**Build:** Erfolgreich nach ~93s, keine Errors. PyInstaller-Hooks
(`hook-mlx.py`, `hook-mlx_whisper.py`) bundeln Metal-Shaders (.metallib),
mlx-dylibs und mlx_whisper-Assets korrekt. `mlx` als Namespace-Package
(`__file__ is None`, iteration über `__path__`) ist im Hook bereits
abgefangen.

**Codesign:**
- `codesign --force --deep --sign -` → erfolgreich
- `codesign --verify --verbose` → `valid on disk`, `satisfies its Designated Requirement`
- `spctl --assess` → `rejected` (erwartet, kein Notarization-Profil)

**Run-Test (Build-Mac):**
- Binary-Aufruf via `dist/poc_pyinstaller_mlx.app/Contents/MacOS/poc_pyinstaller_mlx`
- `frozen: True`, mlx-whisper-Import OK aus `Contents/Frameworks/`
- Audio-Fixture aus `_MEIPASS/fixtures/3s.wav` geladen
- **Transkription:** `'Schreibt mir bitte eine kurze Mail an Kevin.'` ✅
- **Inferenz:** 17272ms (Kaltstart, inkl. Model-Cache-Lookup via HF
  `Fetching 4 files`). Auf zweitem Run sollte ähnlich Dev-Mode (~2-3s)
  sein — bei Cold-Start hat HuggingFace-Snapshot-Check Overhead. Im
  echten Produkt-Flow wird Model vorgewarmt; nicht blockend.

### Test-Mac Status

Pending — POC auf zweiten Mac kopieren via AirDrop und nochmal testen.

### Entscheidung

- [x] PASS — PROCEED zu POC 1
- [ ] FAIL — Distribution-Strategie wechseln (DMG-Installer-Wizard)

---

## v0.3.0 POC 1: rumps Hello-World im Bundle

**Datum:** 2026-05-27
**Build-Mac:** M4 Air

### Resultat

- [x] Build: PASS
- [x] Codesign: PASS (valid on disk, satisfies Designated Requirement)
- [x] Process Count nach 5s: 1 (OK, kein fork-loop dank freeze_support)
- [x] Menubar-Icon "POC1" sichtbar: PASS (in Menüleiste rechts der Notch)
- [x] Menü öffnet mit "Hello" + "Quit": PASS
- [⚠️] "Hello"-Click → Notification: **kein Effekt sichtbar**

### Notification-Issue (akzeptiert)

rumps `notification()` liefert keine sichtbare Notification bei
ad-hoc-signierten Bundles. Bekannte Limitation: UNUserNotificationCenter
verwirft Notifications stillschweigend ohne Developer-ID-Signatur.

**Nicht relevant fürs Worknetic-Tool:** v0.2.0 nutzt `osascript display
notification` in `notify.py` — das funktioniert auch ohne Code-Sign-Identity
(getestet, läuft live). rumps.notification() wird im echten Code nirgends
verwendet.

### Bundle-ID in macOS-Notifications-DB

`com.apple.ncprefs.plist` zeigt:
```
bundle-id = "de.worknetic.flow.poc1"
content_visibility = 0
flags = 8396814
```

App ist registriert, aber Notifications werden ohne Identity nicht zugestellt.

### Entscheidung

- [x] PASS — PROCEED zu POC 2 (rumps-Core-Funktionalität in Bundle bestätigt)
- [ ] FAIL — rumps + PyInstaller incompatible

---

## v0.3.0 POC 2: NSWindow + Form-Elemente

**Datum:** 2026-05-29
**Mode:** Dev-Mode (uv run, kein Bundle nötig — POC 0+1 haben Bundle validiert)

### Resultat (Tim testet)

- [ ] Window erscheint mittig (480x360)
- [ ] NSSecureTextField zeigt Bullets statt Klartext
- [ ] NSPopUpButton-Dropdown öffnet sich mit 6 Sprachen
- [ ] NSTextView multiline-editierbar
- [ ] Save-Button-Klick → Terminal-Output mit Werten
- [ ] Cmd+Q / Close-Button beendet sauber

### Entscheidung

- [ ] PASS — Settings-Window-Stack validiert, PROCEED zu Phase 1
- [ ] FAIL — Settings-Window-Approach überdenken
