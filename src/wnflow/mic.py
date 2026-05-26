"""Audio-Capture via sounddevice mit Max-Duration-Auto-Stop und RMS-Push.

v0.2.0:
- compute_rms() als pure function
- level_ring (collections.deque maxlen=N) für 50Hz-Pill-Updates
  (B1-Fix aus Spec: deque statt Queue — kein zusätzliches Lock im Callback)

start() öffnet InputStream der Audio-Frames in einen internen Buffer schreibt
und startet einen Timer, der nach `max_duration_s` automatisch ein Event in
`auto_stop_queue` postet.

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


def compute_rms(audio: np.ndarray) -> float:
    """Berechnet RMS-Lautstärke. Defensive: leer/NaN → 0.0."""
    if audio.size == 0:
        return 0.0
    # Filter NaN raus (sounddevice xrun kann NaN liefern)
    if np.isnan(audio).any():
        valid = audio[~np.isnan(audio)]
        if valid.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(valid**2)))
    return float(np.sqrt(np.mean(audio**2)))


class MicCapture:
    def __init__(
        self,
        config: RecordingConfig,
        auto_stop_queue: queue.Queue | None = None,
        level_ring: deque | None = None,
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
        self._level_ring = level_ring  # falls None: kein RMS-Push (v0.1.0-Kompatibilität)

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            log.warning("sounddevice status: %s", status)
        flat = indata.copy().flatten()
        with self._lock:
            self._chunks.append(flat)
        # RMS push (B1-Fix: deque statt Queue — kein zusätzliches Lock)
        if self._level_ring is not None:
            rms = compute_rms(flat)
            self._level_ring.append(rms)

    def _on_auto_stop(self) -> None:
        if self._auto_stop_queue is not None:
            self._auto_stop_queue.put("auto_stop")
            log.info("Max-duration %.1fs erreicht, auto-stop angefordert", self._max_duration_s)

    def start(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._start_time = time.perf_counter()
        # level_ring beim start NICHT clearen — Pill darf alten Wert kurz weiter zeigen
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
            blocksize=int(self._sample_rate * 0.1),
        )
        self._stream.start()
        if self._auto_stop_queue is not None:
            self._auto_stop_timer = threading.Timer(
                self._max_duration_s, self._on_auto_stop
            )
            self._auto_stop_timer.daemon = True
            self._auto_stop_timer.start()

    def stop(self) -> tuple[np.ndarray, float]:
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
