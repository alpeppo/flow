"""Tests für settings_window.py — pure validation logic.

NSWindow + AppKit-Form-Elements werden manuell validiert (kein Unit-Test).
"""

from wnflow.settings_window import (
    LANGUAGE_OPTIONS,
    language_code_to_index,
    language_index_to_code,
    parse_hotwords,
)


def test_parse_hotwords_strips_whitespace() -> None:
    assert parse_hotwords("  Worknetic  \n  BZKI  ") == ["Worknetic", "BZKI"]


def test_parse_hotwords_drops_empty_lines() -> None:
    assert parse_hotwords("Worknetic\n\n\nBZKI") == ["Worknetic", "BZKI"]


def test_parse_hotwords_empty_input() -> None:
    assert parse_hotwords("") == []
    assert parse_hotwords("   ") == []
    assert parse_hotwords("\n\n") == []


def test_language_options_has_six_eu_langs() -> None:
    """Spec: DE, EN, FR, ES, IT, NL."""
    codes = [code for code, _ in LANGUAGE_OPTIONS]
    assert codes == ["de", "en", "fr", "es", "it", "nl"]


def test_language_code_to_index_round_trip() -> None:
    for idx, (code, _label) in enumerate(LANGUAGE_OPTIONS):
        assert language_code_to_index(code) == idx
        assert language_index_to_code(idx) == code


def test_language_code_to_index_unknown_returns_zero() -> None:
    """Defensive: unbekannter Code → Default-Sprache (Index 0 = Deutsch)."""
    assert language_code_to_index("xx") == 0
