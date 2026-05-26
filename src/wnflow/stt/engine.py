"""mlx-whisper Wrapper.

Lädt das Modell einmal beim App-Start (~3-5s Cold-Start, danach in-memory).
transcribe() ist thread-safe und blockiert ~2s auf M4 für 3-5s Audio (POC 1).
"""

import time

import mlx_whisper
import numpy as np

from wnflow.config import STTConfig


class STTEngine:
    """Wrapper um mlx_whisper.transcribe()."""

    def __init__(self, config: STTConfig, hotwords: list[str]) -> None:
        self._model = config.model
        self._language = config.language
        self._initial_prompt = " ".join(hotwords) if hotwords else None
        self._warmed_up = False

    def warmup(self) -> float:
        """Lädt das Modell und macht eine Dummy-Inferenz. Return Dauer in s."""
        t0 = time.perf_counter()
        # 1 Sekunde Stille als Warmup-Input
        silent = np.zeros(16000, dtype=np.float32)
        mlx_whisper.transcribe(
            silent,
            path_or_hf_repo=self._model,
            language=self._language,
        )
        elapsed = time.perf_counter() - t0
        self._warmed_up = True
        return elapsed

    def transcribe(self, audio: np.ndarray) -> str:
        """Transkribiert float32-Audio-Array (16kHz mono).

        Returns bereinigten Text (gestrippt).
        """
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self._model,
            language=self._language,
            initial_prompt=self._initial_prompt,
            condition_on_previous_text=False,  # Reduziert Halluzinationen bei PTT
        )
        return result["text"].strip()
