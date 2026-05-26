"""App-Main: bringt alles zusammen mit striktem Threading-Contract.

Siehe Threading-Modell-Doku im Plan-Header und in threading_guard.py.
ALLE State-Transitions und UI-Updates passieren auf dem Main-Thread.
Workers sammeln Ergebnisse in Queues, Main pumpt + dispatched.
"""

import logging
import queue
import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import pyperclip
import rumps
from dotenv import load_dotenv

from wnflow.cleanup.groq_client import GroqClient
from wnflow.config import load
from wnflow.hotkey import HotkeyListener
from wnflow.menubar import MenubarController
from wnflow.mic import MicCapture
from wnflow.notify import notify, play_done_sound, play_error_sound, play_start_sound
from wnflow.output import OutputInjector
from wnflow.permissions import ensure_permissions
from wnflow.pipeline import Pipeline, PipelineResult
from wnflow.state import State, StateMachine
from wnflow.stt.engine import STTEngine
from wnflow.threading_guard import assert_main_thread

log = logging.getLogger(__name__)

POLL_INTERVAL_S = 0.05  # 50ms — Main-Thread pollt Queues


@dataclass
class BootResult:
    success: bool
    warmup_s: float = 0.0
    error: str = ""


@dataclass
class PipelineDone:
    result: PipelineResult | None = None
    error: str = ""


@dataclass
class PasteDone:
    success: bool = True
    error: str = ""


# Union-Type für result_queue
WorkerResult = Union[BootResult, PipelineDone, PasteDone]


class WnflowApp:
    def __init__(self) -> None:
        load_dotenv()
        self._config = load()
        self._setup_logging()

        log.info("worknetic-flow starting...")

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

        # Queues (alles thread-safe)
        self._event_queue: queue.Queue[str] = queue.Queue()
        self._auto_stop_queue: queue.Queue[str] = queue.Queue()
        self._result_queue: queue.Queue[WorkerResult] = queue.Queue()

        # Mic mit Auto-Stop-Queue
        self._mic = MicCapture(
            self._config.recording,
            auto_stop_queue=self._auto_stop_queue,
        )

        # Executors — separat für Boot, Pipeline, Paste
        # → klare Trennung, keine Future-Verwechslung
        self._boot_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="boot")
        self._pipeline_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")
        self._paste_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paste")

        # Pending Futures (für Done-Polling)
        self._pending_boot: Future[BootResult] | None = None
        self._pending_pipeline: Future[PipelineResult] | None = None
        self._pending_paste: Future[bool] | None = None
        self._last_pipeline_result: PipelineResult | None = None  # für Logging in PASTING

        # Hotkey-Listener
        self._hotkey = HotkeyListener(self._config.hotkey, self._event_queue)

        # rumps App (im Main-Thread)
        self._rumps_app = rumps.App("wnflow", quit_button=None)
        self._menubar = MenubarController(
            self._rumps_app,
            on_open_config=self._open_config,
            on_quit=self._quit,
        )

        # State-Subscriber für Menubar updates
        # State wird AUSSCHLIESSLICH von Main aufgerufen → Subscriber auch Main → safe.
        self._state.subscribe(self._on_state_change)

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

    # =========================================================
    # State-Subscriber (läuft im Main, weil state.try_transition() Main ist)
    # =========================================================

    def _on_state_change(self, old: State, new: State) -> None:
        assert_main_thread("WnflowApp._on_state_change")
        log.info("State: %s → %s", old.name, new.name)
        self._menubar.update_state(new)

    # =========================================================
    # Menu-Callbacks (rumps ruft im Main-Thread auf)
    # =========================================================

    def _open_config(self) -> None:
        assert_main_thread("WnflowApp._open_config")
        path = Path.home() / ".worknetic-flow" / "config.toml"
        subprocess.run(["open", str(path)], check=False)

    def _quit(self) -> None:
        assert_main_thread("WnflowApp._quit")
        log.info("Quitting...")
        self._hotkey.stop()
        # boot_executor wurde nach Boot-Done schon geshutdownt; nochmal ist no-op
        self._boot_executor.shutdown(wait=False)
        self._pipeline_executor.shutdown(wait=False)
        self._paste_executor.shutdown(wait=False)
        rumps.quit_application()

    # =========================================================
    # Boot (im Worker — Main bleibt responsive)
    # =========================================================

    def _kick_off_boot(self, _timer) -> None:
        """Wird einmalig vom rumps.Timer aufgerufen, kickt Boot-Worker an."""
        assert_main_thread("WnflowApp._kick_off_boot")
        _timer.stop()

        if not self._config.cleanup.api_key:
            notify("worknetic-flow", "GROQ_API_KEY fehlt — Cleanup deaktiviert")
            self._config.cleanup.enabled = False

        # Permission-Check (raised wenn fehlend)
        permission_ok = ensure_permissions()
        if not permission_ok:
            notify(
                "worknetic-flow",
                "Berechtigungen fehlen. Öffne Systemeinstellungen → "
                "Datenschutz → Bedienungshilfen + Eingabeüberwachung",
            )
            self._state.try_transition(State.DEGRADED)
            return

        log.info("Starting hotkey listener...")
        try:
            self._hotkey.start()
        except Exception as exc:
            log.exception("Hotkey listener failed")
            notify("worknetic-flow", f"Hotkey-Listener failed: {exc}")
            self._state.try_transition(State.DEGRADED)
            return

        log.info("Submitting model warmup to boot-worker...")
        self._pending_boot = self._boot_executor.submit(self._run_boot_warmup)

    def _run_boot_warmup(self) -> BootResult:
        """Läuft im Boot-Worker-Thread. Lädt mlx-whisper-Modell."""
        try:
            warmup_s = self._stt.warmup()
            return BootResult(success=True, warmup_s=warmup_s)
        except Exception as exc:
            log.exception("Model load failed in boot-worker")
            return BootResult(success=False, error=str(exc))

    def _handle_boot_done(self, result: BootResult) -> None:
        assert_main_thread("WnflowApp._handle_boot_done")
        # Boot-Executor wird nicht mehr gebraucht — shutdown spart einen Thread
        self._boot_executor.shutdown(wait=False)

        if not result.success:
            notify("worknetic-flow", f"Modell-Load fehlgeschlagen: {result.error}")
            self._state.try_transition(State.DEGRADED)
            return

        log.info("Model warmed up in %.1fs", result.warmup_s)
        self._state.try_transition(State.IDLE)
        log.info("worknetic-flow ready. Hotkey: %s", self._config.hotkey.key)

    # =========================================================
    # Event-Pump (Main-Thread, via rumps.Timer alle 50ms)
    # =========================================================

    def _pump_events(self, _timer) -> None:
        assert_main_thread("WnflowApp._pump_events")

        # 1. Hotkey-Events vom Hotkey-Worker
        try:
            while True:
                event = self._event_queue.get_nowait()
                self._handle_hotkey_event(event)
        except queue.Empty:
            pass

        # 2. Auto-Stop-Events vom mic Timer-Thread
        try:
            while True:
                self._auto_stop_queue.get_nowait()
                self._handle_auto_stop()
        except queue.Empty:
            pass

        # 3. Boot-Worker-Done
        if self._pending_boot is not None and self._pending_boot.done():
            future = self._pending_boot
            self._pending_boot = None
            try:
                self._handle_boot_done(future.result())
            except Exception as exc:
                log.exception("Boot future raised")
                self._state.try_transition(State.DEGRADED)

        # 4. Pipeline-Worker-Done
        if self._pending_pipeline is not None and self._pending_pipeline.done():
            future = self._pending_pipeline
            self._pending_pipeline = None
            self._handle_pipeline_done(future)

        # 5. Paste-Worker-Done
        if self._pending_paste is not None and self._pending_paste.done():
            future = self._pending_paste
            self._pending_paste = None
            self._handle_paste_done(future)

    # =========================================================
    # Hotkey-Events (Main-Thread)
    # =========================================================

    def _handle_hotkey_event(self, event: str) -> None:
        assert_main_thread("WnflowApp._handle_hotkey_event")
        if event == "start":
            if self._state.current != State.IDLE:
                log.debug("Hotkey 'start' ignored, state=%s", self._state.current.name)
                return
            if self._state.try_transition(State.RECORDING):
                self._mic.start()
                play_start_sound()
        elif event == "stop":
            # C3-Fix: Guard VOR _mic.stop() — sonst stop() auf nicht-recording mic
            if self._state.current != State.RECORDING:
                log.debug("Hotkey 'stop' ignored, state=%s", self._state.current.name)
                return
            self._consume_recording()

    def _handle_auto_stop(self) -> None:
        """Vom Auto-Stop-Timer ausgelöst nach max_duration_s."""
        assert_main_thread("WnflowApp._handle_auto_stop")
        if self._state.current != State.RECORDING:
            return
        notify("worknetic-flow", f"Max-Aufnahmelänge erreicht — wird verarbeitet")
        self._consume_recording()

    def _consume_recording(self) -> None:
        """Stoppt Mic, prüft Dauer, kickt Pipeline an."""
        assert_main_thread("WnflowApp._consume_recording")
        audio, duration_s = self._mic.stop()
        log.info("Recording stopped: %.2fs, %d samples", duration_s, len(audio))

        if self._mic.is_too_short(duration_s):
            log.info("Silent abort (too short)")
            self._state.try_transition(State.IDLE)
            return

        if not self._state.try_transition(State.TRANSCRIBING):
            return  # State race — abort

        self._pending_pipeline = self._pipeline_executor.submit(
            self._pipeline.process, audio
        )

    # =========================================================
    # Pipeline / Paste (Worker-Results, processed im Main)
    # =========================================================

    def _handle_pipeline_done(self, future: Future[PipelineResult]) -> None:
        assert_main_thread("WnflowApp._handle_pipeline_done")
        try:
            result = future.result()
        except Exception as exc:
            log.exception("Pipeline failed")
            notify("worknetic-flow", f"Transkription fehlgeschlagen: {exc}")
            play_error_sound()
            self._state.try_transition(State.IDLE)
            return

        if not self._state.try_transition(State.PASTING):
            # N3-Fix: State-Race — verloren, aber zurück zu IDLE bringen
            log.warning(
                "Cannot transition to PASTING from %s — recovering to IDLE",
                self._state.current.name,
            )
            notify("worknetic-flow", "State-Race beim Paste — Text verworfen")
            play_error_sound()
            self._state.try_transition(State.IDLE)
            return

        # C2-Fix: paste() läuft im Worker (nicht Main) — sonst 300ms Main-Block
        self._last_pipeline_result = result
        self._pending_paste = self._paste_executor.submit(self._output.paste, result.text)

    def _handle_paste_done(self, future: Future[bool]) -> None:
        assert_main_thread("WnflowApp._handle_paste_done")
        try:
            success = future.result()
        except Exception as exc:
            log.exception("Paste failed")
            notify("worknetic-flow", "Paste fehlgeschlagen")
            play_error_sound()
            self._state.try_transition(State.IDLE)
            return

        if success:
            play_done_sound()
            if self._last_pipeline_result:
                log.info(
                    "Paste done: mode=%s, text_len=%d",
                    self._last_pipeline_result.mode,
                    len(self._last_pipeline_result.text),
                )
        else:
            notify(
                "worknetic-flow",
                "Paste fehlgeschlagen — Text bleibt im Clipboard für manuelles Cmd+V",
            )
            play_error_sound()

        self._last_pipeline_result = None
        self._state.try_transition(State.IDLE)

    # =========================================================
    # Run
    # =========================================================

    def run(self) -> None:
        # Boot-Timer feuert nach 100ms genau einmal
        rumps.Timer(self._kick_off_boot, 0.1).start()
        # Event-Pump-Timer alle 50ms
        rumps.Timer(self._pump_events, POLL_INTERVAL_S).start()
        # Blockierender Main-Loop
        self._rumps_app.run()


def main() -> None:
    app = WnflowApp()
    app.run()
