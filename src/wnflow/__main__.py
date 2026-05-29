"""Entry point: python -m wnflow / PyInstaller-Bundle."""

from wnflow.app import main

if __name__ == "__main__":
    # PyInstaller-Bundle-Fix (POC 0 Lesson):
    # mlx-whisper + multiprocessing forken sich endlos im Bundle, weil
    # jeder Child-Prozess das Bundle-Binary als neuen Main interpretiert.
    # freeze_support() bricht die Endlosschleife. No-op im Dev-Modus.
    import multiprocessing

    multiprocessing.freeze_support()
    main()
