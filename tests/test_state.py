"""Tests für state.py — State-Machine + erlaubte Übergänge + Re-Trigger-Schutz."""

import pytest

from wnflow.state import State, StateMachine


def test_initial_state_is_boot() -> None:
    sm = StateMachine()
    assert sm.current == State.BOOT


def test_boot_to_idle_on_model_load_ok() -> None:
    sm = StateMachine()
    assert sm.try_transition(State.IDLE) is True
    assert sm.current == State.IDLE


def test_boot_to_degraded_on_model_load_fail() -> None:
    sm = StateMachine()
    assert sm.try_transition(State.DEGRADED) is True
    assert sm.current == State.DEGRADED


def test_idle_to_recording_via_hotkey() -> None:
    sm = StateMachine()
    sm.try_transition(State.IDLE)
    assert sm.try_transition(State.RECORDING) is True
    assert sm.current == State.RECORDING


def test_recording_to_transcribing() -> None:
    sm = _build_recording_state()
    assert sm.try_transition(State.TRANSCRIBING) is True


def test_recording_to_idle_silent_abort() -> None:
    """Bei Recording <0.5s → silent abort zurück zu IDLE."""
    sm = _build_recording_state()
    assert sm.try_transition(State.IDLE) is True


def test_transcribing_to_pasting() -> None:
    sm = _build_transcribing_state()
    assert sm.try_transition(State.PASTING) is True


def test_transcribing_to_idle_on_error() -> None:
    """Wenn STT/Groq komplett fehlschlägt → zurück zu IDLE."""
    sm = _build_transcribing_state()
    assert sm.try_transition(State.IDLE) is True


def test_pasting_to_idle() -> None:
    sm = _build_pasting_state()
    assert sm.try_transition(State.IDLE) is True


def test_re_trigger_during_transcribing_ignored() -> None:
    """Hotkey 'start' während TRANSCRIBING darf State nicht ändern."""
    sm = _build_transcribing_state()
    assert sm.try_transition(State.RECORDING) is False
    assert sm.current == State.TRANSCRIBING


def test_re_trigger_during_pasting_ignored() -> None:
    """Hotkey 'start' während PASTING darf State nicht ändern."""
    sm = _build_pasting_state()
    assert sm.try_transition(State.RECORDING) is False
    assert sm.current == State.PASTING


def test_invalid_transition_returns_false() -> None:
    sm = StateMachine()
    sm.try_transition(State.IDLE)
    # IDLE → PASTING ist verboten
    assert sm.try_transition(State.PASTING) is False
    assert sm.current == State.IDLE


def test_subscriber_called_on_transition() -> None:
    sm = StateMachine()
    received = []
    sm.subscribe(lambda old, new: received.append((old, new)))
    sm.try_transition(State.IDLE)
    sm.try_transition(State.RECORDING)
    assert received == [
        (State.BOOT, State.IDLE),
        (State.IDLE, State.RECORDING),
    ]


def test_subscriber_not_called_on_invalid_transition() -> None:
    sm = StateMachine()
    sm.try_transition(State.IDLE)
    received = []
    sm.subscribe(lambda old, new: received.append((old, new)))
    sm.try_transition(State.PASTING)  # Invalid
    assert received == []


def _build_recording_state() -> StateMachine:
    sm = StateMachine()
    sm.try_transition(State.IDLE)
    sm.try_transition(State.RECORDING)
    return sm


def _build_transcribing_state() -> StateMachine:
    sm = _build_recording_state()
    sm.try_transition(State.TRANSCRIBING)
    return sm


def _build_pasting_state() -> StateMachine:
    sm = _build_transcribing_state()
    sm.try_transition(State.PASTING)
    return sm
