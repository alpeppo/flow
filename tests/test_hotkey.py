"""Tests für hotkey.py — Modifier-Detection (pure logic).

NSEvent-Integration wird nicht testet (braucht NSRunLoop + Permissions).
Validierung: poc/poc_fn_key.py aus v0.1.0 + E2E.
"""

import pytest

from wnflow.hotkey import detect_mode


def test_no_modifier_yields_none() -> None:
    """Fn allein → mode=None (= use default)."""
    assert detect_mode(has_cmd=False, has_ctrl=False, has_shift=False) is None


def test_fn_with_cmd_yields_verbatim() -> None:
    """rev3 Spec: Fn+Cmd = Verbatim-Override."""
    assert detect_mode(has_cmd=True, has_ctrl=False, has_shift=False) == "verbatim"


def test_fn_with_ctrl_yields_formal() -> None:
    assert detect_mode(has_cmd=False, has_ctrl=True, has_shift=False) == "formal"


def test_fn_with_shift_yields_rage() -> None:
    assert detect_mode(has_cmd=False, has_ctrl=False, has_shift=True) == "rage"


def test_cmd_and_ctrl_yields_none() -> None:
    """Multi-Modifier → None + Warning (rev3)."""
    assert detect_mode(has_cmd=True, has_ctrl=True, has_shift=False) is None


def test_ctrl_and_shift_yields_none() -> None:
    assert detect_mode(has_cmd=False, has_ctrl=True, has_shift=True) is None


def test_all_three_modifiers_yields_none() -> None:
    assert detect_mode(has_cmd=True, has_ctrl=True, has_shift=True) is None
