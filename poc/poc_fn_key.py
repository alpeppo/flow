"""POC: Fn-Taste via pyobjc NSEvent erkennen.

pynput kann Fn auf macOS NICHT lesen (HID-Event statt Keyboard-Event).
pyobjc mit NSEvent.addGlobalMonitorForEventsMatchingMask kann das.

Wenn dieser POC funktioniert, ersetzen wir pynput durch pyobjc in hotkey.py.

Erwartete Output:
  PRESS  Fn (modifier flags: 0x800100)
  RELEASE Fn (modifier flags: 0x100)

Beenden via Ctrl+C im Terminal.
"""

import time

from AppKit import (  # type: ignore[import-not-found]
    NSApp,
    NSApplication,
    NSEvent,
    NSEventMaskFlagsChanged,
)
from Foundation import NSObject  # type: ignore[import-not-found]
from PyObjCTools import AppHelper  # type: ignore[import-not-found]

# NSEvent ModifierFlags
NSEventModifierFlagFunction = 1 << 23  # 0x800000 = Fn-Taste

START_TIME = time.perf_counter()
PREVIOUS_FN_STATE = False
LAST_PRESS_TIME = 0.0
DOUBLE_TAP_WINDOW_MS = 350.0
TOGGLE_ACTIVE = False


def on_flags_changed(event) -> None:
    """Wird gefeuert bei jeder Modifier-Taste (Fn, Cmd, Shift, ...).

    Demo-Logik:
    - PRESS / RELEASE wird immer geloggt
    - Doppel-Tipp innerhalb 350ms → TOGGLE_ON
    - Erneutes PRESS waehrend TOGGLE_ON → TOGGLE_OFF
    """
    global PREVIOUS_FN_STATE, LAST_PRESS_TIME, TOGGLE_ACTIVE
    flags = event.modifierFlags()
    fn_pressed = bool(flags & NSEventModifierFlagFunction)
    now_ms = (time.perf_counter() - START_TIME) * 1000

    if fn_pressed == PREVIOUS_FN_STATE:
        return  # Kein Wechsel

    PREVIOUS_FN_STATE = fn_pressed

    if fn_pressed:
        # PRESS
        gap_ms = now_ms - LAST_PRESS_TIME
        is_double_tap = LAST_PRESS_TIME > 0 and gap_ms < DOUBLE_TAP_WINDOW_MS
        LAST_PRESS_TIME = now_ms

        if TOGGLE_ACTIVE:
            TOGGLE_ACTIVE = False
            print(f"  [{now_ms:>7.0f}ms]    PRESS Fn  -> TOGGLE_OFF")
        elif is_double_tap:
            TOGGLE_ACTIVE = True
            print(f"  [{now_ms:>7.0f}ms]    PRESS Fn  -> TOGGLE_ON (double-tap, gap {gap_ms:.0f}ms)")
        else:
            print(f"  [{now_ms:>7.0f}ms]    PRESS Fn")
    else:
        # RELEASE
        if TOGGLE_ACTIVE:
            print(f"  [{now_ms:>7.0f}ms]  RELEASE Fn  (toggle aktiv, ignoriere)")
        else:
            print(f"  [{now_ms:>7.0f}ms]  RELEASE Fn")


def main() -> None:
    print("POC: Fn-Taste mit pyobjc")
    print("=" * 60)
    print("Druecke und lasse Fn-Taste los — sollte 'PRESS Fn' und 'RELEASE Fn' loggen.")
    print("Andere Modifier (Cmd, Shift, ...) werden ignoriert.")
    print("Ctrl+C zum Beenden.")
    print()

    # Globaler Event-Monitor (lauscht auf Events von anderen Apps)
    NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
        NSEventMaskFlagsChanged,
        on_flags_changed,
    )

    # Lokaler Event-Monitor (lauscht auf Events der eigenen App)
    NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
        NSEventMaskFlagsChanged,
        lambda event: (on_flags_changed(event), event)[1],
    )

    # NSApplication-Lifecycle starten (sonst feuert nichts)
    app = NSApplication.sharedApplication()
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
