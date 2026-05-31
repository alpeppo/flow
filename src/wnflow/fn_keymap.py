"""macOS fn-Taste System-Belegung erkennen.

macOS speichert die fn-Taste-Aktion in com.apple.HIToolbox/AppleFnUsageType:
    0 = Do Nothing (Flow-kompatibel)
    1 = Show Emoji & Symbols
    2 = Change Input Source
    3 = Start Dictation

Wenn Flow als Hotkey die fn-Taste nutzt und AppleFnUsageType != 0,
kollidiert das mit der System-Aktion. Wir können das nicht selbst
verändern (waere zu invasiv), aber wir können es **erkennen** und
den Nutzer freundlich informieren.
"""

from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


FN_USAGE_VALUES = {
    0: "none",
    1: "emoji",
    2: "input_source",
    3: "dictation",
}


def read_fn_usage() -> int:
    """Returns the current AppleFnUsageType. -1 if not readable."""
    try:
        result = subprocess.run(
            ["defaults", "read", "com.apple.HIToolbox", "AppleFnUsageType"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if result.returncode != 0:
            # Key existiert nicht -> macOS-Default ist effectively 0
            return 0
        return int(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError):
        log.exception("Reading AppleFnUsageType failed")
        return -1


def fn_is_free() -> bool:
    """True wenn die fn-Taste keine System-Aktion ausloest."""
    return read_fn_usage() == 0


def fn_conflict_for(hotkey_key: str) -> dict | None:
    """Returns conflict info if the user's configured hotkey is 'fn'
    and the system has fn assigned to something else.

    Returns None if no conflict.
    Returns {'usage': int, 'label': str} on conflict.
    """
    if hotkey_key != "fn":
        return None
    usage = read_fn_usage()
    if usage <= 0:
        return None
    return {
        "usage": usage,
        "label": FN_USAGE_VALUES.get(usage, "unknown"),
    }


def open_keyboard_settings() -> None:
    """Oeffnet macOS Keyboard-Settings (System Settings → Keyboard).

    Ab macOS Ventura: x-apple.systempreferences:com.apple.Keyboard-Settings.extension
    """
    try:
        subprocess.run(
            ["open", "x-apple.systempreferences:com.apple.Keyboard-Settings.extension"],
            check=False,
            timeout=2.0,
        )
    except Exception:
        log.exception("Opening Keyboard settings failed")
