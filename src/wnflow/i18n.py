"""Lightweight internationalization for Flow.

English is canonical. German is provided for users on a macOS locale
starting with `de` (de_DE, de_AT, de_CH). No user toggle — system
locale decides at app startup, cached for the process lifetime.

Usage:

    from wnflow.i18n import t

    notify("Flow", t("notify.api_key_missing"))

In the HTML/JS layer, the same dict is shipped via the
`getLocale` bridge action so the front-end can resolve keys.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Final

log = logging.getLogger(__name__)


def _read_system_locale() -> str:
    """Reads the macOS locale via `defaults`.

    Returns an empty string on any failure so callers can treat it as
    'use the EN default'.
    """
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleLocale"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        log.exception("Reading AppleLocale failed")
        return ""


_cached_locale: str | None = None


def _reset_cache() -> None:
    """Test hook — clears the locale cache so tests can swap the value."""
    global _cached_locale
    _cached_locale = None


def detect_locale() -> str:
    """Returns the active locale string: `de` or `en`. Cached."""
    global _cached_locale
    if _cached_locale is not None:
        return _cached_locale
    raw = _read_system_locale().lower()
    _cached_locale = "de" if raw.startswith("de") else "en"
    return _cached_locale


# Seed translation: Task 2 expands this dict massively.
TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "notify.api_key_missing": "GROQ_API_KEY missing — cleanup disabled",
    },
    "de": {
        "notify.api_key_missing": "GROQ_API_KEY fehlt — Cleanup deaktiviert",
    },
}


def t(key: str) -> str:
    """Returns the translation for `key` in the current locale.
    Unknown keys are returned as `[key]` so missing translations are
    obvious in the UI without crashing."""
    locale = detect_locale()
    table = TRANSLATIONS.get(locale, TRANSLATIONS["en"])
    return table.get(key, f"[{key}]")
