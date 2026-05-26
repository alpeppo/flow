"""POC 2: Hotkey-Detection mit pynput.

Loggt Press/Release-Events für right_cmd + alternative Keys.
Validiert keine missed events, keine TIS/TSM-Warnings.

KRITISCH: Manuelle Test-Szenarien müssen durchgespielt werden:
1. Right-Cmd 30s halten → keine missed events
2. Right-Cmd 10x doppel-tippen (350ms Window) → alle detected
3. Right-Cmd halten + in Notes.app gleichzeitig tippen
   → Triggern Cmd-Shortcuts (Cmd+C, Cmd+V, Cmd+A)?
4. Falls 3 fails: right_shift und f13 testen
"""

import time
from pynput import keyboard

EVENTS = []
START_TIME = time.perf_counter()


def log_event(kind: str, key) -> None:
    elapsed = (time.perf_counter() - START_TIME) * 1000
    EVENTS.append((elapsed, kind, str(key)))
    print(f"  [{elapsed:>7.0f}ms] {kind:>7} {key}")


def on_press(key):
    if key in (keyboard.Key.cmd_r, keyboard.Key.shift_r, keyboard.Key.f13, keyboard.Key.f14):
        log_event("PRESS", key)
    if key == keyboard.Key.esc:
        return False  # stop listener


def on_release(key):
    if key in (keyboard.Key.cmd_r, keyboard.Key.shift_r, keyboard.Key.f13, keyboard.Key.f14):
        log_event("RELEASE", key)


def main() -> None:
    print("POC 2: Hotkey-Detection Test")
    print("=" * 60)
    print("Tracking: cmd_r, shift_r, f13, f14")
    print("ESC zum Beenden")
    print()
    print("Test-Szenarien (manuell durchspielen):")
    print("  1. Right-Cmd 5s halten → erwarte 1 PRESS, 1 RELEASE")
    print("  2. Right-Cmd 5x doppel-tippen (schnell) → 10 PRESS, 10 RELEASE")
    print("  3. WICHTIG: Right-Cmd halten + in Terminal 'abc' tippen")
    print("     Beobachte: Erscheint 'abc' oder werden Cmd-Shortcuts getriggert?")
    print("  4. Wiederhole 1-3 mit Right-Shift, F13, F14")
    print()

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

    print()
    print(f"Total events: {len(EVENTS)}")
    print()
    print("Dokumentiere im RESULTS.md:")
    print("  - Wurden alle Doppel-Tipps detected?")
    print("  - Triggert Right-Cmd parallele Tasten zu Cmd-Shortcuts?")
    print("  - Welcher Key war am stabilsten?")


if __name__ == "__main__":
    main()
