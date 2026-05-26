"""Hotkey-Listener via pyobjc NSEvent.

Detektiert PTT (Fn halten) und Toggle (Fn doppel-tippen).
Schreibt Events als Strings in eine thread-safe Queue, die der App-Main-Thread
über rumps.Timer pollt.

WARUM pyobjc statt pynput:
pynput erkennt die Fn-Taste auf macOS nicht (Fn wird als HID-Event statt
Keyboard-Event gesendet). pyobjc mit NSEventModifierFlagFunction kann das.

Events in Queue:
- "start"  — Recording soll starten (PTT-Down oder Toggle-Activate)
- "stop"   — Recording soll stoppen (PTT-Up oder Toggle-Deactivate)

Threading:
- NSEvent-Monitor läuft im Main-Thread (AppHelper.runEventLoop)
- Aber wir behalten die Queue-Schnittstelle für app.py-Konsistenz
- Andere Modifier-Tasten (Cmd, Shift, ...) werden über die unterstützen Keys
  in MODIFIER_FLAGS gemappt und unterstützt
"""

import logging
import queue
import time

from AppKit import (  # type: ignore[import-not-found]
    NSEvent,
    NSEventMaskFlagsChanged,
)

from wnflow.config import HotkeyConfig

log = logging.getLogger(__name__)


# macOS NSEvent ModifierFlags (siehe Apple Developer Docs)
# Wir nutzen nur die rechten Modifier-Varianten wo möglich
NSEventModifierFlagFunction = 1 << 23  # 0x800000 — Fn-Taste
NSEventModifierFlagShift = 1 << 17     # 0x20000 — Shift (LEFT+RIGHT)
NSEventModifierFlagCommand = 1 << 20   # 0x100000 — Cmd (LEFT+RIGHT)
NSEventModifierFlagOption = 1 << 19    # 0x80000 — Option/Alt (LEFT+RIGHT)

# Mapping: config-key-name → NSEventModifierFlag
MODIFIER_FLAGS: dict[str, int] = {
    "fn": NSEventModifierFlagFunction,
    "right_cmd": NSEventModifierFlagCommand,
    "right_shift": NSEventModifierFlagShift,
    "right_option": NSEventModifierFlagOption,
}


class HotkeyListener:
    """pyobjc-basierter Hotkey-Listener.

    Lifecycle:
    - start(): Registriert Global+Local NSEvent-Monitors für FlagsChanged
    - stop(): Hebt Registrierung auf (pyobjc cleanup)

    Wichtig: NSEvent-Monitors brauchen einen laufenden NSRunLoop. Die wird
    durch rumps.App.run() (in app.py) automatisch bereitgestellt — der
    HotkeyListener kann NICHT alleine laufen ohne App.
    """

    def __init__(self, config: HotkeyConfig, event_queue: queue.Queue[str]) -> None:
        if config.key not in MODIFIER_FLAGS:
            raise ValueError(
                f"Unbekannter hotkey.key '{config.key}'. "
                f"Erlaubt: {', '.join(MODIFIER_FLAGS)}"
            )
        self._modifier_flag = MODIFIER_FLAGS[config.key]
        self._mode = config.mode
        self._double_tap_window = config.double_tap_window_ms / 1000.0
        self._queue = event_queue

        # State für Doppel-Tipp + PTT-Tracking
        self._modifier_active = False  # War der Hotkey-Modifier zuletzt gedrückt?
        self._last_tap_time: float = 0.0
        self._toggle_active: bool = False

        # Monitor-Handles (zum späteren Entfernen)
        self._global_monitor = None
        self._local_monitor = None

    def start(self) -> None:
        """Registriert Global- und Local-Monitor für FlagsChanged-Events.

        Global-Monitor: feuert wenn andere App im Vordergrund ist.
        Local-Monitor: feuert wenn diese App im Vordergrund ist.
        Beide nötig damit der Hotkey überall funktioniert.
        """
        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged,
            self._on_flags_changed,
        )
        # Local-Monitor muss Event zurückgeben (sonst wird's geschluckt)
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged,
            lambda event: (self._on_flags_changed(event), event)[1],
        )
        log.info("HotkeyListener started (modifier flag: 0x%x)", self._modifier_flag)

    def stop(self) -> None:
        """Entfernt Monitors."""
        if self._global_monitor is not None:
            NSEvent.removeMonitor_(self._global_monitor)
            self._global_monitor = None
        if self._local_monitor is not None:
            NSEvent.removeMonitor_(self._local_monitor)
            self._local_monitor = None

    def _on_flags_changed(self, event) -> None:
        """Wird vom Main-Thread aufgerufen wenn eine Modifier-Taste sich ändert."""
        flags = event.modifierFlags()
        is_pressed = bool(flags & self._modifier_flag)

        # Nur Übergänge (Press OR Release) verarbeiten
        if is_pressed == self._modifier_active:
            return
        self._modifier_active = is_pressed

        if is_pressed:
            self._handle_press()
        else:
            self._handle_release()

    def _handle_press(self) -> None:
        """Modifier wurde gerade gedrückt."""
        # Toggle-Mode aktiv → erneuter Druck stoppt
        if self._toggle_active:
            self._toggle_active = False
            self._queue.put("stop")
            log.debug("Toggle deactivated")
            return

        # Doppel-Tipp Detection (nur wenn Mode toggle oder both)
        now = time.perf_counter()
        gap = now - self._last_tap_time
        is_double_tap = (
            self._mode in ("toggle", "both")
            and self._last_tap_time > 0
            and gap < self._double_tap_window
        )
        self._last_tap_time = now

        if is_double_tap:
            self._toggle_active = True
            self._queue.put("start")
            log.debug("Toggle activated via double-tap (gap %.0fms)", gap * 1000)
            return

        # PTT-Modus (oder both als 1. Tap eines möglichen Doppel-Tipps)
        if self._mode in ("ptt", "both"):
            self._queue.put("start")
            log.debug("PTT start")

    def _handle_release(self) -> None:
        """Modifier wurde gerade losgelassen."""
        # Im Toggle-Mode wird Release ignoriert (bleibt am)
        if self._toggle_active:
            return

        # PTT-Release → stop
        if self._mode in ("ptt", "both"):
            self._queue.put("stop")
            log.debug("PTT stop")
