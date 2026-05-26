"""Menubar via rumps mit Mode-Submenu (v0.2.0).

Verantwortlich für:
- Tray-Icon mit State-abhängigem Text (oder Logo-PNG falls vorhanden)
- Mode-Submenu mit 3 Radio-Items
- Open Config + Quit

WICHTIG: update_state() und set_mode() MÜSSEN vom Main-Thread gerufen werden.
"""

from collections.abc import Callable
from pathlib import Path

import rumps

from wnflow.state import State
from wnflow.threading_guard import assert_main_thread

STATE_ICONS = {
    State.BOOT: "...",
    State.IDLE: "·",
    State.RECORDING: "●",
    State.TRANSCRIBING: "~",
    State.PASTING: "~",
    State.DEGRADED: "!",
}

MODES = ["verbatim", "formal", "rage"]
MODE_LABELS = {
    "verbatim": "Verbatim",
    "formal": "Formal",
    "rage": "Anti-Wut",
}


class MenubarController:
    """Wrappt rumps.App, exposes title-Update + Mode-Selection."""

    def __init__(
        self,
        app: rumps.App,
        on_open_config: Callable[[], None],
        on_quit: Callable[[], None],
        on_mode_change: Callable[[str], None],
        initial_mode: str = "verbatim",
        logo_path: Path | None = None,
    ) -> None:
        self._app = app
        self._on_mode_change = on_mode_change
        self._current_mode = initial_mode
        self._has_logo = False  # rev2 S3-Fix: eigenes Flag statt _icon-Check

        # Logo falls vorhanden, sonst Unicode-Text
        if logo_path is not None and logo_path.exists():
            try:
                self._app.icon = str(logo_path)
                self._app.template = True  # macOS dark/light adaptiv
                self._has_logo = True
            except Exception:
                self._app.title = STATE_ICONS[State.BOOT]
        else:
            self._app.title = STATE_ICONS[State.BOOT]

        # Mode-MenuItems mit Checkmark
        self._mode_items: dict[str, rumps.MenuItem] = {}
        for mode in MODES:
            item = rumps.MenuItem(
                MODE_LABELS[mode],
                callback=self._make_mode_callback(mode),
            )
            if mode == initial_mode:
                item.state = 1  # Checkmark
            self._mode_items[mode] = item

        # Mode-Submenu
        mode_submenu = rumps.MenuItem("Mode")
        for mode in MODES:
            mode_submenu.add(self._mode_items[mode])

        self._app.menu = [
            mode_submenu,
            None,
            rumps.MenuItem("Open Config", callback=lambda _: on_open_config()),
            None,
            rumps.MenuItem("Quit", callback=lambda _: on_quit()),
        ]

    def _make_mode_callback(self, mode: str) -> Callable:
        def cb(_):
            assert_main_thread("MenubarController.mode_callback")
            self._current_mode = mode
            # Checkmarks updaten (radio-button-Verhalten)
            for m, item in self._mode_items.items():
                item.state = 1 if m == mode else 0
            self._on_mode_change(mode)
        return cb

    def update_state(self, state: State) -> None:
        """Setzt Menubar-Title basierend auf State (nur wenn kein Logo gesetzt)."""
        assert_main_thread("MenubarController.update_state")
        # rev2 S3-Fix: eigenes _has_logo Flag statt getattr(_app, "_icon")
        # (das war Halluzination — rumps.App hat kein _icon-Attribut)
        if not self._has_logo:
            self._app.title = STATE_ICONS.get(state, "?")

    def set_mode_checkmark(self, mode: str) -> None:
        """Synchronisiert Checkmark falls Mode extern geändert wurde."""
        assert_main_thread("MenubarController.set_mode_checkmark")
        self._current_mode = mode
        for m, item in self._mode_items.items():
            item.state = 1 if m == mode else 0
