"""POC 0: Validiert PyInstaller + mlx-whisper + ad-hoc Codesigning.

Lädt mlx-whisper, transkribiert eine WAV-Datei, druckt Resultat.
Soll als PyInstaller-Bundle laufen — wenn nicht: DMG-Installer-Fallback nötig.

PASS-Kriterien:
- .app baut ohne Fehler
- .app startet ohne Crash
- Transkription liefert Text (nicht leer, nicht crash)
- codesign --verify zeigt valide ad-hoc-Signatur
"""

import sys
import time
from pathlib import Path


def main() -> None:
    print("POC 0: PyInstaller + mlx-whisper + Codesigning")
    print("=" * 60)

    # Bundle-Info zuerst (damit wir sehen wenn import fehlt)
    print(f"sys.executable: {sys.executable}")
    print(f"__file__: {__file__}")
    print(f"frozen: {getattr(sys, 'frozen', False)}")
    print()

    # Modell-Check
    print("Lade mlx-whisper...")
    try:
        import mlx_whisper  # noqa: F401
        print(f"mlx-whisper Pfad: {mlx_whisper.__file__}")
    except ImportError as exc:
        print(f"FAIL: mlx-whisper Import: {exc}")
        sys.exit(2)

    # Audio-Fixture finden — im Bundle liegt es im _MEIPASS-Ordner
    if getattr(sys, "frozen", False):
        # PyInstaller-Bundle
        bundle_dir = Path(sys._MEIPASS)
        audio_file = bundle_dir / "fixtures" / "3s.wav"
    else:
        # Dev-Mode
        audio_file = Path(__file__).parent / "fixtures" / "3s.wav"

    if not audio_file.exists():
        print(f"FAIL: {audio_file} nicht vorhanden")
        print("Erst aus v0.2.0-POC kopieren oder neu aufnehmen.")
        sys.exit(1)

    print(f"Audio: {audio_file}")

    # Transkribieren
    print("Starte Transkription...")
    t0 = time.perf_counter()
    try:
        result = mlx_whisper.transcribe(
            str(audio_file),
            path_or_hf_repo="mlx-community/whisper-large-v3-turbo-q4",
            language="de",
        )
    except Exception as exc:
        print(f"FAIL: mlx_whisper.transcribe crashte: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(3)

    elapsed = (time.perf_counter() - t0) * 1000
    text = result["text"].strip()
    print(f"Inferenz: {elapsed:.0f}ms")
    print(f"Result: {text!r}")

    if not text:
        print("FAIL: leeres Result")
        sys.exit(4)

    print()
    print("=" * 60)
    print("PASS: POC 0 erfolgreich")


if __name__ == "__main__":
    # PyInstaller-Bundle-Fix: mlx + multiprocessing forken sich endlos
    # ohne freeze_support, weil jeder Child-Prozess das Bundle-Binary als
    # "neuen Main" interpretiert. freeze_support() bricht den Loop.
    import multiprocessing
    multiprocessing.freeze_support()
    main()
