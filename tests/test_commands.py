"""Tests für commands.py — Trigger-Wort-Detection."""

import pytest

from wnflow.cleanup.commands import Command, detect

TRIGGERS = ["Befehl:", "Mach das", "Übersetze", "Schreib das"]


def test_no_trigger_returns_none() -> None:
    assert detect("Schreib mir eine Mail an Kevin.", TRIGGERS) is None


def test_trigger_at_start_returns_command() -> None:
    cmd = detect("Befehl: mach das kürzer", TRIGGERS)
    assert cmd is not None
    assert cmd.instruction == "mach das kürzer"
    assert cmd.trigger == "Befehl:"


def test_trigger_case_insensitive() -> None:
    cmd = detect("BEFEHL: kürzer machen", TRIGGERS)
    assert cmd is not None
    assert cmd.instruction == "kürzer machen"


def test_trigger_with_leading_whitespace() -> None:
    cmd = detect("   Befehl: kürzer", TRIGGERS)
    assert cmd is not None


def test_trigger_mitten_im_text_returns_none() -> None:
    assert detect("Ich sage Befehl: mach kürzer", TRIGGERS) is None


def test_mach_das_trigger() -> None:
    cmd = detect("Mach das kürzer bitte", TRIGGERS)
    assert cmd is not None
    assert cmd.instruction == "kürzer bitte"
    assert cmd.trigger == "Mach das"


def test_empty_triggers_list_returns_none() -> None:
    assert detect("Befehl: irgendwas", []) is None


def test_empty_text_returns_none() -> None:
    assert detect("", TRIGGERS) is None


def test_trigger_only_with_no_instruction_returns_none() -> None:
    """Nur 'Befehl:' ohne Anweisung dahinter ist kein gültiger Command."""
    assert detect("Befehl:", TRIGGERS) is None
    assert detect("Befehl: ", TRIGGERS) is None
