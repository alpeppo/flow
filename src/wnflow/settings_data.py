"""Pure-Helpers für Settings-Werte (keine UI-Abhaengigkeiten).

Hier landen alle datenformenden Funktionen, die fueher in
settings_window.py lagen. Die UI selbst lebt seit v0.3.2 im
Hauptfenster (HTML/JS via main_window.MainWindow).
"""

from __future__ import annotations

LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    ("de", "Deutsch"),
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("nl", "Nederlands"),
]


def parse_hotwords(text: str) -> list[str]:
    """Multi-line text -> list of stripped, non-empty hotwords."""
    return [line.strip() for line in text.split("\n") if line.strip()]


def language_code_to_index(code: str) -> int:
    """ISO-Code -> Dropdown-Index. Unbekannt -> 0 (Default Deutsch)."""
    for idx, (c, _) in enumerate(LANGUAGE_OPTIONS):
        if c == code:
            return idx
    return 0


def language_index_to_code(idx: int) -> str:
    """Dropdown-Index -> ISO-Code. Out-of-range -> 'de'."""
    if 0 <= idx < len(LANGUAGE_OPTIONS):
        return LANGUAGE_OPTIONS[idx][0]
    return "de"
