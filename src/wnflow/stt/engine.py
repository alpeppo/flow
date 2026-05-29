"""mlx-whisper Wrapper.

v0.3.0 Hard-Break: language und hotwords sind jetzt callable-getters,
gelesen bei jedem transcribe()-Call. Erlaubt Live-Config-Reload ohne Restart.

KEIN Compat-Layer zur v0.2.0-Signatur — v0.2.0-Tag dient als Rollback.
"""

import time
from collections.abc import Callable

import mlx_whisper
import numpy as np


class STTEngine:
    """Wrapper um mlx_whisper.transcribe() mit live-reloadbarer Config."""

    def __init__(
        self,
        model: str,
        language_getter: Callable[[], str],
        hotwords_getter: Callable[[], list[str]],
    ) -> None:
        self._model = model
        self._language_getter = language_getter
        self._hotwords_getter = hotwords_getter
        self._warmed_up = False

    def warmup(self) -> float:
        """Lädt das Modell mit Stille als Warmup-Input. Return Dauer in s."""
        t0 = time.perf_counter()
        silent = np.zeros(16000, dtype=np.float32)
        mlx_whisper.transcribe(
            silent,
            path_or_hf_repo=self._model,
            language=self._language_getter(),
        )
        elapsed = time.perf_counter() - t0
        self._warmed_up = True
        return elapsed

    def transcribe(self, audio: np.ndarray) -> str:
        """Transkribiert float32-Audio-Array (16kHz mono).

        Sprache und Hotwords werden live aus den getters gelesen.
        """
        hotwords = self._hotwords_getter()
        initial_prompt = " ".join(hotwords) if hotwords else None
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self._model,
            language=self._language_getter(),
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,
        )
        return result["text"].strip()
