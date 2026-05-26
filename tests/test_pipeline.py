"""Tests für pipeline.py — orchestriert STT + Cleanup mit Mocks."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from wnflow.cleanup.groq_client import GroqError
from wnflow.config import CleanupConfig, CommandsConfig
from wnflow.pipeline import Pipeline, PipelineResult


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


def test_dictation_mode_returns_cleaned_text() -> None:
    pipeline, _, groq = _make_pipeline(
        stt_output="Äh schreib mir eine Mail",
        cleanup_output="Schreib mir eine Mail.",
    )
    result = pipeline.process(np.zeros(16000, dtype=np.float32))
    assert result.text == "Schreib mir eine Mail."
    assert result.mode == "dictation"
    assert groq.clean.called


def test_dictation_mode_groq_error_falls_back_to_raw() -> None:
    pipeline, _, _ = _make_pipeline(
        stt_output="Äh schreib mir eine Mail",
        cleanup_raises=GroqError("API down"),
    )
    result = pipeline.process(np.zeros(16000, dtype=np.float32))
    assert result.text == "Äh schreib mir eine Mail"
    assert result.mode == "dictation_fallback"


def test_command_mode_with_clipboard_content() -> None:
    pipeline, _, groq = _make_pipeline(
        stt_output="Befehl: mach das kürzer",
        cleanup_output="Kurzer Text.",
        clipboard="Sehr geehrter Herr Müller, ich schreibe Ihnen heute...",
    )
    result = pipeline.process(np.zeros(16000, dtype=np.float32))
    assert result.text == "Kurzer Text."
    assert result.mode == "command"

    # Verifiziere: System-Prompt enthielt Clipboard-Content
    call = groq.clean.call_args
    system_prompt = call.kwargs.get("system_prompt") or call.args[0]
    assert "Sehr geehrter Herr Müller" in system_prompt


def test_command_mode_without_clipboard_falls_back_to_dictation() -> None:
    """Wenn Command-Trigger erkannt aber Clipboard leer, fallback to dictation."""
    pipeline, _, _ = _make_pipeline(
        stt_output="Befehl: mach das kürzer",
        cleanup_output="Mach das kürzer.",
        clipboard="",
    )
    result = pipeline.process(np.zeros(16000, dtype=np.float32))
    assert result.mode == "dictation"


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
    result = pipeline.process(np.zeros(16000, dtype=np.float32))
    assert result.text == "Äh schreib mir"
    assert not groq.clean.called
