"""Locale detection + translation lookup."""

from unittest.mock import patch

import pytest

import wnflow.i18n as i18n


def test_detect_locale_returns_de_for_german_macos_locale() -> None:
    with patch("wnflow.i18n._read_system_locale", return_value="de_DE"):
        i18n._reset_cache()
        assert i18n.detect_locale() == "de"


def test_detect_locale_returns_de_for_austrian() -> None:
    with patch("wnflow.i18n._read_system_locale", return_value="de_AT"):
        i18n._reset_cache()
        assert i18n.detect_locale() == "de"


def test_detect_locale_returns_en_for_english() -> None:
    with patch("wnflow.i18n._read_system_locale", return_value="en_US"):
        i18n._reset_cache()
        assert i18n.detect_locale() == "en"


def test_detect_locale_returns_en_when_locale_unknown() -> None:
    with patch("wnflow.i18n._read_system_locale", return_value=""):
        i18n._reset_cache()
        assert i18n.detect_locale() == "en"


def test_detect_locale_returns_en_for_french() -> None:
    """Only 'de' gets the German strings; everyone else gets English."""
    with patch("wnflow.i18n._read_system_locale", return_value="fr_FR"):
        i18n._reset_cache()
        assert i18n.detect_locale() == "en"


def test_t_returns_english_default() -> None:
    with patch("wnflow.i18n._read_system_locale", return_value="en_US"):
        i18n._reset_cache()
        assert i18n.t("notify.api_key_missing") == "GROQ_API_KEY missing — cleanup disabled"


def test_t_returns_german_when_locale_de() -> None:
    with patch("wnflow.i18n._read_system_locale", return_value="de_DE"):
        i18n._reset_cache()
        assert i18n.t("notify.api_key_missing") == "GROQ_API_KEY fehlt — Cleanup deaktiviert"


def test_t_unknown_key_returns_key_in_brackets() -> None:
    """Defensive: missing key returns '[key]' instead of crashing."""
    with patch("wnflow.i18n._read_system_locale", return_value="en_US"):
        i18n._reset_cache()
        assert i18n.t("nonexistent.key") == "[nonexistent.key]"


def test_both_languages_have_identical_key_sets() -> None:
    """Every key in EN must exist in DE, and vice versa.
    Prevents accidental drift when adding strings."""
    en = set(i18n.TRANSLATIONS["en"].keys())
    de = set(i18n.TRANSLATIONS["de"].keys())
    missing_in_de = en - de
    missing_in_en = de - en
    assert not missing_in_de, f"Keys missing in DE: {missing_in_de}"
    assert not missing_in_en, f"Keys missing in EN: {missing_in_en}"
