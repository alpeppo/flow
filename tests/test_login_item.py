"""Tests für login_item.py — Bundle-Detection.

SMAppService selbst nicht testen (braucht echtes .app-Bundle + macOS-API).
"""

import sys
from unittest.mock import patch

from wnflow.login_item import is_in_app_bundle, is_login_enabled, set_login_enabled


def test_is_in_app_bundle_false_in_dev() -> None:
    """In Dev-Mode (uv run): nicht im Bundle."""
    # sys.frozen wird von PyInstaller gesetzt, in Dev nicht da
    assert is_in_app_bundle() is False or "Contents/MacOS" in sys.executable


def test_is_login_enabled_false_in_dev() -> None:
    """In Dev-Mode: SMAppService nicht verfügbar → False."""
    with patch("wnflow.login_item.is_in_app_bundle", return_value=False):
        assert is_login_enabled() is False


def test_set_login_enabled_returns_error_in_dev() -> None:
    """In Dev-Mode: graceful-fallback mit Fehlermeldung."""
    with patch("wnflow.login_item.is_in_app_bundle", return_value=False):
        result = set_login_enabled(True)
        assert result is not None  # error-message zurück
        assert "App" in result or "Bundle" in result
