"""Output-Injection: Clipboard preserve + cmd+V senden + Clipboard restore.

WICHTIG: paste() blockiert ~350ms (300ms restore-delay + paste-overhead).
Wird im Worker-Thread (Executor) aufgerufen, nicht im Main-Thread —
sonst würde die rumps.Timer-Event-Pump einfrieren.

Sub-APIs (pyperclip, pynput.Controller) sind aus Worker-Threads sicher
nutzbar: pyperclip nutzt pbcopy/pbpaste-Subprocesses auf macOS,
pynput.Controller postet Events via CGEventPost (thread-safe).
"""

import logging
import time

import pyperclip
from pynput import keyboard

log = logging.getLogger(__name__)


class OutputInjector:
    def __init__(self, restore_delay_ms: int = 300) -> None:
        self._restore_delay = restore_delay_ms / 1000.0
        self._controller = keyboard.Controller()

    def paste(self, text: str) -> bool:
        """Setzt Clipboard auf `text`, sendet cmd+V, restored altes Clipboard.

        Blockierend für ~restore_delay_ms + paste-Overhead (~50ms).
        Im Worker-Thread aufrufen, NICHT im Main-Thread.

        Returns True bei Erfolg, False bei kritischem Fehler.
        """
        try:
            saved = pyperclip.paste()
        except Exception as exc:
            log.warning("Clipboard save failed: %s", exc)
            saved = ""

        try:
            pyperclip.copy(text)
        except Exception as exc:
            log.error("Clipboard set failed: %s", exc)
            return False

        # cmd+V via pynput
        try:
            with self._controller.pressed(keyboard.Key.cmd):
                self._controller.press("v")
                self._controller.release("v")
        except Exception as exc:
            log.error("Paste keystroke failed: %s", exc)
            # Text bleibt im Clipboard, User kann manuell pasten
            return False

        # Warten bis Ziel-App den Paste verarbeitet hat
        time.sleep(self._restore_delay)

        # Clipboard restoren
        try:
            pyperclip.copy(saved)
        except Exception as exc:
            log.warning("Clipboard restore failed: %s", exc)
            # Nicht kritisch — User-Text bleibt verloren im Clipboard

        return True
