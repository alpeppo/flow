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
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import objc  # type: ignore[import-not-found]
import pyperclip
import rumps
from dotenv import load_dotenv
from Foundation import (  # type: ignore[import-not-found]
    NSObject,
    NSRunLoop,
    NSRunLoopCommonModes,
    NSTimer,
)

from wnflow.cleanup.groq_client import GroqClient
from wnflow.config import load
from wnflow.hotkey import HotkeyListener
from wnflow.menubar import MenubarController
from wnflow.mic import MicCapture
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

        log.info("worknetic-flow v0.2.0 starting...")

        # Domain
        self._state = StateMachine()
        self._stt = STTEngine(self._config.stt, self._config.cleanup.hotwords)
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
        self._done_timer: rumps.Timer | None = None  # rev2 C1-Fix: strong-ref gegen GC

        self._hotkey = HotkeyListener(self._config.hotkey, self._event_queue)

        # Pill (lazy NSWindow-Creation)
        self._pill = PillWindow() if self._config.pill.enabled else None

        # rumps App
        self._rumps_app = rumps.App("wnflow", quit_button=None)
        logo_path = Path(__file__).parent.parent.parent / "brand" / "wnflow_icon_22.png"
        self._menubar = MenubarController(
            self._rumps_app,
            on_open_config=self._open_config,
            on_quit=self._quit,
            on_mode_change=self._on_default_mode_change,
            initial_mode=self._default_mode,
            logo_path=logo_path if logo_path.exists() else None,
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

    def _on_default_mode_change(self, mode: str) -> None:
        assert_main_thread("WnflowApp._on_default_mode_change")
        log.info("Default mode changed: %s → %s", self._default_mode, mode)
        self._default_mode = mode

    def _open_config(self) -> None:
        assert_main_thread("WnflowApp._open_config")
        path = Path.home() / ".worknetic-flow" / "config.toml"
        subprocess.run(["open", str(path)], check=False)

    def _quit(self) -> None:
        assert_main_thread("WnflowApp._quit")
        log.info("Quitting...")
        self._hotkey.stop()
        self._boot_executor.shutdown(wait=False)
        self._pipeline_executor.shutdown(wait=False)
        self._paste_executor.shutdown(wait=False)
        rumps.quit_application()

    # Boot

    def kickOffBoot_(self, _timer):
        """rumps.Timer-Callback. Startet Boot-Worker."""
        assert_main_thread("WnflowApp.kickOffBoot_")
        _timer.stop()  # rumps.Timer has stop(), not invalidate() (NSTimer-API)

        if not self._config.cleanup.api_key:
            notify("worknetic-flow", "GROQ_API_KEY fehlt — Cleanup deaktiviert")
            self._config.cleanup.enabled = False

        if not ensure_permissions():
            notify(
                "worknetic-flow",
                "Berechtigungen fehlen. Systemeinstellungen → Datenschutz → Bedienungshilfen + Eingabeüberwachung",
            )
            self._state.try_transition(State.DEGRADED)
            return

        try:
            self._hotkey.start()
        except Exception as exc:
            log.exception("Hotkey listener failed")
            notify("worknetic-flow", f"Hotkey-Listener failed: {exc}")
            self._state.try_transition(State.DEGRADED)
            return

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

        # 6. Pill-Level-Update (während Recording)
        if (
            self._pill is not None
            and self._state.current == State.RECORDING
            and self._level_ring
        ):
            self._pill.update_level(self._level_ring[-1])

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

        if not self._state.try_transition(State.TRANSCRIBING):
            return

        if self._pill is not None:
            self._pill.update_state(PillState.LOADING)

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
