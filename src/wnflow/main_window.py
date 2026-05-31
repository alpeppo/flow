"""Hauptfenster mit WKWebView.

NSWindow + WKWebView, der src/wnflow/web/index.html lädt. JavaScript
spricht über `window.webkit.messageHandlers.flow.postMessage({action})`
mit Python.

Bridge-Actions:
  - "loadHistory": Python schickt History-Payload via
    evaluateJavaScript("applyHistory(<json>)")
  - "openSettings": oeffnet das bestehende SettingsWindow

Threading: Window-Open / WebView-Calls IMMER vom Main-Thread.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from pathlib import Path

import objc  # type: ignore[import-not-found]
from AppKit import (  # type: ignore[import-not-found]
    NSApp,
    NSBackingStoreBuffered,
    NSColor,
    NSFloatingWindowLevel,
    NSWindow,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskFullSizeContentView,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
)
from Foundation import (  # type: ignore[import-not-found]
    NSObject,
    NSOperationQueue,
    NSURL,
    NSURLRequest,
)
from WebKit import (  # type: ignore[import-not-found]
    WKUserContentController,
    WKWebView,
    WKWebViewConfiguration,
)

from wnflow import history_store
from wnflow.threading_guard import assert_main_thread

log = logging.getLogger(__name__)


WINDOW_WIDTH = 980
WINDOW_HEIGHT = 640


def _html_path() -> Path | None:
    """Findet index.html im Bundle (sys._MEIPASS) oder im Dev-Tree."""
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "wnflow" / "web" / "index.html")
        candidates.append(Path(meipass) / "web" / "index.html")
    candidates.append(Path(__file__).parent / "web" / "index.html")
    for p in candidates:
        if p.exists():
            return p
    log.error("main_window: index.html not found in %s", candidates)
    return None


class _BridgeHandler(NSObject):
    """WKScriptMessageHandler — empfaengt JS → Python Calls."""

    def initWithOwner_(self, owner):
        self = objc.super(_BridgeHandler, self).init()
        if self is None:
            return None
        self._owner = owner
        return self

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        try:
            body = message.body()
            action = body.get("action") if hasattr(body, "get") else None
            if action is None and isinstance(body, dict):
                action = body.get("action")
            if action is None:
                return
            # NIEMALS synchron im WebKit-Callback ausfuehren — sonst
            # EXC_BAD_ACCESS bei Side-Effects wie Window-Open. Stattdessen
            # auf den Main-RunLoop dispatchen (next iteration).
            owner = self._owner
            NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: owner._on_bridge_message(action, body)
            )
        except Exception:
            log.error("Bridge handler failed:\n%s", traceback.format_exc())


class MainWindow:
    """Wrapper um NSWindow + WKWebView mit Lazy-Creation."""

    def __init__(
        self,
        on_load_settings=None,
        on_save_settings=None,
        on_test_api_key=None,
        on_open_keyboard_settings=None,
    ) -> None:
        self._window: NSWindow | None = None
        self._webview: WKWebView | None = None
        self._bridge: _BridgeHandler | None = None
        self._on_load_settings = on_load_settings
        self._on_save_settings = on_save_settings
        self._on_test_api_key = on_test_api_key
        self._on_open_keyboard_settings = on_open_keyboard_settings
        self._loaded = False

    # ---------- Public API --------------------------------------------------

    def show(self) -> None:
        assert_main_thread("MainWindow.show")
        try:
            self._ensure_window()
            self._window.makeKeyAndOrderFront_(None)
            try:
                NSApp.activateIgnoringOtherApps_(True)
            except Exception:
                pass
        except Exception:
            log.exception("MainWindow.show failed")

    def hide(self) -> None:
        assert_main_thread("MainWindow.hide")
        if self._window is not None:
            try:
                self._window.orderOut_(None)
            except Exception:
                log.exception("MainWindow.hide failed")

    def refresh_history(self) -> None:
        """Pusht aktualisierte History an JS. Aufruf vom Main-Thread."""
        if not self._loaded or self._webview is None:
            return
        try:
            self._send_history()
        except Exception:
            log.exception("refresh_history failed")

    # ---------- Bridge ------------------------------------------------------

    def _on_bridge_message(self, action: str, body) -> None:
        log.debug("Bridge: %s", action)
        if action == "loadHistory":
            self._send_history()
        elif action == "loadSettings":
            self._send_settings()
        elif action == "saveSettings":
            payload = self._body_to_dict(body).get("payload") or {}
            if self._on_save_settings is not None:
                try:
                    self._on_save_settings(payload)
                    self.notify_settings_saved()
                except Exception:
                    log.exception("saveSettings callback raised")
        elif action == "testApiKey":
            payload = self._body_to_dict(body).get("payload") or {}
            key = str(payload.get("key", ""))
            if self._on_test_api_key is not None:
                try:
                    self._on_test_api_key(key, self._deliver_test_result)
                except Exception:
                    log.exception("testApiKey callback raised")
                    self._deliver_test_result(False, "Interner Fehler")
        elif action == "windowClose":
            self.hide()
        elif action == "windowMinimize":
            if self._window is not None:
                try:
                    self._window.miniaturize_(None)
                except Exception:
                    log.exception("miniaturize failed")
        elif action == "windowZoom":
            if self._window is not None:
                try:
                    self._window.zoom_(None)
                except Exception:
                    log.exception("zoom failed")
        elif action == "openKeyboardSettings":
            if self._on_open_keyboard_settings is not None:
                try:
                    self._on_open_keyboard_settings()
                except Exception:
                    log.exception("openKeyboardSettings callback raised")
        else:
            log.warning("Unknown bridge action: %s", action)

    @staticmethod
    def _body_to_dict(body) -> dict:
        """WKScriptMessage.body kommt als NSDictionary; dict() schickt's."""
        try:
            return dict(body) if body is not None else {}
        except Exception:
            return {}

    def _send_history(self) -> None:
        if self._webview is None:
            return
        data = history_store.payload(limit=80)
        js_payload = json.dumps(data, ensure_ascii=False)
        self._webview.evaluateJavaScript_completionHandler_(
            f"window.applyHistory({js_payload})", None
        )

    def _send_settings(self) -> None:
        if self._webview is None or self._on_load_settings is None:
            return
        try:
            values = self._on_load_settings()
        except Exception:
            log.exception("loadSettings provider raised")
            values = {}
        js_payload = json.dumps(values, ensure_ascii=False)
        self._webview.evaluateJavaScript_completionHandler_(
            f"window.applySettings({js_payload})", None
        )

    def _deliver_test_result(self, ok: bool, message: str) -> None:
        """Wird vom Test-Worker aufgerufen (anderer Thread). Wir hoppen
        zurück auf Main für den JS-Call."""
        def _push():
            if self._webview is None:
                return
            payload = json.dumps({"ok": bool(ok), "message": str(message or "")},
                                  ensure_ascii=False)
            js = f"window.applyApiKeyTestResult({json.dumps(bool(ok))}, {json.dumps(str(message or ''))})"
            self._webview.evaluateJavaScript_completionHandler_(js, None)
        NSOperationQueue.mainQueue().addOperationWithBlock_(_push)

    def notify_settings_saved(self) -> None:
        if self._webview is None:
            return
        self._webview.evaluateJavaScript_completionHandler_(
            "window.applySettingsSaved && window.applySettingsSaved()", None
        )

    def activate_tab(self, tab: str) -> None:
        """Wechselt den Tab im offenen Fenster (vor allem für Menubar
        'Settings…' → tab=settings)."""
        if self._webview is None:
            return
        try:
            self._webview.evaluateJavaScript_completionHandler_(
                f"window.activateTab && window.activateTab({json.dumps(tab)})", None
            )
        except Exception:
            log.exception("activate_tab failed")

    # ---------- Setup -------------------------------------------------------

    def _ensure_window(self) -> None:
        if self._window is not None:
            return

        # 1. WKWebView-Config mit ScriptMessageHandler "flow"
        config = WKWebViewConfiguration.alloc().init()
        controller = WKUserContentController.alloc().init()
        self._bridge = _BridgeHandler.alloc().initWithOwner_(self)
        controller.addScriptMessageHandler_name_(self._bridge, "flow")
        config.setUserContentController_(controller)

        # 2. WebView
        from AppKit import NSMakeRect  # type: ignore[import-not-found]
        frame = NSMakeRect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self._webview = WKWebView.alloc().initWithFrame_configuration_(frame, config)
        try:
            # Transparenter Hintergrund während Ladens: Window hat eigene Farbe.
            self._webview.setValue_forKey_(False, "drawsBackground")
        except Exception:
            pass

        # 3. NSWindow — borderless, full-size content. Titlebar wird komplett
        # vom HTML übernommen (eigene Ampel-Controls + Drag-Region via
        # CSS -webkit-app-region). Resizable + Miniaturizable bleiben aktiv,
        # damit Cmd+M und Edge-Resize funktionieren.
        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            | NSWindowStyleMaskResizable
            | NSWindowStyleMaskFullSizeContentView
        )
        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, style, NSBackingStoreBuffered, False
        )
        self._window.setTitle_("Flow")
        # FullSizeContentView: Titlebar wird transparent, WebView fuellt
        # bis ganz nach oben — sichtbarer Titlebar-Strip verschwindet.
        try:
            self._window.setTitlebarAppearsTransparent_(True)
            self._window.setTitleVisibility_(1)  # NSWindowTitleHidden
            self._window.setMovableByWindowBackground_(False)
        except Exception:
            pass
        # Hintergrund transparent — der Card-Look entsteht im HTML.
        try:
            self._window.setBackgroundColor_(NSColor.clearColor())
            self._window.setOpaque_(False)
            self._window.setHasShadow_(True)
        except Exception:
            pass
        # Standard-Buttons (Ampel) verstecken — wir bauen eigene im HTML.
        try:
            from AppKit import (  # type: ignore[import-not-found]
                NSWindowCloseButton,
                NSWindowMiniaturizeButton,
                NSWindowZoomButton,
            )
            for btn_key in (NSWindowCloseButton, NSWindowMiniaturizeButton, NSWindowZoomButton):
                btn = self._window.standardWindowButton_(btn_key)
                if btn is not None:
                    btn.setHidden_(True)
        except Exception:
            log.exception("Hiding standard window buttons failed (non-fatal)")
        self._window.setContentView_(self._webview)
        self._window.center()
        # Beim ersten Show wird Window zur Key-Window — wir wollen dass die App
        # aktiviert ist, damit die Titlebar normalen Focus-State zeigt.

        # 4. HTML laden
        html_path = _html_path()
        if html_path is None:
            log.error("MainWindow: index.html missing — empty window shown")
            return
        url = NSURL.fileURLWithPath_(str(html_path))
        # readAccessURL = Eltern-Verzeichnis, damit das HTML eventuelle
        # Assets aus dem gleichen Ordner laden darf.
        try:
            self._webview.loadFileURL_allowingReadAccessToURL_(
                url, NSURL.fileURLWithPath_(str(html_path.parent))
            )
        except AttributeError:
            # Fallback: ohne read-access scope
            req = NSURLRequest.requestWithURL_(url)
            self._webview.loadRequest_(req)
        self._loaded = True
        log.info("MainWindow ready (loaded %s)", html_path)
