"""POC 1: mlx-whisper Latenz-Benchmark.

Misst Inferenz-Zeit von mlx-whisper large-v3-turbo-q4 auf verschiedenen
Audio-Längen. Validiert dass das Latenz-Ziel auf Tim's M4 erreicht wird.

PASS-Kriterium (M4 Air): <700ms für 3s Audio, <1500ms für 15s Audio.
"""

import statistics
import time
from pathlib import Path

import mlx_whisper

MODEL = "mlx-community/whisper-large-v3-turbo-q4"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
RUNS_PER_FILE = 3
HOTWORDS = "Worknetic Ridersystem BZKI Pannhausen"


def benchmark(audio_path: Path, runs: int) -> dict:
    """Run transcription `runs` times, return stats."""
    durations = []
    text = None
    for i in range(runs):
        t0 = time.perf_counter()
        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=MODEL,
            language="de",
            initial_prompt=HOTWORDS,
            condition_on_previous_text=False,
        )
        elapsed = time.perf_counter() - t0
        durations.append(elapsed)
        text = result["text"].strip()
        print(f"  Run {i+1}/{runs}: {elapsed*1000:.0f}ms")
    return {
        "file": audio_path.name,
        "median_ms": statistics.median(durations) * 1000,
        "min_ms": min(durations) * 1000,
        "max_ms": max(durations) * 1000,
        "text": text,
    }


def main() -> None:
    print(f"Model: {MODEL}")
    print(f"Hotwords: {HOTWORDS}")
    print(f"Runs per file: {RUNS_PER_FILE}\n")

    fixtures = sorted(FIXTURES_DIR.glob("*.wav"))
    if not fixtures:
        print(f"ERROR: No .wav files in {FIXTURES_DIR}")
        print("Erstelle 4 Test-Files in poc/fixtures/:")
        print("  1s.wav   — 'Hallo Kevin'")
        print("  3s.wav   — 'Schreib mir bitte eine kurze Mail'")
        print("  5s.wav   — Sentence ca. 5s")
        print("  15s.wav  — Längeres Absatz-Diktat")
        print("\nTipp: QuickTime Player → Neue Audioaufnahme → exportieren als WAV 16kHz mono")
        return

    # Warmup (first call downloads model + JIT-compiles)
    print(f"Warmup with {fixtures[0].name}...")
    t0 = time.perf_counter()
    mlx_whisper.transcribe(str(fixtures[0]), path_or_hf_repo=MODEL, language="de")
    print(f"  Warmup: {(time.perf_counter()-t0)*1000:.0f}ms\n")

    results = []
    for audio in fixtures:
        print(f"Benchmarking {audio.name}...")
        results.append(benchmark(audio, RUNS_PER_FILE))
        print()

    print("=" * 70)
    print(f"{'File':<20} {'Median':>10} {'Min':>10} {'Max':>10}")
    print("-" * 70)
    for r in results:
        print(f"{r['file']:<20} {r['median_ms']:>8.0f}ms {r['min_ms']:>8.0f}ms {r['max_ms']:>8.0f}ms")
    print("=" * 70)
    print("\nTranscripts:")
    for r in results:
        print(f"  [{r['file']}] {r['text']}")

    print("\n--- PASS-Kriterien (Tim M4 Air) ---")
    for r in results:
        target = None
        if "3s" in r["file"]:
            target = 700
        elif "15s" in r["file"]:
            target = 1500
        if target:
            status = "PASS" if r["median_ms"] < target else "FAIL"
            print(f"  {r['file']}: {r['median_ms']:.0f}ms (target <{target}ms) → {status}")


if __name__ == "__main__":
    main()
