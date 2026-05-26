"""State-Machine für worknetic-flow.

Single source of truth für Recording-Lifecycle. Wird ausschließlich vom
Main-Thread mutiert (try_transition). Workers triggern State-Changes nur
indirekt über Queues, die der Main-Thread pumpt.

Vereinfacht v2: Kein separater CLEANING-Zustand. Pipeline cleant in einem
einzigen Worker-Call (STT + Groq). State-Übergang ist:
  BOOT → IDLE → RECORDING → TRANSCRIBING → PASTING → IDLE

Erlaubte Übergänge siehe ALLOWED dict.
"""

from collections.abc import Callable
from enum import Enum, auto
from threading import Lock


class State(Enum):
    BOOT = auto()
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()  # STT + Cleanup laufen in einem Worker
    PASTING = auto()
    DEGRADED = auto()  # STT nicht verfügbar (z.B. Modell-Load fehlgeschlagen)


# Erlaubte State-Übergänge. Alles was hier nicht steht → invalid.
ALLOWED: dict[State, set[State]] = {
    State.BOOT: {State.IDLE, State.DEGRADED},
    State.IDLE: {State.RECORDING},
    State.RECORDING: {State.TRANSCRIBING, State.IDLE},  # IDLE = silent abort
    State.TRANSCRIBING: {State.PASTING, State.IDLE},  # IDLE = pipeline_error
    State.PASTING: {State.IDLE},
    State.DEGRADED: set(),  # Terminal — nur via App-Restart raus
}


Subscriber = Callable[[State, State], None]


class StateMachine:
    """Thread-safe State-Machine mit Subscriber-Pattern.

    Threading-Contract: try_transition() darf nur vom Main-Thread aufgerufen
    werden. Subscribers laufen synchron im aufrufenden Thread (= Main).
    Workers triggern State-Changes indirekt über die Event-Queue im
    App-Main-Loop.
    """

    def __init__(self) -> None:
        self._current = State.BOOT
        self._subscribers: list[Subscriber] = []
        self._lock = Lock()

    @property
    def current(self) -> State:
        with self._lock:
            return self._current

    def try_transition(self, new: State) -> bool:
        """Versucht Übergang zu `new`. Return True wenn erlaubt."""
        with self._lock:
            if new not in ALLOWED.get(self._current, set()):
                return False
            old = self._current
            self._current = new
            subscribers = list(self._subscribers)

        # Subscribers außerhalb des Locks aufrufen
        for cb in subscribers:
            cb(old, new)
        return True

    def subscribe(self, callback: Subscriber) -> None:
        """Registriert Callback der bei jedem erfolgreichen Übergang gerufen wird."""
        with self._lock:
            self._subscribers.append(callback)
