"""Tests fuer fn_keymap.py — pure logic + subprocess mocking."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from wnflow.fn_keymap import (
    FN_USAGE_VALUES,
    fn_conflict_for,
    fn_is_free,
    read_fn_usage,
)


def _mock_defaults(stdout: str, returncode: int = 0):
    """Returns a mock for subprocess.run that mimics `defaults read ...`."""
    result = subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")
    return patch("wnflow.fn_keymap.subprocess.run", return_value=result)


def test_fn_usage_values_includes_all_four_states() -> None:
    assert FN_USAGE_VALUES == {
        0: "none",
        1: "emoji",
        2: "input_source",
        3: "dictation",
    }


def test_read_fn_usage_returns_zero_when_key_missing() -> None:
    """`defaults read` returns non-zero exit when the key doesn't exist;
    treat that as the macOS default (0 = none)."""
    with _mock_defaults(stdout="", returncode=1):
        assert read_fn_usage() == 0


def test_read_fn_usage_parses_integer_stdout() -> None:
    with _mock_defaults(stdout="2\n"):
        assert read_fn_usage() == 2


def test_read_fn_usage_returns_minus_one_on_unparseable_stdout() -> None:
    with _mock_defaults(stdout="not-an-int"):
        assert read_fn_usage() == -1


def test_fn_is_free_true_when_usage_zero() -> None:
    with _mock_defaults(stdout="0"):
        assert fn_is_free() is True


def test_fn_is_free_false_when_emoji_picker() -> None:
    with _mock_defaults(stdout="1"):
        assert fn_is_free() is False


def test_fn_conflict_for_returns_none_when_hotkey_not_fn() -> None:
    # Auch wenn das System fn fuer Emojis nutzt — solange der User
    # right_cmd als Hotkey gewaehlt hat, ist das kein Konflikt.
    with _mock_defaults(stdout="1"):
        assert fn_conflict_for("right_cmd") is None
        assert fn_conflict_for("caps_lock") is None


def test_fn_conflict_for_returns_none_when_fn_is_free() -> None:
    with _mock_defaults(stdout="0"):
        assert fn_conflict_for("fn") is None


def test_fn_conflict_for_emoji() -> None:
    with _mock_defaults(stdout="1"):
        result = fn_conflict_for("fn")
        assert result == {"usage": 1, "label": "emoji"}


def test_fn_conflict_for_input_source() -> None:
    with _mock_defaults(stdout="2"):
        result = fn_conflict_for("fn")
        assert result == {"usage": 2, "label": "input_source"}


def test_fn_conflict_for_dictation() -> None:
    with _mock_defaults(stdout="3"):
        result = fn_conflict_for("fn")
        assert result == {"usage": 3, "label": "dictation"}


def test_fn_conflict_for_unknown_usage_label_falls_back() -> None:
    """Unbekannter Wert (z.B. neues macOS-Release fuegt einen Modus dazu)
    soll trotzdem als Konflikt signalisiert werden, nur mit 'unknown'."""
    with _mock_defaults(stdout="42"):
        result = fn_conflict_for("fn")
        assert result == {"usage": 42, "label": "unknown"}


def test_read_fn_usage_handles_subprocess_error() -> None:
    """Falls subprocess komplett fehlschlaegt (TimeoutExpired etc.),
    nicht crashen — -1 zurueckgeben."""
    with patch(
        "wnflow.fn_keymap.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="defaults", timeout=2.0),
    ):
        assert read_fn_usage() == -1
