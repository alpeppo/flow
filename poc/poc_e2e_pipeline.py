"""POC 3: End-to-End Pipeline ohne UI.

Pipeline (entspricht echter App-Codepath):
1. 5s Audio aufnehmen via sounddevice InputStream + Callback (NICHT sd.rec)
2. mlx-whisper transcribe
3. Groq Cleanup
4. Result in Clipboard

Misst Tail-Latenz: Aufnahme-Stop bis Clipboard gesetzt.
PASS-Kriterium: ≤1.2s auf M4.

v2 fix: InputStream + threading verwenden statt sd.rec, weil die echte App
das auch tut. Andere Buffer-Charakteristik, andere Latenz.
"""

import os
import threading
import time
from collections import deque
from pathlib import Path

import httpx
import mlx_whisper
import numpy as np
import pyperclip
import sounddevice as sd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

MODEL = "mlx-community/whisper-large-v3-turbo-q4"
SAMPLE_RATE = 16000
RECORD_SECONDS = 5
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"
HOTWORDS = "Worknetic Ridersystem BZKI Pannhausen"

SYSTEM_PROMPT = """Du erhältst rohes Diktat aus Speech-to-Text. Bereinige es:
- Entferne Füllwörter (äh, ähm, also, halt)
- Korrigiere offensichtliche Grammatik
- Behalte Bedeutung und Stil exakt bei
- Behalte Eigennamen: Worknetic, Ridersystem, BZKI, Pannhausen

Antworte AUSSCHLIESSLICH mit dem bereinigten Text. Keine Anführungszeichen,
keine Erklärung, kein Vor- oder Nachsatz."""


def record_via_inputstream(seconds: int) -> np.ndarray:
    """Aufnahme via InputStream + Callback — wie die echte App."""
    chunks: deque[np.ndarray] = deque()
    lock = threading.Lock()

    def callback(indata, frames, time_info, status):
        if status:
            print(f"    status: {status}")
        with lock:
            chunks.append(indata.copy().flatten())

    print(f"  Aufnahme für {seconds}s... SPRICH JETZT!")
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=callback,
        blocksize=int(SAMPLE_RATE * 0.1),
    )
    stream.start()
    time.sleep(seconds)
    stream.stop()
    stream.close()
    print("  Aufnahme fertig.")

    with lock:
        if not chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(list(chunks))


def transcribe(audio: np.ndarray) -> str:
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=MODEL,
        language="de",
        initial_prompt=HOTWORDS,
        condition_on_previous_text=False,
    )
    return result["text"].strip()


def cleanup(text: str) -> str:
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.0,
        },
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def main() -> None:
    print("POC 3: End-to-End Pipeline")
    print("=" * 60)
    print(f"Modell: {MODEL}")
    print(f"Cleanup: Groq {GROQ_MODEL}")
    print()

    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY nicht in .env gesetzt.")
        print("Erstelle .env aus .env.template und trage deinen Groq-Key ein.")
        return

    # Warmup mlx-whisper (erste Inferenz JIT-compiliert)
    print("Warmup mlx-whisper...")
    silent = np.zeros(SAMPLE_RATE, dtype="float32")
    t0 = time.perf_counter()
    transcribe(silent)
    print(f"  Warmup: {(time.perf_counter()-t0)*1000:.0f}ms")
    print()

    # Recording (via InputStream wie echte App)
    audio = record_via_inputstream(RECORD_SECONDS)
    print()

    # TAIL-LATENZ-Messung beginnt HIER (User hat "aufgehört zu sprechen")
    tail_start = time.perf_counter()

    # STT
    t0 = time.perf_counter()
    raw = transcribe(audio)
    stt_ms = (time.perf_counter() - t0) * 1000
    print(f"  STT: {stt_ms:.0f}ms")
    print(f"  Raw: {raw}")

    # Cleanup
    t0 = time.perf_counter()
    cleaned = cleanup(raw)
    cleanup_ms = (time.perf_counter() - t0) * 1000
    print(f"  Cleanup: {cleanup_ms:.0f}ms")
    print(f"  Cleaned: {cleaned}")

    # Clipboard
    t0 = time.perf_counter()
    pyperclip.copy(cleaned)
    clip_ms = (time.perf_counter() - t0) * 1000
    print(f"  Clipboard: {clip_ms:.0f}ms")

    tail_total_ms = (time.perf_counter() - tail_start) * 1000

    print()
    print("=" * 60)
    print(f"TAIL-LATENZ: {tail_total_ms:.0f}ms (target: ≤1200ms)")
    print(f"  STT:       {stt_ms:.0f}ms")
    print(f"  Cleanup:   {cleanup_ms:.0f}ms")
    print(f"  Clipboard: {clip_ms:.0f}ms")
    print()
    status = "PASS" if tail_total_ms <= 1200 else "FAIL"
    print(f"Status: {status}")
    print()
    print(f"Text im Clipboard. Drücke Cmd+V irgendwo zum Verifizieren.")


if __name__ == "__main__":
    main()
