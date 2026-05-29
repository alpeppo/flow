"""Settings-Window via NSWindow + AppKit.

v0.3.0: Native macOS-Fenster für Settings (API-Key, Sprache, Hotwords,
Login-Item-Toggle). Lazy creation beim ersten show().

Save schreibt TOML atomic, callback informiert WnflowApp für Live-Reload.

WICHTIG Threading:
- show/hide/save MÜSSEN vom Main-Thread aufgerufen werden
- Test-Button verwendet Worker-Thread für httpx-Call
"""

import logging
from collections.abc import Callable

import objc  # type: ignore[import-not-found]
from AppKit import (  # type: ignore[import-not-found]
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSBezelBorder,
    NSButton,
    NSColor,
    NSFont,
    NSMakeRect,
    NSPopUpButton,
    NSScrollView,
    NSSecureTextField,
    NSTextField,
    NSTextView,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSObject  # type: ignore[import-not-found]

from wnflow.threading_guard import assert_main_thread

log = logging.getLogger(__name__)


# Spec §3.5: 6 EU-Sprachen
LANGUAGE_OPTIONS = [
    ("de", "Deutsch"),
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("nl", "Nederlands"),
]


def parse_hotwords(text: str) -> list[str]:
    """Multi-line text → list of stripped non-empty hotwords."""
    return [line.strip() for line in text.split("\n") if line.strip()]


def language_code_to_index(code: str) -> int:
    """ISO-Code → Dropdown-Index. Unbekannt → 0 (Default Deutsch)."""
    for idx, (c, _) in enumerate(LANGUAGE_OPTIONS):
        if c == code:
            return idx
    return 0


def language_index_to_code(idx: int) -> str:
    """Dropdown-Index → ISO-Code. Out-of-range → 'de'."""
    if 0 <= idx < len(LANGUAGE_OPTIONS):
        return LANGUAGE_OPTIONS[idx][0]
    return "de"


class _SettingsController(NSObject):
    """NSObject-Subclass für ObjC-Selector-Targets."""

    def initWithCallbacks_testCallback_(self, on_save_dict, on_test):
        self = objc.super(_SettingsController, self).init()
        if self is None:
            return None
        self._on_save_dict = on_save_dict
        self._on_test = on_test
        self._window = None
        self._key_field = None
        self._lang_popup = None
        self._hw_view = None
        self._login_item_btn = None
        self._test_label = None
        self._test_button = None
        return self

    def buildWindow_(self, initial_values):
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 480, 380), style, NSBackingStoreBuffered, False
        )
        self._window.setTitle_("worknetic-flow Settings")
        self._window.center()
        content = self._window.contentView()

        y = 340

        # API-Key Label
        api_label = self._make_label("Groq API-Key", 20, y, 200)
        content.addSubview_(api_label)
        y -= 24

        # API-Key Field + Test-Button
        self._key_field = NSSecureTextField.alloc().initWithFrame_(
            NSMakeRect(20, y, 340, 24)
        )
        self._key_field.setStringValue_(initial_values.get("api_key", ""))
        content.addSubview_(self._key_field)

        self._test_button = NSButton.alloc().initWithFrame_(
            NSMakeRect(370, y - 2, 80, 28)
        )
        self._test_button.setTitle_("Test")
        self._test_button.setBezelStyle_(1)
        self._test_button.setTarget_(self)
        self._test_button.setAction_(b"onTest:")
        content.addSubview_(self._test_button)
        y -= 30

        # Test-Result-Label (initial leer)
        self._test_label = self._make_label("", 20, y, 440)
        content.addSubview_(self._test_label)
        y -= 16

        # Hint
        hint = self._make_label(
            "ⓘ Auf console.groq.com/keys erstellen", 20, y, 440
        )
        hint.setTextColor_(NSColor.secondaryLabelColor())
        content.addSubview_(hint)
        y -= 32

        # Sprache Label
        lang_label = self._make_label("Diktat-Sprache", 20, y, 200)
        content.addSubview_(lang_label)
        y -= 30

        # Sprach-Dropdown
        self._lang_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(20, y, 200, 26), False
        )
        for _code, label in LANGUAGE_OPTIONS:
            self._lang_popup.addItemWithTitle_(label)
        self._lang_popup.selectItemAtIndex_(
            language_code_to_index(initial_values.get("language", "de"))
        )
        content.addSubview_(self._lang_popup)
        y -= 40

        # Hotwords Label
        hw_label = self._make_label("Hotwords (eine pro Zeile)", 20, y, 300)
        content.addSubview_(hw_label)
        y -= 90

        # Hotwords TextView (in ScrollView)
        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(20, y, 440, 80))
        scroll.setBorderType_(NSBezelBorder)
        scroll.setHasVerticalScroller_(True)
        self._hw_view = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, 440, 80)
        )
        # POC 2 Lesson: alle 4 Settings nötig für interaktive TextView
        self._hw_view.setEditable_(True)
        self._hw_view.setSelectable_(True)
        self._hw_view.setRichText_(False)
        self._hw_view.setAllowsUndo_(True)
        self._hw_view.setFont_(NSFont.userFixedPitchFontOfSize_(12))
        hw_text = "\n".join(initial_values.get("hotwords", []))
        self._hw_view.setString_(hw_text)
        scroll.setDocumentView_(self._hw_view)
        content.addSubview_(scroll)
        y -= 30

        # Login-Item Toggle
        self._login_item_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(20, y, 300, 24)
        )
        self._login_item_btn.setButtonType_(3)  # NSButtonTypeSwitch
        self._login_item_btn.setTitle_("Beim Login automatisch starten")
        self._login_item_btn.setState_(
            1 if initial_values.get("login_item", False) else 0
        )
        content.addSubview_(self._login_item_btn)

        # Save + Cancel Buttons (rechts unten)
        save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(380, 12, 80, 32))
        save_btn.setTitle_("Speichern")
        save_btn.setBezelStyle_(1)
        save_btn.setKeyEquivalent_("\r")
        save_btn.setTarget_(self)
        save_btn.setAction_(b"onSave:")
        content.addSubview_(save_btn)

        cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(290, 12, 80, 32))
        cancel_btn.setTitle_("Abbrechen")
        cancel_btn.setBezelStyle_(1)
        cancel_btn.setKeyEquivalent_("\x1b")  # ESC
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_(b"onCancel:")
        content.addSubview_(cancel_btn)

        return self._window

    def _make_label(self, text, x, y, width):
        label = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, width, 20))
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        return label

    def onSave_(self, sender):
        values = {
            "api_key": str(self._key_field.stringValue()),
            "language": language_index_to_code(
                self._lang_popup.indexOfSelectedItem()
            ),
            "hotwords": parse_hotwords(str(self._hw_view.string())),
            "login_item": bool(self._login_item_btn.state()),
        }
        self._on_save_dict(values)
        self._window.orderOut_(None)
        # Zurück zu Accessory (Menubar-only ohne Dock-Icon)
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )

    def onCancel_(self, sender):
        self._window.orderOut_(None)
        # Zurück zu Accessory (Menubar-only ohne Dock-Icon)
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )

    def onTest_(self, sender):
        key = str(self._key_field.stringValue())
        self._test_button.setEnabled_(False)
        self._test_label.setStringValue_("Testen...")

        def result_callback(success: bool, message: str) -> None:
            # Wird vom Worker-Thread aufgerufen — auf Main dispatchen
            from PyObjCTools import AppHelper  # type: ignore[import-not-found]

            AppHelper.callAfter(self._update_test_result, success, message)

        self._on_test(key, result_callback)

    def _update_test_result(self, success: bool, message: str):
        if success:
            self._test_label.setStringValue_("✓ Valide")
            self._test_label.setTextColor_(NSColor.systemGreenColor())
        else:
            self._test_label.setStringValue_(f"✗ {message}")
            self._test_label.setTextColor_(NSColor.systemRedColor())
        self._test_button.setEnabled_(True)


class SettingsWindow:
    """Wrapper um NSWindow mit Form-Elements für Settings."""

    def __init__(
        self,
        on_save: Callable[[dict], None],
        on_test_api_key: Callable[[str, Callable[[bool, str], None]], None],
    ) -> None:
        self._on_save = on_save
        self._on_test_api_key = on_test_api_key
        self._controller = None
        self.is_ready = False

    def show(self, initial_values: dict) -> None:
        assert_main_thread("SettingsWindow.show")
        if self._controller is None:
            self._controller = (
                _SettingsController.alloc().initWithCallbacks_testCallback_(
                    self._on_save, self._on_test_api_key
                )
            )
            self._controller.buildWindow_(initial_values)
            self.is_ready = True
        else:
            # Re-show: aktualisiere Werte
            self._controller._key_field.setStringValue_(initial_values.get("api_key", ""))
            self._controller._lang_popup.selectItemAtIndex_(
                language_code_to_index(initial_values.get("language", "de"))
            )
            hw_text = "\n".join(initial_values.get("hotwords", []))
            self._controller._hw_view.setString_(hw_text)
            self._controller._login_item_btn.setState_(
                1 if initial_values.get("login_item", False) else 0
            )

        # KRITISCH: rumps.App läuft als LSUIElement (kein Dock-Icon, kein
        # App-Switcher). Solche Apps können keinen Keyboard-Focus auf Sub-
        # Windows weiterleiten — Textfields wären "read-only".
        # Lösung: temporär zur Regular-App promoten beim Settings-Open.
        # Beim Close (onSave_ / onCancel_) zurück zu Accessory.
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        self._controller._window.makeKeyAndOrderFront_(None)
        app.activateIgnoringOtherApps_(True)
