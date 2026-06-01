"""HotkeyListener has a lock guarding _pending_ptt_timer + _pending_ptt_mode
so the Timer-thread (_fire_pending_ptt) can't race the main-thread press path."""

import queue
import threading

from wnflow.config import HotkeyConfig
from wnflow.hotkey import HotkeyListener


def test_listener_has_a_lock_attribute() -> None:
    listener = HotkeyListener(HotkeyConfig(), queue.Queue())
    assert isinstance(listener._lock, type(threading.Lock()))


def test_lock_is_used_in_handle_press(monkeypatch) -> None:
    """Spy on the lock to confirm _handle_press acquires it during the
    pending-PTT teardown."""
    listener = HotkeyListener(HotkeyConfig(mode="both"), queue.Queue())
    acquired = []
    real_lock = listener._lock

    class SpyLock:
        def __enter__(self_inner):
            acquired.append(True)
            return real_lock.__enter__()
        def __exit__(self_inner, *a):
            return real_lock.__exit__(*a)

    monkeypatch.setattr(listener, "_lock", SpyLock())
    # Simulate a press
    listener._handle_press(mode=None)
    assert len(acquired) >= 1
