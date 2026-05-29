"""POC 2: NSWindow mit Form-Elementen.

Öffnet ein 480x360 Fenster mit:
- NSSecureTextField (API-Key)
- NSPopUpButton (Sprache-Dropdown)
- NSTextView (Hotwords-Textarea)
- Save-Button (loggt Werte)

Validiert das Settings-Window-Stack vor 6h Implementation.

Run: cd ~/Developer/worknetic-flow && unset VIRTUAL_ENV && uv run python poc/poc_nswindow_form.py
Quit: Cmd+Q oder Window-Close-Button.
"""

import objc  # type: ignore[import-not-found]
from AppKit import (  # type: ignore[import-not-found]
    NSApplication,
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
from PyObjCTools import AppHelper  # type: ignore[import-not-found]


class POC2Controller(NSObject):
    def init(self):
        self = objc.super(POC2Controller, self).init()
        if self is None:
            return None
        return self

    def setup(self):
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 200, 480, 360), style, NSBackingStoreBuffered, False
        )
        self._window.setTitle_("POC 2 — NSWindow Form")
        self._window.center()
        content = self._window.contentView()

        # API-Key Label
        label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 310, 200, 20))
        label.setStringValue_("Groq API-Key")
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        content.addSubview_(label)

        # API-Key NSSecureTextField (zeigt Bullets)
        self._key_field = NSSecureTextField.alloc().initWithFrame_(
            NSMakeRect(20, 280, 350, 24)
        )
        self._key_field.setStringValue_("vorhandener_key_demo_12345")
        content.addSubview_(self._key_field)

        # Sprach-Dropdown
        lang_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 240, 200, 20))
        lang_label.setStringValue_("Diktat-Sprache")
        lang_label.setBezeled_(False)
        lang_label.setDrawsBackground_(False)
        lang_label.setEditable_(False)
        content.addSubview_(lang_label)

        self._lang_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(20, 210, 200, 26), False
        )
        for lang in ["Deutsch", "English", "Français", "Español", "Italiano", "Nederlands"]:
            self._lang_popup.addItemWithTitle_(lang)
        content.addSubview_(self._lang_popup)

        # Hotwords-Textarea
        hw_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 170, 300, 20))
        hw_label.setStringValue_("Hotwords (eine pro Zeile)")
        hw_label.setBezeled_(False)
        hw_label.setDrawsBackground_(False)
        hw_label.setEditable_(False)
        content.addSubview_(hw_label)

        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(20, 80, 440, 80))
        scroll.setBorderType_(NSBezelBorder)
        self._hw_view = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, 440, 80)
        )
        self._hw_view.setFont_(NSFont.userFixedPitchFontOfSize_(12))
        self._hw_view.setString_("Worknetic\nRidersystem\n")
        scroll.setDocumentView_(self._hw_view)
        content.addSubview_(scroll)

        # Save-Button
        self._save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(360, 20, 100, 32))
        self._save_btn.setTitle_("Save")
        self._save_btn.setBezelStyle_(1)  # Rounded
        self._save_btn.setTarget_(self)
        self._save_btn.setAction_(b"onSave:")
        content.addSubview_(self._save_btn)

        self._window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        print(f"POC 2 ready. Window: 480x360")
        print("Form-Elemente: NSSecureTextField, NSPopUpButton, NSTextView, NSButton")
        print("Save-Klick loggt Werte. Cmd+Q oder Close-Button beendet.")

    def onSave_(self, sender):
        key = str(self._key_field.stringValue())
        lang_idx = self._lang_popup.indexOfSelectedItem()
        lang_name = str(self._lang_popup.titleOfSelectedItem())
        hotwords_raw = str(self._hw_view.string())
        hotwords = [w.strip() for w in hotwords_raw.split("\n") if w.strip()]
        print()
        print("=== SAVE CLICKED ===")
        print(f"API-Key length: {len(key)}")
        print(f"Language: [{lang_idx}] {lang_name}")
        print(f"Hotwords: {hotwords}")
        print("===================")


def main():
    NSApplication.sharedApplication()
    controller = POC2Controller.alloc().init()
    controller.setup()
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
