# Flow

**Local-first dictation for macOS.** Tap a hotkey, speak, see your words pasted into whatever app is focused. Transcription happens on-device via MLX-Whisper. Cleanup (formal mode / anti-rage mode) goes through Groq's API — fast, but optional.

No cloud uploads of audio. No subscription. MIT-licensed.

> Inspired by Wispr Flow, built as a learning project that turned into a daily driver.

---

## Requirements

- macOS **13** (Ventura) or newer
- **Apple Silicon** (M1 / M2 / M3 / M4) — MLX-Whisper needs the Metal backend
- Optional: a free [Groq API key](https://console.groq.com/keys) for the formal/anti-wut cleanup modes

---

## Install (5 minutes)

1. **Download the latest DMG** from the [Releases page](https://github.com/alpeppo/flow/releases/latest).
2. **Open the DMG**, drag **Flow.app** into your **Applications** folder.
3. **Launch Flow.app**. macOS will ask for two permissions on first run:
   - **Microphone** (system dialog) → allow.
   - **Accessibility** → System Settings → Privacy & Security → Accessibility → toggle **Flow** on. This is what lets Flow listen for the `fn` hotkey globally and paste text into any focused app.
4. **Drop in your Groq API key** (optional, but recommended):
   - In Flow's main window → **Einstellungen** tab → paste the key → **Speichern**.
   - Without a key, you only get raw Whisper output (verbatim mode). With a key, formal/anti-wut cleanup gets enabled.

That's it. **Double-tap `fn`** anywhere and start dictating.

---

## How to use

| Action | Hotkey | What happens |
|---|---|---|
| Start recording | Double-tap **fn** | Pill appears at bottom of screen with red dot + live waveform + timer |
| Stop & paste | Double-tap **fn** again | Audio transcribed, cleaned (if Groq key set), pasted into focused app |
| Cancel recording | **ESC** or click the **X** on the pill | Audio discarded, nothing pasted |
| Force formal cleanup | Hold **Ctrl** while tapping fn | Override: this recording gets the "Formal" prompt |
| Force anti-wut cleanup | Hold **Shift** while tapping fn | Override: this recording gets the "Anti-Wut" prompt |

The hotkey key, activation mode (push-to-talk / toggle / both), and default cleanup mode are all configurable in **Einstellungen**.

---

## Features

- **On-device speech recognition** — MLX-Whisper Large v3 Turbo runs entirely on your Mac, never uploads audio anywhere.
- **Real-time HUD pill** — bottom-of-screen overlay shows recording state, scrolling waveform, elapsed time, and an X to cancel. Works over fullscreen apps.
- **Three cleanup modes**:
  - **Verbatim** — raw Whisper output, no LLM rewriting.
  - **Formal** — Groq Llama rewrites your speech as polished prose.
  - **Anti-Wut** — same idea, but specifically de-escalates emotionally-charged dictations before paste.
- **Background audio ducking** — Apple Music / Spotify pause automatically while you dictate, resume after.
- **Customizable hotkey** — fn, right-Cmd, or right-Shift; PTT or double-tap toggle.
- **History view** — your last 500 dictations with word counts and weekly stats.
- **Borderless, themed window** — eigene Traffic-Light-Controls, beige card design, no Mac-default chrome clash.

---

## Privacy & data

- **Audio never leaves your machine.** MLX-Whisper is local. Transcription happens before any network call.
- **Cleanup mode (Formal / Anti-Wut)** sends the **transcribed text** (not audio) to Groq. If that worries you, stick to Verbatim mode and Groq is never contacted.
- **History** is stored locally in `~/.worknetic-flow/history.json`. Plain JSON, easy to inspect, easy to delete.
- **No telemetry**, no analytics, no auto-update phone-home.

---

## Troubleshooting

**fn double-tap doesn't do anything.**
Open System Settings → Privacy & Security → **Accessibility** → make sure Flow is in the list and toggled on. If you re-installed the DMG, macOS treats it as a new app and the permission resets — remove the old Flow entry and add the new one.

**Some keyboards don't have an fn key.**
Switch to right-Cmd or right-Shift in **Einstellungen → Aktivierungs-Taste**.

**App says "Flow is damaged and can't be opened" on first launch.**
The DMG isn't notarized yet. Open Terminal and run:
```bash
xattr -cr /Applications/Flow.app
```
This clears macOS's Gatekeeper quarantine flag. Notarization is on the roadmap.

**"GROQ_API_KEY fehlt" notification.**
You haven't entered a Groq key. Either grab one at https://console.groq.com/keys (free tier is plenty for personal use) or just stay in Verbatim mode — it works without any key.

**Pill doesn't show up.**
Click the menubar icon → "Hauptfenster…" → check the **Verlauf** tab. If you see "Noch keine Diktate" but you just dictated, Whisper probably picked up silence — check your microphone input level.

---

## For developers

### Setup

```bash
git clone https://github.com/alpeppo/flow.git
cd flow
uv sync
cp .env.template .env  # optional, only if you want Groq cleanup in dev
uv run python -m wnflow
```

### Build a fresh `.app` bundle

```bash
uv run pyinstaller wnflow.spec --noconfirm
# → dist/Flow.app
```

### Build a release DMG

```bash
mkdir -p /tmp/flow-dmg && cp -R dist/Flow.app /tmp/flow-dmg/
ln -s /Applications /tmp/flow-dmg/Applications
hdiutil create -volname "Flow" -srcfolder /tmp/flow-dmg -ov -format UDZO dist/Flow-0.3.3.dmg
```

### Run the tests

```bash
uv run pytest tests/ -q
```

90 pure-logic tests covering config, hotkey state machine, pipeline routing, Groq client, mic capture, and threading guards. The UI layer (Pill, MainWindow) is verified manually — adding headless tests is on the roadmap.

### Architecture (90-second tour)

- **`src/wnflow/app.py`** — the main orchestrator. Owns the state machine (`BOOT → IDLE → RECORDING → TRANSCRIBING → PASTING`), wires together every other component, runs the NSTimer pump on the main thread.
- **`src/wnflow/hotkey.py`** — pyobjc-based global hotkey listener. pynput doesn't see the fn key on macOS, so we go straight to `NSEvent.addGlobalMonitorForEventsMatchingMask_handler_`.
- **`src/wnflow/mic.py`** — sounddevice capture at 16 kHz mono float32, RMS push to the pill via a deque ring buffer, optional auto-stop timer.
- **`src/wnflow/stt/engine.py`** — MLX-Whisper warmup + transcription.
- **`src/wnflow/pipeline.py`** — STT → mode routing → Groq cleanup → paste-ready text.
- **`src/wnflow/pill.py`** — the floating HUD overlay, custom NSView drawing, X-button hit testing, ESC monitor.
- **`src/wnflow/main_window.py`** — borderless NSWindow + WKWebView. The HTML in `src/wnflow/web/index.html` is the entire UI; Python sends data and receives action callbacks via a `WKScriptMessageHandler`.
- **`src/wnflow/history_store.py`** — append-only JSON history with weekly KPI calculation.

Threading contract: **everything UI lives on the main thread.** Worker queues (`event_queue`, `auto_stop_queue`) plus a `pumpEvents_` NSTimer push events to main. `assert_main_thread()` decorators catch violations early.

### Contributing

PRs welcome. Open an issue first if it's a bigger change. Code style is boring Python with type hints; tests run locally with `uv run pytest`. No CI yet — adding GitHub Actions is on the roadmap.

---

## License

[MIT](LICENSE) © 2026 Tim Pannhausen
