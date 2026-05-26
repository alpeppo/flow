"""Audio-Capture via sounddevice mit Max-Duration-Auto-Stop.

start() öffnet InputStream der Audio-Frames in einen internen Buffer schreibt
und startet einen Timer, der nach `max_duration_s` automatisch ein Event in
`auto_stop_queue` postet — der App-Main pollt das und triggert stop().

stop() schließt den Stream und gibt das gesammelte Audio als np.ndarray zurück.

Sample-Rate fix 16kHz mono float32 (Whisper-nativ).
"""

import logging
import queue
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd

from wnflow.config import RecordingConfig

log = logging.getLogger(__name__)


class MicCapture:
    def __init__(
        self,
        config: RecordingConfig,
        auto_stop_queue: queue.Queue[str] | None = None,
    ) -> None:
        self._sample_rate = config.sample_rate
        self._min_duration_s = config.min_duration_s
        self._max_duration_s = config.max_duration_s
        self._chunks: deque[np.ndarray] = deque()
        self._stream: sd.InputStream | None = None
        self._start_time: float | None = None
        self._lock = threading.Lock()
        self._auto_stop_queue = auto_stop_queue
        self._auto_stop_timer: threading.Timer | None = None

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            log.warning("sounddevice status: %s", status)
        with self._lock:
            self._chunks.append(indata.copy().flatten())

    def _on_auto_stop(self) -> None:
        """Vom Timer-Thread aufgerufen wenn max_duration erreicht."""
        if self._auto_stop_queue is not None:
            self._auto_stop_queue.put("auto_stop")
            log.info("Max-duration %.1fs erreicht, auto-stop angefordert", self._max_duration_s)

    def start(self) -> None:
        """Öffnet InputStream. Nicht-blockierend."""
        with self._lock:
            self._chunks.clear()
            self._start_time = time.perf_counter()
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
            blocksize=int(self._sample_rate * 0.1),  # 100ms-Chunks
        )
        self._stream.start()
        # Auto-Stop-Timer starten
        if self._auto_stop_queue is not None:
            self._auto_stop_timer = threading.Timer(
                self._max_duration_s, self._on_auto_stop
            )
            self._auto_stop_timer.daemon = True
            self._auto_stop_timer.start()

    def stop(self) -> tuple[np.ndarray, float]:
        """Schließt Stream. Return (audio_array, duration_s)."""
        # Auto-Stop-Timer abbrechen falls noch aktiv
        if self._auto_stop_timer is not None:
            self._auto_stop_timer.cancel()
            self._auto_stop_timer = None

        if self._stream is None or self._start_time is None:
            return np.array([], dtype=np.float32), 0.0

        self._stream.stop()
        self._stream.close()
        self._stream = None
        duration = time.perf_counter() - self._start_time
        self._start_time = None

        with self._lock:
            if not self._chunks:
                return np.array([], dtype=np.float32), duration
            audio = np.concatenate(list(self._chunks))
            self._chunks.clear()
        return audio, duration

    def is_too_short(self, duration_s: float) -> bool:
        return duration_s < self._min_duration_s

    def is_too_long(self, duration_s: float) -> bool:
        return duration_s >= self._max_duration_s
