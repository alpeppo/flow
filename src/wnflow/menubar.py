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

from wnflow.i18n import t
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


def mode_label(mode: str) -> str:
    """Returns the localized label for a mode code.

    Function, not a dict, so the locale is re-resolved every call.
    Tests rely on this — see test_i18n.test_menubar_mode_label_*.
    """
    return t(f"menubar.mode.{mode}")


class MenubarController:
    """Wrappt rumps.App, exposes title-Update + Mode-Selection."""

    def __init__(
        self,
        app: rumps.App,
        on_open_config: Callable[[], None],
        on_quit: Callable[[], None],
        on_mode_change: Callable[[str], None],
        on_open_settings: Callable[[], None],
        on_open_main: Callable[[], None] | None = None,
        initial_mode: str = "verbatim",
        logo_path: Path | None = None,
    ) -> None:
        self._app = app
        self._on_mode_change = on_mode_change
        self._current_mode = initial_mode
        self._has_logo = False  # rev2 S3-Fix: eigenes Flag statt _icon-Check
        # Keep callbacks so rebuild_menu() can re-wire them after locale change.
        self._on_open_config = on_open_config
        self._on_quit = on_quit
        self._on_open_settings = on_open_settings
        self._on_open_main = on_open_main

        # Logo falls vorhanden, sonst Unicode-Text
        if logo_path is not None and logo_path.exists():
            try:
                self._app.icon = str(logo_path)
                # template=False: farbiges Icon (Squircle beige + Soundwave),
                # kein automatisches dark/light-Invertieren.
                self._app.template = False
                self._has_logo = True
                # Retina-Fix: rumps lädt das PNG als NSImage mit Pixel-Größe.
                # Bei 22px-PNG auf Retina-Display interpretiert macOS das als
                # 22pt-Bild und skaliert auf 44px hoch → unscharf. Wir setzen
                # _icon_nsimage explizit auf 22pt Display-Größe (NSImage hat
                # die volle Auflösung, wird sauber runterskaliert).
                from AppKit import NSMakeSize  # type: ignore[import-not-found]

                if self._app._icon_nsimage is not None:
                    self._app._icon_nsimage.setSize_(NSMakeSize(22, 22))
                    self._app._icon_nsimage.setTemplate_(False)
            except Exception:
                self._app.title = STATE_ICONS[State.BOOT]
        else:
            self._app.title = STATE_ICONS[State.BOOT]

        self._build_menu()

    def _build_menu(self) -> None:
        """Constructs the menubar tree with the current locale.

        Called once from __init__ and again from rebuild_menu() after the
        user switches the UI locale. Mode-checkmarks are preserved across
        rebuilds via `self._current_mode`.
        """
        self._mode_items: dict[str, rumps.MenuItem] = {}
        for mode in MODES:
            item = rumps.MenuItem(
                mode_label(mode),
                callback=self._make_mode_callback(mode),
            )
            if mode == self._current_mode:
                item.state = 1
            self._mode_items[mode] = item

        mode_submenu = rumps.MenuItem(t("menubar.mode_submenu"))
        for mode in MODES:
            mode_submenu.add(self._mode_items[mode])

        menu_items: list = []
        if self._on_open_main is not None:
            menu_items.append(
                rumps.MenuItem(t("menubar.main_window"),
                               callback=lambda _: self._on_open_main())
            )
            menu_items.append(None)
        menu_items += [
            mode_submenu,
            None,
            rumps.MenuItem(t("menubar.settings"),
                           callback=lambda _: self._on_open_settings()),
            rumps.MenuItem(t("menubar.open_config"),
                           callback=lambda _: self._on_open_config()),
            None,
            rumps.MenuItem(t("menubar.quit"),
                           callback=lambda _: self._on_quit()),
        ]
        # rumps clears the menu and accepts the new list as-is.
        self._app.menu.clear()
        self._app.menu = menu_items

    def rebuild_menu(self) -> None:
        """Re-renders the menu after the UI locale changed.

        Called from app._on_settings_save when ui_locale changes. Idempotent.
        """
        assert_main_thread("MenubarController.rebuild_menu")
        self._build_menu()

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
