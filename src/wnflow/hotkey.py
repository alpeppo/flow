"""Hotkey-Listener via pyobjc NSEvent.

v0.2.0:
- Erweitert: Liest Cmd/Ctrl/Shift parallel zu Fn
- Event-Payload: ("start", mode_or_none) statt nur "start"
- mode_or_none ist 'verbatim' | 'formal' | 'rage' | None
- None heißt "use default" (Main entscheidet anhand _default_mode)
- "mode_hint" event vor "start" für Pill-Color-Pre-Show (S3-Fix)

WARUM pyobjc: pynput erkennt Fn-Taste auf macOS nicht
(POC v0.1.0 hat das validiert).
"""

import logging
import queue
import threading
import time

from AppKit import (  # type: ignore[import-not-found]
    NSEvent,
    NSEventMaskFlagsChanged,
    NSEventModifierFlagCommand,
    NSEventModifierFlagControl,
    NSEventModifierFlagShift,
)

from wnflow.config import HotkeyConfig

log = logging.getLogger(__name__)


# Fn-Taste (NSEventModifierFlagFunction = 1 << 23 = 0x800000)
NSEventModifierFlagFunction = 1 << 23
# Device-Independent-Maske (M3-Fix: rev3 Spec)
NSDeviceIndependentModifierFlagsMask = 0xFFFF0000

# Mapping: config-key-name → NSEventModifierFlag
MODIFIER_FLAGS: dict[str, int] = {
    "fn": NSEventModifierFlagFunction,
    "right_cmd": NSEventModifierFlagCommand,
    "right_shift": NSEventModifierFlagShift,
}


def detect_mode(has_cmd: bool, has_ctrl: bool, has_shift: bool) -> str | None:
    """Mappt Modifier-Status auf Mode (rev3 Spec §3.2).

    - Cmd → 'verbatim' (override)
    - Ctrl → 'formal'
    - Shift → 'rage'
    - Mehrere gleichzeitig → None (use default) + caller logs warning
    - Keine → None (use default)
    """
    mods_count = sum([has_cmd, has_ctrl, has_shift])
    if mods_count > 1:
        return None
    if has_cmd:
        return "verbatim"
    if has_ctrl:
        return "formal"
    if has_shift:
        return "rage"
    return None


class HotkeyListener:
    """pyobjc-basierter Hotkey-Listener mit Mode-Modifier-Detection."""

    def __init__(self, config: HotkeyConfig, event_queue: queue.Queue) -> None:
        if config.key not in MODIFIER_FLAGS:
            raise ValueError(
                f"Unbekannter hotkey.key '{config.key}'. "
                f"Erlaubt: {', '.join(MODIFIER_FLAGS)}"
            )
        self._modifier_flag = MODIFIER_FLAGS[config.key]
        self._mode = config.mode
        self._double_tap_window = config.double_tap_window_ms / 1000.0
        self._queue = event_queue

        self._modifier_active = False
        self._last_tap_time: float = 0.0
        self._toggle_active: bool = False
        # v0.2.1 Debounce: bei mode='both' wird PTT verzögert, damit ein
        # möglicher 2. Tap als Doppel-Tipp erkannt wird (Toggle) statt
        # mit dem 1. PTT zu kollidieren.
        self._pending_ptt_timer: threading.Timer | None = None
        self._pending_ptt_mode: str | None = None

        self._global_monitor = None
        self._local_monitor = None

    def start(self) -> None:
        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged,
            self._on_flags_changed,
        )
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged,
            lambda event: (self._on_flags_changed(event), event)[1],
        )
        log.info("HotkeyListener started (modifier flag: 0x%x)", self._modifier_flag)

    def stop(self) -> None:
        if self._global_monitor is not None:
            NSEvent.removeMonitor_(self._global_monitor)
            self._global_monitor = None
        if self._local_monitor is not None:
            NSEvent.removeMonitor_(self._local_monitor)
            self._local_monitor = None

    def _on_flags_changed(self, event) -> None:
        # M3-Fix: device-independent maskieren
        flags = event.modifierFlags() & NSDeviceIndependentModifierFlagsMask
        is_pressed = bool(flags & self._modifier_flag)

        if is_pressed == self._modifier_active:
            return
        self._modifier_active = is_pressed

        if is_pressed:
            # Mode-Detection NUR beim Press (rev3 Spec §3.2)
            has_cmd = bool(flags & NSEventModifierFlagCommand)
            has_ctrl = bool(flags & NSEventModifierFlagControl)
            has_shift = bool(flags & NSEventModifierFlagShift)

            mods_count = sum([has_cmd, has_ctrl, has_shift])
            if mods_count > 1:
                log.warning(
                    "Multiple modifiers held (cmd=%s ctrl=%s shift=%s) — using default mode",
                    has_cmd, has_ctrl, has_shift,
                )

            mode = detect_mode(has_cmd=has_cmd, has_ctrl=has_ctrl, has_shift=has_shift)
            self._handle_press(mode)
        else:
            self._handle_release()

    def _handle_press(self, mode: str | None) -> None:
        # Toggle-Mode aktiv → 2. Press stoppt
        if self._toggle_active:
            self._toggle_active = False
            self._queue.put(("stop", None))
            # v0.2.1: nach Toggle-Stop _last_tap_time resetten, sonst wird
            # der Stop-Tap als 1. Tap eines neuen Doppel-Tipps registriert.
            self._last_tap_time = 0.0
            log.debug("Toggle deactivated")
            return

        now = time.perf_counter()
        gap = now - self._last_tap_time
        # v0.2.1 State-Race-Fix: Tap-Times älter als 1s gelten als "stale"
        # (z.B. wenn 1. Tap während TRANSCRIBING ignoriert wurde und User
        # später erst den 2. Tap setzt).
        is_double_tap = (
            self._mode in ("toggle", "both")
            and self._last_tap_time > 0
            and gap < self._double_tap_window
        )
        self._last_tap_time = now

        # S3-Fix: mode_hint VOR start posten damit Pill sofort Color zeigen kann
        if mode is not None:
            self._queue.put(("mode_hint", mode))

        if is_double_tap:
            # 2. Tap erkannt — wenn debounced PTT noch pending: canceln
            if self._pending_ptt_timer is not None:
                self._pending_ptt_timer.cancel()
                self._pending_ptt_timer = None
                self._pending_ptt_mode = None
                log.debug("Pending PTT cancelled — toggle wins")
            self._toggle_active = True
            self._queue.put(("start", mode))
            log.debug("Toggle activated via double-tap (gap %.0fms, mode=%s)",
                      gap * 1000, mode)
            return

        # v0.2.1 Debounce für mode='both':
        # PTT verzögert starten, damit ein 2. Tap als Doppel-Tipp erkannt wird.
        # Pure 'ptt'-mode: kein Debounce nötig (Doppel-Tipp ist eh inaktiv).
        if self._mode == "both":
            self._pending_ptt_mode = mode
            self._pending_ptt_timer = threading.Timer(
                self._double_tap_window, self._fire_pending_ptt
            )
            self._pending_ptt_timer.daemon = True
            self._pending_ptt_timer.start()
            log.debug("PTT debounced %dms (mode=%s)",
                      int(self._double_tap_window * 1000), mode)
        elif self._mode == "ptt":
            self._queue.put(("start", mode))
            log.debug("PTT start (mode=%s)", mode)

    def _fire_pending_ptt(self) -> None:
        """Timer-Callback: PTT-Debounce abgelaufen, kein 2. Tap → PTT starten."""
        if not self._modifier_active:
            # User hat schon losgelassen bevor Debounce abgelaufen
            log.debug("Pending PTT skipped — modifier already released")
            self._pending_ptt_timer = None
            self._pending_ptt_mode = None
            return
        mode = self._pending_ptt_mode
        self._pending_ptt_timer = None
        self._pending_ptt_mode = None
        self._queue.put(("start", mode))
        log.debug("Debounced PTT start (mode=%s)", mode)

    def _handle_release(self) -> None:
        # Wenn PTT noch debounced ist (User hat zu kurz gehalten) → cancel,
        # kein start, kein stop. Sieht aus wie ein "Klick" der nichts tut.
        if self._pending_ptt_timer is not None:
            self._pending_ptt_timer.cancel()
            self._pending_ptt_timer = None
            self._pending_ptt_mode = None
            log.debug("PTT release before debounce — cancelled, no recording")
            return

        if self._toggle_active:
            return
        if self._mode in ("ptt", "both"):
            self._queue.put(("stop", None))
            log.debug("PTT stop")
