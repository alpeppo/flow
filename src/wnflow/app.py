"""App-Main: bringt alles zusammen mit striktem Threading-Contract.

v0.2.0:
- Hotkey-Events sind jetzt (action, mode_or_none) Tupel
- "mode_hint" event vor "start" für Pill-Pre-Color (S3-Fix)
- _current_mode + _default_mode Properties
- NSTimer in NSRunLoopCommonModes für Pump (B2-Fix)
- Pill integriert: show/hide/update_state/update_level/update_mode
- Level-Ring deque für RMS-Push (B1-Fix)
- Mode-Submenu via MenubarController

Threading bleibt: alle State-Transitions + UI auf Main, Workers in Queues.
"""

import logging
import queue
import subprocess
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import objc  # type: ignore[import-not-found]
import pyperclip
import rumps
from AppKit import (  # type: ignore[import-not-found]
    NSEvent,
    NSEventMaskKeyDown,
)
from dotenv import load_dotenv
from Foundation import (  # type: ignore[import-not-found]
    NSObject,
    NSRunLoop,
    NSRunLoopCommonModes,
    NSTimer,
)

# keyCode 53 = Escape
KEYCODE_ESCAPE = 53

from wnflow import history_store
from wnflow.audio_ducker import AudioDucker
from wnflow.cleanup.groq_client import GroqClient
from wnflow.config import __version__ as _wnflow_version
from wnflow.config import load, save
from wnflow.hotkey import HotkeyListener
from wnflow.login_item import is_login_enabled, set_login_enabled
from wnflow.main_window import MainWindow
from wnflow.menubar import MenubarController
from wnflow.mic import MicCapture, compute_rms
from wnflow.notify import notify, play_done_sound, play_error_sound, play_start_sound
from wnflow.output import OutputInjector
from wnflow.permissions import ensure_permissions
from wnflow.pill import PillState, PillWindow
from wnflow.pipeline import Pipeline, PipelineResult
from wnflow.state import State, StateMachine
from wnflow.stt.engine import STTEngine
from wnflow.threading_guard import assert_main_thread

log = logging.getLogger(__name__)

POLL_INTERVAL_S = 0.02  # 20ms = 50Hz für smooth Waveform

# v0.2.1: RMS-Threshold — Audio leiser als das wird als "Stille" verworfen.
# Verhindert Whisper-Halluzinationen ("ja ja ja", YouTube-Subtitle-Garbage).
# Bei normaler Sprache liegt RMS bei 0.05-0.15, klar oberhalb 0.005.
RMS_SILENCE_THRESHOLD = 0.005


@dataclass
class BootResult:
    success: bool
    warmup_s: float = 0.0
    error: str = ""


WorkerResult = Union[BootResult, None]


class WnflowApp(NSObject):
    """rumps + NSObject hybrid für NSTimer-Selector-Support."""

    def init(self):
        self = objc.super(WnflowApp, self).init()
        if self is None:
            return None
        load_dotenv()
        self._config = load()
        self._setup_logging()

        log.info("worknetic-flow v%s starting...", _wnflow_version)

        # Domain
        self._state = StateMachine()
        self._stt = STTEngine(
            model=self._config.stt.model,
            language_getter=lambda: self._config.stt.language,
            hotwords_getter=lambda: self._config.cleanup.hotwords,
        )
        self._groq = GroqClient(
            api_key=self._config.cleanup.api_key,
            model=self._config.cleanup.model,
            timeout_s=self._config.cleanup.timeout_s,
            retry=self._config.cleanup.retry,
        )
        self._pipeline = Pipeline(
            stt_engine=self._stt,
            groq_client=self._groq,
            cleanup_config=self._config.cleanup,
            commands_config=self._config.commands,
            get_clipboard=pyperclip.paste,
            logging_config=self._config.logging,
        )
        self._output = OutputInjector(
            restore_delay_ms=self._config.output.clipboard_restore_delay_ms
        )

        # Queues
        self._event_queue: queue.Queue = queue.Queue()  # (action, mode)
        self._auto_stop_queue: queue.Queue[str] = queue.Queue()
        self._level_ring: deque = deque(maxlen=4)

        # Mode-Properties
        self._default_mode = self._config.modes.default
        self._current_mode = self._default_mode  # für active recording

        # Mic mit Auto-Stop + Level-Ring
        self._mic = MicCapture(
            self._config.recording,
            auto_stop_queue=self._auto_stop_queue,
            level_ring=self._level_ring,
        )

        # Executors
        self._boot_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="boot")
        self._pipeline_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")
        self._paste_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paste")

        self._pending_boot: Future[BootResult] | None = None
        self._pending_pipeline: Future[PipelineResult] | None = None
        self._pending_paste: Future[bool] | None = None
        self._last_pipeline_result: PipelineResult | None = None
        self._last_recording_duration_s: float = 0.0  # fuer History-Speed-KPI
        self._done_timer: rumps.Timer | None = None  # rev2 C1-Fix: strong-ref gegen GC

        # v0.3.0 S-e Fix: eigener Executor für API-Key-Test
        # (kein Reuse von paste_executor — sonst race-condition zwischen
        # Test-Click und Paste-Operation)
        self._test_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="api-test"
        )

        # v0.3.2: Settings sind jetzt vollstaendig im Hauptfenster integriert
        # (HTML/JS-Form via main_window). settings_window.py wurde entfernt;
        # pure Helpers liegen in settings_data.py.

        self._hotkey = HotkeyListener(self._config.hotkey, self._event_queue)

        # Pill (lazy NSWindow-Creation)
        self._pill = PillWindow() if self._config.pill.enabled else None
        if self._pill is not None:
            # Cancel-Callback wird beim ersten show() in den View injiziert.
            # Hier setzen, damit X-Klick → _request_cancel triggert.
            self._pill.set_cancel_callback(self._request_cancel)

        # Hauptfenster (Verlauf + Tabs). Lazy: NSWindow erst beim ersten Open.
        self._main_window = MainWindow(
            on_load_settings=self._collect_settings_values,
            on_save_settings=self._on_settings_save,
            on_test_api_key=self._on_test_api_key,
            on_open_keyboard_settings=self._open_keyboard_settings,
        )

        # ESC-Hotkey-Monitor (global): laeuft permanent, prueft state.
        self._esc_monitor = None
        # Activation-Observer fuer Dock-Click-Reopen.
        # Wir wollen das Hauptfenster bei JEDER Aktivierung oeffnen, wenn
        # kein anderes Fenster sichtbar ist — auch beim allerersten Launch.
        self._activation_obs = None

        # AudioDucker (mutet Hintergrund waehrend Recording, wenn aktiviert)
        self._audio_ducker = AudioDucker(
            enabled=self._config.audio.mute_background
        )

        # rumps App
        self._rumps_app = rumps.App("wnflow", quit_button=None)
        # Retina-Fix: wir laden das 64px-PNG (3x Retina) und lassen MenubarController
        # das NSImage auf 22pt Display-Groesse skalieren. Das gibt scharfe Darstellung
        # auf Retina-Macs (Down-Sampling 64→44 = scharf, Up-Sampling 22→44 = blurry).
        # Im Bundle liegt 'brand/' direkt unter sys._MEIPASS (Resources/),
        # im Dev-Run unter repo/brand/. Beide Pfade probieren.
        import sys as _sys
        _candidates = []
        meipass = getattr(_sys, "_MEIPASS", None)
        if meipass:
            _candidates.append(Path(meipass) / "brand" / "wnflow_icon_64.png")
        _candidates.append(Path(__file__).parent.parent.parent / "brand" / "wnflow_icon_64.png")
        logo_path = next((p for p in _candidates if p.exists()), None)
        log.info("Menubar logo: %s", logo_path)
        self._menubar = MenubarController(
            self._rumps_app,
            on_open_config=self._open_config,
            on_quit=self._quit,
            on_mode_change=self._on_default_mode_change,
            on_open_settings=self._open_settings,
            on_open_main=self._open_main_window,
            initial_mode=self._default_mode,
            logo_path=logo_path,
        )

        self._state.subscribe(self._on_state_change)
        return self

    def _setup_logging(self) -> None:
        log_dir = Path.home() / ".worknetic-flow" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_level = getattr(logging, self._config.logging.level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(log_dir / "wnflow.log"),
                logging.StreamHandler(),
            ],
        )

    # State + Menu callbacks

    def _on_state_change(self, old: State, new: State) -> None:
        assert_main_thread("WnflowApp._on_state_change")
        log.info("State: %s → %s", old.name, new.name)
        self._menubar.update_state(new)
        # AudioDucker NIE synchron — der Main-Thread darf nicht 2s auf
        # osascript warten. Im Hintergrund-Thread feuern und vergessen.
        if new == State.RECORDING and old != State.RECORDING:
            threading.Thread(
                target=self._audio_ducker.mute, daemon=True,
                name="audio-mute",
            ).start()
        elif old == State.RECORDING and new != State.RECORDING:
            threading.Thread(
                target=self._audio_ducker.restore, daemon=True,
                name="audio-restore",
            ).start()

    def _on_default_mode_change(self, mode: str) -> None:
        assert_main_thread("WnflowApp._on_default_mode_change")
        log.info("Default mode changed: %s → %s", self._default_mode, mode)
        self._default_mode = mode

    def _open_config(self) -> None:
        assert_main_thread("WnflowApp._open_config")
        path = Path.home() / ".worknetic-flow" / "config.toml"
        subprocess.run(["open", str(path)], check=False)

    def _open_main_window(self) -> None:
        assert_main_thread("WnflowApp._open_main_window")
        if self._main_window is None:
            return
        self._main_window.show()

    def _open_keyboard_settings(self) -> None:
        """Bridge-Action: oeffnet die macOS Tastatur-Einstellungen,
        damit der User die fn-Taste-Belegung umstellen kann."""
        assert_main_thread("WnflowApp._open_keyboard_settings")
        from wnflow.fn_keymap import open_keyboard_settings
        open_keyboard_settings()

    def _on_app_did_become_active(self) -> None:
        """Reopen-Handler: bei Dock-Click, Finder-Doppelklick oder
        Cmd-Tab-Aktivierung oeffnen wir das Hauptfenster, sofern aktuell
        kein anderes sichtbar ist. Der Boot-Done-Handler triggert den
        Initial-Open einmal direkt nach Model-Warmup — der hier kuemmert
        sich um spaetere Re-Activations."""
        # Boot kann noch laufen — dann gar nichts oeffnen, das macht
        # _handle_boot_done explizit.
        if self._state.current.name == "BOOT":
            return
        try:
            from AppKit import NSApplication  # type: ignore[import-not-found]
            visible = [w for w in NSApplication.sharedApplication().windows() if w.isVisible()]
            # Pill-NSPanel filtern: hat keinen Titel
            visible = [w for w in visible if w.title() and w.title() != ""]
            if not visible:
                self._open_main_window()
        except Exception:
            log.exception("Reopen handler failed")

    def _quit(self) -> None:
        assert_main_thread("WnflowApp._quit")
        log.info("Quitting...")
        if self._esc_monitor is not None:
            try:
                NSEvent.removeMonitor_(self._esc_monitor)
            except Exception:
                log.exception("ESC monitor remove failed")
            self._esc_monitor = None
        if self._activation_obs is not None:
            try:
                from Foundation import NSNotificationCenter  # type: ignore[import-not-found]
                NSNotificationCenter.defaultCenter().removeObserver_(self._activation_obs)
            except Exception:
                log.exception("Activation observer remove failed")
            self._activation_obs = None
        self._hotkey.stop()
        self._boot_executor.shutdown(wait=False)
        self._pipeline_executor.shutdown(wait=False)
        self._paste_executor.shutdown(wait=False)
        self._test_executor.shutdown(wait=False)  # v0.3.0
        rumps.quit_application()

    # Boot

    def kickOffBoot_(self, _timer):
        """rumps.Timer-Callback. Startet Boot-Worker."""
        assert_main_thread("WnflowApp.kickOffBoot_")
        _timer.stop()  # rumps.Timer has stop(), not invalidate() (NSTimer-API)

        # v0.3.0 Migration-Check: warne wenn alte v0.2.0 launchd-plist da ist
        legacy_plist = Path.home() / "Library/LaunchAgents/de.worknetic.flow.plist"
        if legacy_plist.exists():
            notify(
                "worknetic-flow",
                "v0.2.0 launchd-Agent gefunden. Bitte 'launchctl unload && rm' "
                "und neu starten — sonst laufen 2 Instanzen parallel.",
            )

        if not self._config.cleanup.api_key:
            notify("worknetic-flow", "GROQ_API_KEY fehlt — Cleanup deaktiviert")
            self._config.cleanup.enabled = False

        if not ensure_permissions():
            notify(
                "worknetic-flow",
                "Berechtigungen fehlen. Systemeinstellungen → Datenschutz → Bedienungshilfen + Eingabeüberwachung",
            )
            self._state.try_transition(State.DEGRADED)
            # Trotz DEGRADED: Hauptfenster anzeigen, damit der User die App
            # sieht (sonst wirkt sie tot) und ueber Settings-Tab nachvollziehen
            # kann was fehlt.
            if self._main_window is not None:
                try:
                    self._main_window.show()
                except Exception:
                    log.exception("MainWindow degraded-open failed")
            return

        try:
            self._hotkey.start()
        except Exception as exc:
            log.exception("Hotkey listener failed")
            notify("worknetic-flow", f"Hotkey-Listener failed: {exc}")
            self._state.try_transition(State.DEGRADED)
            if self._main_window is not None:
                try:
                    self._main_window.show()
                except Exception:
                    log.exception("MainWindow degraded-open failed")
            return

        # ESC-Hotkey global: cancelt nur waehrend RECORDING; sonst no-op.
        try:
            self._esc_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown, self._on_global_keydown
            )
            log.info("ESC monitor active (cancel recording)")
        except Exception:
            log.exception("ESC monitor failed (non-fatal — X-Button still works)")

        # Dock-Click-Trigger: wenn der User die App via Dock aktiviert und
        # kein Fenster sichtbar ist, oeffnen wir das Hauptfenster.
        try:
            from Foundation import NSNotificationCenter  # type: ignore[import-not-found]
            self._activation_obs = NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
                "NSApplicationDidBecomeActiveNotification", None, None,
                lambda _note: self._on_app_did_become_active(),
            )
        except Exception:
            log.exception("App-Activation observer failed (non-fatal)")

        log.info("Submitting model warmup...")
        self._pending_boot = self._boot_executor.submit(self._run_boot_warmup)

    def _run_boot_warmup(self) -> BootResult:
        try:
            warmup_s = self._stt.warmup()
            return BootResult(success=True, warmup_s=warmup_s)
        except Exception as exc:
            log.exception("Model load failed")
            return BootResult(success=False, error=str(exc))

    def _handle_boot_done(self, result: BootResult) -> None:
        assert_main_thread("WnflowApp._handle_boot_done")
        self._boot_executor.shutdown(wait=False)

        if not result.success:
            notify("worknetic-flow", f"Modell-Load fehlgeschlagen: {result.error}")
            self._state.try_transition(State.DEGRADED)
            return

        log.info("Model warmed up in %.1fs", result.warmup_s)
        self._state.try_transition(State.IDLE)
        log.info("worknetic-flow ready. Hotkey: %s, Default Mode: %s",
                 self._config.hotkey.key, self._default_mode)

        # Pre-Warm Pill: NSPanel erstellen ohne sie zu zeigen, damit der
        # erste fn-Tap nicht auf lazy-init wartet (~200ms).
        if self._pill is not None:
            try:
                self._pill.update_mode(self._default_mode)  # triggert _ensure_window
            except Exception:
                log.exception("Pill pre-warm failed (non-fatal)")

        # Hauptfenster immer beim Launch oeffnen. Bei First-Run (kein API-Key)
        # direkt auf den Settings-Tab springen, sonst auf den Verlauf-Tab.
        if self._main_window is not None:
            try:
                self._main_window.show()
                if not self._config.cleanup.api_key:
                    log.info("First run detected (no API key) — jumping to Settings tab")
                    self._main_window.activate_tab("settings")
            except Exception:
                log.exception("MainWindow boot-open failed (non-fatal)")

    # Event-Pump (NSTimer in CommonModes — B2-Fix)

    def pumpEvents_(self, _timer):
        assert_main_thread("WnflowApp.pumpEvents_")

        # 1. Hotkey-Events
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._handle_hotkey_event(event)
        except queue.Empty:
            pass

        # 2. Auto-Stop-Events
        try:
            while True:
                self._auto_stop_queue.get_nowait()
                self._handle_auto_stop()
        except queue.Empty:
            pass

        # 3. Boot-Done
        if self._pending_boot is not None and self._pending_boot.done():
            future = self._pending_boot
            self._pending_boot = None
            try:
                self._handle_boot_done(future.result())
            except Exception:
                log.exception("Boot future raised")
                self._state.try_transition(State.DEGRADED)

        # 4. Pipeline-Done
        if self._pending_pipeline is not None and self._pending_pipeline.done():
            future = self._pending_pipeline
            self._pending_pipeline = None
            self._handle_pipeline_done(future)

        # 5. Paste-Done
        if self._pending_paste is not None and self._pending_paste.done():
            future = self._pending_paste
            self._pending_paste = None
            self._handle_paste_done(future)

        # 6. Pill-Level + Timer-Update (waehrend Recording)
        if self._pill is not None and self._state.current == State.RECORDING:
            if self._level_ring:
                self._pill.update_level(self._level_ring[-1])
            start = self._mic.get_start_time()
            if start is not None:
                self._pill.set_elapsed(time.perf_counter() - start)

    def _handle_hotkey_event(self, event: tuple) -> None:
        assert_main_thread("WnflowApp._handle_hotkey_event")
        action, payload = event

        if action == "mode_hint":
            # S3-Fix: Pill schon vor State-Transition mit Mode-Color zeigen
            if self._pill is not None:
                self._pill.update_mode(payload)
            return

        if action == "start":
            if self._state.current != State.IDLE:
                log.debug("Hotkey 'start' ignored, state=%s", self._state.current.name)
                return
            mode = payload if payload is not None else self._default_mode
            self._current_mode = mode

            if self._state.try_transition(State.RECORDING):
                self._mic.start()
                if self._pill is not None:
                    self._pill.show(PillState.RECORDING, mode=mode)
                play_start_sound()

        elif action == "stop":
            if self._state.current != State.RECORDING:
                log.debug("Hotkey 'stop' ignored, state=%s", self._state.current.name)
                return
            self._consume_recording()

    def _handle_auto_stop(self) -> None:
        assert_main_thread("WnflowApp._handle_auto_stop")
        if self._state.current != State.RECORDING:
            return
        notify("worknetic-flow", "Max-Aufnahmelänge erreicht — wird verarbeitet")
        self._consume_recording()

    def _on_global_keydown(self, event) -> None:
        """Globaler KeyDown-Monitor. Reagiert nur auf ESC waehrend RECORDING."""
        try:
            if event.keyCode() != KEYCODE_ESCAPE:
                return
            if self._state.current != State.RECORDING:
                return
            # Cancel-Pfad muss auf Main laufen — wir sind in einem
            # NSEvent-Callback, also bereits auf Main.
            self._request_cancel()
        except Exception:
            log.exception("ESC monitor handler raised")

    def _request_cancel(self) -> None:
        """Bricht die laufende Aufnahme ab. Audio wird verworfen, kein STT."""
        assert_main_thread("WnflowApp._request_cancel")
        if self._state.current != State.RECORDING:
            log.debug("Cancel ignored, state=%s", self._state.current.name)
            return
        log.info("Cancel requested — discarding recording")
        self._mic.discard()
        if self._pill is not None:
            self._pill.hide()
        self._state.try_transition(State.IDLE)

    def _consume_recording(self) -> None:
        assert_main_thread("WnflowApp._consume_recording")
        audio, duration_s = self._mic.stop()
        log.info("Recording stopped: %.2fs, %d samples, mode=%s",
                 duration_s, len(audio), self._current_mode)

        if self._mic.is_too_short(duration_s):
            log.info("Silent abort (too short)")
            if self._pill is not None:
                self._pill.hide()
            self._state.try_transition(State.IDLE)
            return

        # v0.2.1 Halluzinations-Schutz: RMS-Check verhindert dass Whisper aus
        # Stille "ja ja ja" oder YouTube-Subtitle-Garbage halluziniert.
        avg_rms = compute_rms(audio)
        if avg_rms < RMS_SILENCE_THRESHOLD:
            log.info("Silent abort (rms=%.5f < %.5f, no speech detected)",
                     avg_rms, RMS_SILENCE_THRESHOLD)
            if self._pill is not None:
                self._pill.hide()
            self._state.try_transition(State.IDLE)
            return

        if not self._state.try_transition(State.TRANSCRIBING):
            return

        if self._pill is not None:
            self._pill.update_state(PillState.LOADING)

        # Recording-Dauer fuer History/KPI merken
        self._last_recording_duration_s = float(duration_s)

        # Pipeline mit current_mode
        self._pending_pipeline = self._pipeline_executor.submit(
            self._pipeline.process, audio, self._current_mode
        )

    def _handle_pipeline_done(self, future: Future[PipelineResult]) -> None:
        assert_main_thread("WnflowApp._handle_pipeline_done")
        try:
            result = future.result()
        except Exception as exc:
            log.exception("Pipeline failed")
            notify("worknetic-flow", f"Transkription fehlgeschlagen: {exc}")
            play_error_sound()
            if self._pill is not None:
                self._pill.hide()
            self._state.try_transition(State.IDLE)
            return

        if not self._state.try_transition(State.PASTING):
            log.warning("Cannot transition to PASTING from %s — recovering",
                        self._state.current.name)
            notify("worknetic-flow", "State-Race beim Paste")
            play_error_sound()
            if self._pill is not None:
                self._pill.hide()
            self._state.try_transition(State.IDLE)
            return

        self._last_pipeline_result = result
        # History persistieren (best-effort, ohne Blocking)
        try:
            words = len(result.text.split())
            history_store.append(
                text=result.text,
                words=words,
                mode=result.mode,
                duration_s=self._last_recording_duration_s,
            )
            if self._main_window is not None:
                self._main_window.refresh_history()
        except Exception:
            log.exception("history_store.append failed (non-fatal)")
        self._pending_paste = self._paste_executor.submit(self._output.paste, result.text)

    def _handle_paste_done(self, future: Future[bool]) -> None:
        assert_main_thread("WnflowApp._handle_paste_done")
        try:
            success = future.result()
        except Exception:
            log.exception("Paste failed")
            notify("worknetic-flow", "Paste fehlgeschlagen")
            play_error_sound()
            if self._pill is not None:
                self._pill.hide()
            self._state.try_transition(State.IDLE)
            return

        if success and self._last_pipeline_result:
            play_done_sound()
            log.info("Paste done: mode=%s, text_len=%d",
                     self._last_pipeline_result.mode,
                     len(self._last_pipeline_result.text))
            if self._pill is not None:
                self._pill.update_state(PillState.DONE)
                # rev2 C1-Fix: Timer als Instance-Var damit GC ihn nicht killt
                self._done_timer = rumps.Timer(self._hide_pill_after_done, 0.3)
                self._done_timer.start()
        else:
            notify(
                "worknetic-flow",
                "Paste fehlgeschlagen — Text bleibt im Clipboard für manuelles Cmd+V",
            )
            play_error_sound()
            if self._pill is not None:
                self._pill.hide()

        self._last_pipeline_result = None
        self._state.try_transition(State.IDLE)

    def _hide_pill_after_done(self, timer) -> None:
        """rumps.Timer-Callback. Hide Pill nach Done-Anzeige."""
        timer.stop()
        self._done_timer = None  # rev2 C1-Fix: ref freigeben
        if self._pill is not None:
            self._pill.hide()

    def _open_settings(self) -> None:
        """Oeffnet das Hauptfenster und wechselt zum Settings-Tab.
        (Frueher: separates SettingsWindow — jetzt in der UI integriert.)"""
        assert_main_thread("WnflowApp._open_settings")
        if self._main_window is None:
            return
        self._main_window.show()
        self._main_window.activate_tab("settings")

    def _collect_settings_values(self) -> dict:
        """Liefert das initial-values-Dict fuer das Settings-Form im HTML."""
        from wnflow.settings_data import LANGUAGE_OPTIONS
        from wnflow.menubar import MODE_LABELS, MODES
        from wnflow.fn_keymap import fn_conflict_for
        mode_options = [[m, MODE_LABELS.get(m, m)] for m in MODES]
        # Reihenfolge: empfohlene Modifier zuerst, fn am Ende (kann durch
        # macOS-Emoji-Funktion blockiert sein).
        hotkey_key_options = [
            ["fn", "fn (Funktions-Taste)"],
            ["right_cmd", "Rechte Cmd-Taste"],
            ["right_shift", "Rechte Shift-Taste"],
            ["right_option", "Rechte Option-Taste"],
            ["caps_lock", "Caps Lock"],
        ]
        return {
            "api_key": self._config.cleanup.api_key or "",
            "language": self._config.stt.language,
            "hotwords": list(self._config.cleanup.hotwords or []),
            "login_item": is_login_enabled(),
            "mute_background": self._config.audio.mute_background,
            "language_options": list(LANGUAGE_OPTIONS),
            # Modi + Hotkey
            "default_mode": self._config.modes.default,
            "mode_options": mode_options,
            "hotkey_key": self._config.hotkey.key,
            "hotkey_mode": self._config.hotkey.mode,
            "hotkey_key_options": hotkey_key_options,
            "double_tap_window_ms": int(self._config.hotkey.double_tap_window_ms),
            # macOS-fn-Konflikt-Hint (v0.3.5)
            "fn_conflict": fn_conflict_for(self._config.hotkey.key),
        }

    def _on_settings_save(self, values: dict) -> None:
        """Callback wenn der Settings-Tab 'Speichern' triggert."""
        assert_main_thread("WnflowApp._on_settings_save")
        log.info(
            "Settings save: language=%s, hotwords=%d, login_item=%s, mute_bg=%s, "
            "default_mode=%s, hotkey=%s/%s, dtw=%d",
            values.get("language"), len(values.get("hotwords") or []),
            values.get("login_item"), values.get("mute_background", False),
            values.get("default_mode"), values.get("hotkey_key"),
            values.get("hotkey_mode"), values.get("double_tap_window_ms", 0),
        )

        # Config-State updaten
        self._config.cleanup.api_key = values["api_key"]
        self._config.stt.language = values["language"]
        self._config.cleanup.hotwords = values["hotwords"]
        self._config.audio.mute_background = values.get("mute_background", False)

        # Modi + Hotkey
        new_default_mode = values.get("default_mode")
        if new_default_mode:
            self._config.modes.default = new_default_mode

        old_hotkey = (
            self._config.hotkey.key,
            self._config.hotkey.mode,
            self._config.hotkey.double_tap_window_ms,
        )
        new_hotkey_key = values.get("hotkey_key") or self._config.hotkey.key
        new_hotkey_mode = values.get("hotkey_mode") or self._config.hotkey.mode
        new_dtw = int(values.get("double_tap_window_ms") or self._config.hotkey.double_tap_window_ms)
        # Validierung: nur erlaubte Werte uebernehmen
        from wnflow.hotkey import MODIFIER_FLAGS
        if new_hotkey_key in MODIFIER_FLAGS:
            self._config.hotkey.key = new_hotkey_key
        if new_hotkey_mode in ("ptt", "toggle", "both"):
            self._config.hotkey.mode = new_hotkey_mode
        self._config.hotkey.double_tap_window_ms = max(150, min(600, new_dtw))

        # TOML schreiben
        try:
            save(self._config)
        except Exception as exc:
            log.exception("Config save failed")
            notify("worknetic-flow", f"Settings-Speichern fehlgeschlagen: {exc}")
            return

        # Cleanup wieder aktivieren falls jetzt API-Key da
        if self._config.cleanup.api_key:
            self._config.cleanup.enabled = True

        # Groq-Client mit neuem Key neu instanziieren
        self._groq = GroqClient(
            api_key=self._config.cleanup.api_key,
            model=self._config.cleanup.model,
            timeout_s=self._config.cleanup.timeout_s,
            retry=self._config.cleanup.retry,
        )
        # Pipeline mit neuem Groq-Client neu binden (S-d Fix: Setter)
        self._pipeline.set_groq_client(self._groq)

        # Login-Item synchronisieren
        err = set_login_enabled(values["login_item"])
        if err is not None:
            log.warning("Login-Item-Setzen fehlgeschlagen: %s", err)

        # AudioDucker Live-Reload (Toggle wirkt ab naechstem Recording)
        self._audio_ducker.set_enabled(self._config.audio.mute_background)

        # Default-Mode in Menubar widerspiegeln
        if new_default_mode:
            self._default_mode = new_default_mode
            try:
                self._menubar.set_mode_checkmark(new_default_mode)
            except Exception:
                log.exception("Menubar mode-checkmark sync failed")

        # Hotkey-Listener neu binden, wenn sich was geaendert hat
        new_hotkey = (
            self._config.hotkey.key,
            self._config.hotkey.mode,
            self._config.hotkey.double_tap_window_ms,
        )
        if old_hotkey != new_hotkey:
            try:
                self._hotkey.stop()
                self._hotkey = HotkeyListener(self._config.hotkey, self._event_queue)
                self._hotkey.start()
                log.info("HotkeyListener re-bound: key=%s, mode=%s, dtw=%d",
                         *new_hotkey)
            except Exception:
                log.exception("Hotkey re-bind failed — please restart Flow")
                notify("Flow", "Hotkey-Aenderung wirkt nach Neustart")

        notify("Flow", "Einstellungen gespeichert")

    def _on_test_api_key(self, key: str, result_callback) -> None:
        """Worker-Thread: testet API-Key via minimalem Groq-Request.

        S-h Fix: Direkt httpx.post mit max_tokens=5, nicht GroqClient.clean
        (sonst voller 70B-Roundtrip mit ~1-3s Latenz statt <500ms).
        S-e Fix: Nutzt eigenen _test_executor, nicht paste_executor.
        """
        def worker():
            try:
                import httpx
                response = httpx.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": self._config.cleanup.model,
                        "messages": [
                            {"role": "system", "content": "Antworte mit OK."},
                            {"role": "user", "content": "Test"},
                        ],
                        "max_tokens": 5,
                        "temperature": 0.0,
                    },
                    timeout=5.0,
                )
                if response.status_code == 200:
                    result_callback(True, "Valide")
                elif response.status_code == 401:
                    result_callback(False, "Key ungültig")
                else:
                    result_callback(False, f"HTTP {response.status_code}")
            except httpx.TimeoutException:
                result_callback(False, "Timeout")
            except httpx.RequestError as exc:
                result_callback(False, f"Verbindungsfehler: {str(exc)[:60]}")
            except Exception as exc:
                result_callback(False, f"Fehler: {str(exc)[:80]}")

        self._test_executor.submit(worker)

    def run(self) -> None:
        # Boot-Timer als Instance-Var (rev2 defensive: GC-safe)
        self._boot_timer = rumps.Timer(self.kickOffBoot_, 0.1)
        self._boot_timer.start()

        # NSTimer-Pump in CommonModes — B2-Fix
        # rev2: als Instance-Var (defensive gegen GC)
        self._pump_timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            POLL_INTERVAL_S, self, "pumpEvents:", None, True
        )
        NSRunLoop.currentRunLoop().addTimer_forMode_(self._pump_timer, NSRunLoopCommonModes)

        # rumps.App.run() blockiert
        self._rumps_app.run()


def main() -> None:
    app = WnflowApp.alloc().init()
    app.run()
