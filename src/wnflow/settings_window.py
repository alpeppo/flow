"""Settings-Window via NSWindow + AppKit.

v0.3.0: Native macOS-Fenster für Settings (API-Key, Sprache, Hotwords,
Login-Item-Toggle). Lazy creation beim ersten show().

Save schreibt TOML atomic, callback informiert WnflowApp für Live-Reload.

WICHTIG Threading:
- show/hide/save MÜSSEN vom Main-Thread aufgerufen werden
- Test-Button verwendet Worker-Thread für httpx-Call
"""

import logging
from collections.abc import Callable

import objc  # type: ignore[import-not-found]
from AppKit import (  # type: ignore[import-not-found]
    NSApplication,
    NSBackingStoreBuffered,
    NSBezelBorder,
    NSButton,
    NSColor,
    NSFont,
    NSMakeRect,
    NSPopUpButton,
    NSScrollView,
    NSSecureTextField,
    NSTextField,
    NSTextView,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSObject  # type: ignore[import-not-found]

from wnflow.threading_guard import assert_main_thread

log = logging.getLogger(__name__)


# Spec §3.5: 6 EU-Sprachen
LANGUAGE_OPTIONS = [
    ("de", "Deutsch"),
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("nl", "Nederlands"),
]


def parse_hotwords(text: str) -> list[str]:
    """Multi-line text → list of stripped non-empty hotwords."""
    return [line.strip() for line in text.split("\n") if line.strip()]


def language_code_to_index(code: str) -> int:
    """ISO-Code → Dropdown-Index. Unbekannt → 0 (Default Deutsch)."""
    for idx, (c, _) in enumerate(LANGUAGE_OPTIONS):
        if c == code:
            return idx
    return 0


def language_index_to_code(idx: int) -> str:
    """Dropdown-Index → ISO-Code. Out-of-range → 'de'."""
    if 0 <= idx < len(LANGUAGE_OPTIONS):
        return LANGUAGE_OPTIONS[idx][0]
    return "de"


# NSWindow + Form-Elements — wird in Task 2.2 vervollständigt
class SettingsWindow:
    """Wrapper um NSWindow mit Form-Elements für Settings."""

    def __init__(
        self,
        on_save: Callable[[dict], None],
        on_test_api_key: Callable[[str, Callable[[bool, str], None]], None],
    ) -> None:
        self._on_save = on_save
        self._on_test_api_key = on_test_api_key
        self._controller = None
        self.is_ready = False

    def show(self, initial_values: dict) -> None:
        assert_main_thread("SettingsWindow.show")
        log.warning("SettingsWindow.show: TODO in Task 2.2")
