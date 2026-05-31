"""macOS Notifications + System-Sounds.

Notifications via rumps (osascript fallback wenn rumps nicht passt).
System-Sounds via afplay (lazy, nicht-blockierend).
"""

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

SYSTEM_SOUND_DIR = Path("/System/Library/Sounds")
DEFAULT_SOUND_START = "Tink.aiff"
DEFAULT_SOUND_DONE = "Pop.aiff"
DEFAULT_SOUND_ERROR = "Funk.aiff"


def notify(title: str, message: str) -> None:
    """Zeigt eine macOS Notification.

    Wir benutzen `osascript -e SCRIPT -- arg1 arg2`. Das Script greift
    via `item N of argv` auf die Strings zu, sodass sie als AppleScript-
    `text` ankommen — keine Interpolation in den Script-Body, kein
    Injection-Vektor.
    """
    script = (
        "on run argv\n"
        "  display notification (item 1 of argv) with title (item 2 of argv)\n"
        "end run"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script, "--", message, title],
            check=False,
            timeout=2.0,
            capture_output=True,
        )
    except Exception as exc:
        log.warning("Notification failed: %s", exc)


def play_sound(name: str = DEFAULT_SOUND_DONE) -> None:
    """Spielt System-Sound. Nicht-blockierend (Popen ohne wait)."""
    sound_path = SYSTEM_SOUND_DIR / name
    if not sound_path.exists():
        return
    try:
        subprocess.Popen(
            ["afplay", str(sound_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        log.warning("Sound play failed: %s", exc)


def play_start_sound() -> None:
    play_sound(DEFAULT_SOUND_START)


def play_done_sound() -> None:
    play_sound(DEFAULT_SOUND_DONE)


def play_error_sound() -> None:
    play_sound(DEFAULT_SOUND_ERROR)
