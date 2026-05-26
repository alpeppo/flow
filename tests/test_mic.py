"""Tests für mic.py — RMS-Berechnung (pure logic).

InputStream-Integration wird nicht getestet (braucht echtes Mikrofon).
"""

import numpy as np

from wnflow.mic import compute_rms


def test_rms_silence_is_zero() -> None:
    silence = np.zeros(1600, dtype=np.float32)
    assert compute_rms(silence) == 0.0


def test_rms_constant_value() -> None:
    """Konstantes Signal: RMS = abs(value)."""
    signal = np.full(1600, 0.5, dtype=np.float32)
    assert abs(compute_rms(signal) - 0.5) < 1e-6


def test_rms_sine_wave() -> None:
    """Sine-Wave Amplitude 1.0: RMS = 1/sqrt(2) ≈ 0.707."""
    t = np.linspace(0, 1, 1600, dtype=np.float32)
    signal = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    rms = compute_rms(signal)
    assert 0.69 < rms < 0.72


def test_rms_empty_array_returns_zero() -> None:
    """Defensive: leeres Array darf nicht crashen."""
    empty = np.array([], dtype=np.float32)
    assert compute_rms(empty) == 0.0


def test_rms_nan_returns_zero() -> None:
    """Defensive: NaN-Werte (z.B. bei xrun) → 0.0."""
    bad = np.array([np.nan, np.nan], dtype=np.float32)
    assert compute_rms(bad) == 0.0
