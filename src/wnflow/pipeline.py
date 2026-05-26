"""Pipeline-Orchestrator: STT → Command-Detection → Cleanup → Result.

v0.2.0: process() nimmt jetzt `mode`-Parameter ('verbatim'|'formal'|'rage').
Unbekannte Modi → safe default verbatim.

Wird vom App-Main-Loop aufgerufen wenn State zu TRANSCRIBING wechselt.
Läuft im Worker-Thread (über ThreadPoolExecutor) damit Main-Thread frei bleibt.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from wnflow.cleanup.commands import detect
from wnflow.cleanup.groq_client import GroqClient, GroqError
from wnflow.cleanup.prompts import (
    build_command_prompt,
    build_formal_prompt,
    build_rage_prompt,
    build_verbatim_prompt,
)
from wnflow.config import CleanupConfig, CommandsConfig
from wnflow.stt.engine import STTEngine

log = logging.getLogger(__name__)


MODE_BUILDERS = {
    "verbatim": build_verbatim_prompt,
    "formal": build_formal_prompt,
    "rage": build_rage_prompt,
}


@dataclass
class PipelineResult:
    text: str
    mode: str  # "verbatim" | "formal" | "rage" | "*_fallback" | "command" | "command_fallback"
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

    def process(self, audio: np.ndarray, mode: str = "verbatim") -> PipelineResult:
        """STT → Cleanup → Result. Blockierend, im Worker-Thread aufrufen.

        mode: 'verbatim' | 'formal' | 'rage'. Unbekannt → fallback verbatim.
        """
        if mode not in MODE_BUILDERS:
            log.warning("Unknown mode '%s' — falling back to verbatim", mode)
            mode = "verbatim"

        raw = self._stt.transcribe(audio)
        log.info("STT done, mode=%s, raw_len=%d", mode, len(raw))

        if not self._cleanup_cfg.enabled:
            return PipelineResult(text=raw, mode=mode, raw_transcript=raw)

        # Command-Detection (überschreibt mode wenn Trigger gefunden)
        if self._commands_cfg.enabled:
            command = detect(raw, self._commands_cfg.triggers)
            if command and (clipboard := self._get_clipboard()):
                return self._run_command(command.instruction, clipboard, raw)

        return self._run_dictation(raw, mode)

    def _run_dictation(self, raw: str, mode: str) -> PipelineResult:
        builder = MODE_BUILDERS[mode]
        prompt = builder(self._cleanup_cfg.hotwords)
        try:
            cleaned = self._groq.clean(system_prompt=prompt, user_text=raw)
            return PipelineResult(text=cleaned, mode=mode, raw_transcript=raw)
        except GroqError as exc:
            log.warning("Groq cleanup failed (mode=%s), fallback to raw: %s", mode, exc)
            return PipelineResult(text=raw, mode=f"{mode}_fallback", raw_transcript=raw)

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
