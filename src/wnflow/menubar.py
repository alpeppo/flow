"""Menubar via rumps.

Verantwortlich für:
- Tray-Icon mit State-abhängigem Text
- Menu-Items: Open Config, Quit

WICHTIG: update_state() MUSS vom Main-Thread aufgerufen werden — AppKit-Mutationen
crashen oder warnen aus Worker-Threads. assert_main_thread() setzt das durch.
"""

from collections.abc import Callable

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


class MenubarController:
    """Wrappt rumps.App, exposes title-Update."""

    def __init__(
        self,
        app: rumps.App,
        on_open_config: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._app = app
        self._app.title = STATE_ICONS[State.BOOT]
        self._app.menu = [
            rumps.MenuItem("Open Config", callback=lambda _: on_open_config()),
            None,  # Separator
            rumps.MenuItem("Quit", callback=lambda _: on_quit()),
        ]

    def update_state(self, state: State) -> None:
        """Setzt Menubar-Title basierend auf State.

        MUSS vom Main-Thread gerufen werden — wird durch assert_main_thread
        explizit erzwungen, sonst MainThreadViolation.
        """
        assert_main_thread("MenubarController.update_state")
        self._app.title = STATE_ICONS.get(state, "?")
