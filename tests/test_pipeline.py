"""Tests für pipeline.py — STT + Cleanup-Orchestrator mit Mode-Parameter (v0.2.0)."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from wnflow.cleanup.groq_client import GroqError
from wnflow.config import CleanupConfig, CommandsConfig
from wnflow.pipeline import Pipeline


def _make_pipeline(
    stt_output: str = "Schreib mir eine Mail",
    cleanup_output: str = "Schreib mir eine Mail.",
    clipboard: str = "",
    cleanup_raises: Exception | None = None,
) -> tuple[Pipeline, MagicMock, MagicMock]:
    engine = MagicMock()
    engine.transcribe.return_value = stt_output

    groq = MagicMock()
    if cleanup_raises:
        groq.clean.side_effect = cleanup_raises
    else:
        groq.clean.return_value = cleanup_output

    cleanup_cfg = CleanupConfig(enabled=True, hotwords=["Worknetic"])
    commands_cfg = CommandsConfig(enabled=True, triggers=["Befehl:"])
    pipeline = Pipeline(
        stt_engine=engine,
        groq_client=groq,
        cleanup_config=cleanup_cfg,
        commands_config=commands_cfg,
        get_clipboard=lambda: clipboard,
    )
    return pipeline, engine, groq


def test_pipeline_process_accepts_mode_parameter() -> None:
    """v0.2.0: process(audio, mode)."""
    pipeline, _, _ = _make_pipeline()
    result = pipeline.process(np.zeros(16000, dtype=np.float32), mode="verbatim")
    assert result.text == "Schreib mir eine Mail."
    assert result.mode == "verbatim"


def test_verbatim_mode_uses_verbatim_prompt() -> None:
    pipeline, _, groq = _make_pipeline()
    pipeline.process(np.zeros(16000, dtype=np.float32), mode="verbatim")
    # Prüfe dass der system_prompt verbatim-charakteristische Wörter enthält
    call = groq.clean.call_args
    system_prompt = call.kwargs.get("system_prompt") or call.args[0]
    assert "BEHALTE den natürlichen Sprachstil" in system_prompt


def test_formal_mode_uses_formal_prompt() -> None:
    pipeline, _, groq = _make_pipeline()
    pipeline.process(np.zeros(16000, dtype=np.float32), mode="formal")
    call = groq.clean.call_args
    system_prompt = call.kwargs.get("system_prompt") or call.args[0]
    assert "E-Mail" in system_prompt or "Slack" in system_prompt


def test_rage_mode_uses_rage_prompt() -> None:
    pipeline, _, groq = _make_pipeline()
    pipeline.process(np.zeros(16000, dtype=np.float32), mode="rage")
    call = groq.clean.call_args
    system_prompt = call.kwargs.get("system_prompt") or call.args[0]
    assert "Beleidigungen" in system_prompt or "diplomatisch" in system_prompt


def test_unknown_mode_falls_back_to_verbatim() -> None:
    """Defensive: unbekannter Mode → Verbatim als safe default."""
    pipeline, _, groq = _make_pipeline()
    result = pipeline.process(np.zeros(16000, dtype=np.float32), mode="bogus")
    assert result.mode == "verbatim"


def test_groq_error_fallback_to_raw() -> None:
    pipeline, _, _ = _make_pipeline(
        stt_output="Äh schreib mir eine Mail",
        cleanup_raises=GroqError("API down"),
    )
    result = pipeline.process(np.zeros(16000, dtype=np.float32), mode="formal")
    assert result.text == "Äh schreib mir eine Mail"
    # Mode-Suffix bleibt erhalten für Logging-Klarheit
    assert "fallback" in result.mode


def test_command_mode_overrides_diktat_mode() -> None:
    """Trigger-Wort 'Befehl:' aktiviert Command-Mode unabhängig vom mode-Param."""
    pipeline, _, groq = _make_pipeline(
        stt_output="Befehl: mach das kürzer",
        cleanup_output="Kurzer Text.",
        clipboard="Sehr geehrter Herr Müller...",
    )
    result = pipeline.process(np.zeros(16000, dtype=np.float32), mode="formal")
    assert result.text == "Kurzer Text."
    assert result.mode == "command"


def test_cleanup_disabled_returns_raw_stt() -> None:
    engine = MagicMock()
    engine.transcribe.return_value = "Äh schreib mir"
    groq = MagicMock()
    cleanup_cfg = CleanupConfig(enabled=False, hotwords=[])
    commands_cfg = CommandsConfig(enabled=True, triggers=["Befehl:"])
    pipeline = Pipeline(
        stt_engine=engine,
        groq_client=groq,
        cleanup_config=cleanup_cfg,
        commands_config=commands_cfg,
        get_clipboard=lambda: "",
    )
    result = pipeline.process(np.zeros(16000, dtype=np.float32), mode="formal")
    assert result.text == "Äh schreib mir"
    assert not groq.clean.called
