"""Threading-Contract: alle UI/State-Operationen müssen auf Main-Thread laufen.

Wird in menubar.update_state(), state.try_transition() (von Subscribers),
und allen Stellen aufgerufen, wo AppKit-/State-Mutationen passieren.

Workers nutzen Queues — Main pumpt diese und ruft dann die State-Mutationen.
"""

import threading


class MainThreadViolation(RuntimeError):
    """Erhoben wenn UI/State von einem Worker-Thread mutiert wird."""


def is_main_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


def assert_main_thread(label: str = "") -> None:
    """Raised MainThreadViolation wenn nicht auf Main-Thread.

    `label` hilft beim Debuggen — z.B. "menubar.update_state".
    """
    if not is_main_thread():
        location = f" in {label}" if label else ""
        raise MainThreadViolation(
            f"Threading-Contract verletzt{location}: "
            f"Aufruf aus Thread {threading.current_thread().name}, "
            f"erwartet Main-Thread"
        )
