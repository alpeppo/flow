"""Pipeline-Orchestrator: STT → Command-Detection → Cleanup → Result.

Wird vom App-Main-Loop aufgerufen wenn State zu TRANSCRIBING wechselt.
Läuft im Worker-Thread (über ThreadPoolExecutor) damit Main-Thread frei bleibt.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from wnflow.cleanup.commands import detect
from wnflow.cleanup.groq_client import GroqClient, GroqError
from wnflow.cleanup.prompts import build_command_prompt, build_dictation_prompt
from wnflow.config import CleanupConfig, CommandsConfig
from wnflow.stt.engine import STTEngine

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    text: str
    mode: str  # "dictation" | "dictation_fallback" | "command" | "command_fallback"
    raw_transcript: str


class Pipeline:
    def __init__(
        self,
        stt_engine: STTEngine,
        groq_client: GroqClient,
        cleanup_config: CleanupConfig,
        commands_config: CommandsConfig,
        get_clipboard: Callable[[], str],
    ) -> None:
        self._stt = stt_engine
        self._groq = groq_client
        self._cleanup_cfg = cleanup_config
        self._commands_cfg = commands_config
        self._get_clipboard = get_clipboard

    def process(self, audio: np.ndarray) -> PipelineResult:
        """STT → Cleanup → Result. Blockierend, im Worker-Thread aufrufen."""
        raw = self._stt.transcribe(audio)
        log.info("STT done, raw_len=%d", len(raw))

        # Cleanup disabled → raw direkt durchreichen
        if not self._cleanup_cfg.enabled:
            return PipelineResult(text=raw, mode="dictation", raw_transcript=raw)

        # Command-Detection
        if self._commands_cfg.enabled:
            command = detect(raw, self._commands_cfg.triggers)
            if command and (clipboard := self._get_clipboard()):
                return self._run_command(command.instruction, clipboard, raw)

        return self._run_dictation(raw)

    def _run_dictation(self, raw: str) -> PipelineResult:
        prompt = build_dictation_prompt(self._cleanup_cfg.hotwords)
        try:
            cleaned = self._groq.clean(system_prompt=prompt, user_text=raw)
            return PipelineResult(text=cleaned, mode="dictation", raw_transcript=raw)
        except GroqError as exc:
            log.warning("Groq cleanup failed, fallback to raw: %s", exc)
            return PipelineResult(text=raw, mode="dictation_fallback", raw_transcript=raw)

    def _run_command(self, instruction: str, target: str, raw: str) -> PipelineResult:
        prompt = build_command_prompt(
            instruction=instruction,
            target_text=target,
            hotwords=self._cleanup_cfg.hotwords,
        )
        try:
            cleaned = self._groq.clean(system_prompt=prompt, user_text=instruction)
            return PipelineResult(text=cleaned, mode="command", raw_transcript=raw)
        except GroqError as exc:
            log.warning("Groq command failed, fallback to raw: %s", exc)
            return PipelineResult(text=raw, mode="command_fallback", raw_transcript=raw)
