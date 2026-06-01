"""Lightweight internationalization for Flow.

English is canonical. German is provided for users on a macOS locale
starting with `de` (de_DE, de_AT, de_CH). No user toggle — system
locale decides at app startup, cached for the process lifetime.

Usage:

    from wnflow.i18n import t

    notify("Flow", t("notify.api_key_missing"))

In the HTML/JS layer, the same dict is shipped via the
`getLocale` bridge action so the front-end can resolve keys.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Final

log = logging.getLogger(__name__)


def _read_system_locale() -> str:
    """Reads the macOS locale via `defaults`.

    Returns an empty string on any failure so callers can treat it as
    'use the EN default'.
    """
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleLocale"],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        log.exception("Reading AppleLocale failed")
        return ""


_cached_locale: str | None = None
# User override from settings ("auto" | "en" | "de"). "auto" means follow
# system locale. Set via set_user_override() from app startup or settings save.
_user_override: str = "auto"


def _reset_cache() -> None:
    """Test hook — clears the locale cache so tests can swap the value."""
    global _cached_locale, _user_override
    _cached_locale = None
    _user_override = "auto"


def set_user_override(value: str | None) -> None:
    """Sets the explicit UI-language override from user settings.

    `value` is one of "auto", "en", "de". Anything else is treated as "auto".
    Side effect: clears the cache so the next `detect_locale()` re-resolves.
    """
    global _user_override, _cached_locale
    if value not in ("auto", "en", "de"):
        value = "auto"
    _user_override = value
    _cached_locale = None


def detect_locale() -> str:
    """Returns the active locale string: `de` or `en`. Cached.

    Resolution order:
      1. user override (from settings) if explicit `en` / `de`
      2. macOS system locale (defaults read -g AppleLocale)
      3. fallback `en`
    """
    global _cached_locale
    if _cached_locale is not None:
        return _cached_locale
    if _user_override in ("en", "de"):
        _cached_locale = _user_override
        return _cached_locale
    raw = _read_system_locale().lower()
    _cached_locale = "de" if raw.startswith("de") else "en"
    return _cached_locale


TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        # ─── notify / system notifications ────────────────────────────
        "notify.api_key_missing": "GROQ_API_KEY missing — cleanup disabled",
        "notify.hotkey_listener_failed": "Hotkey listener failed: {error}",
        "notify.model_load_failed": "Model load failed: {error}",
        "notify.max_recording_reached": "Max recording length reached — processing",
        "notify.transcription_failed": "Transcription failed: {error}",
        "notify.paste_state_race": "State race on paste",
        "notify.paste_failed": "Paste failed",
        "notify.paste_failed_clipboard": "Paste failed — text stays in the clipboard for manual Cmd+V",
        "notify.settings_save_failed": "Saving settings failed: {error}",
        "notify.hotkey_change_pending_restart": "Hotkey change takes effect after restart",
        "notify.settings_saved": "Settings saved",
        "notify.permissions_missing": (
            "Permissions missing. System Settings → Privacy → Accessibility + Input Monitoring"
        ),
        "notify.v020_legacy_plist": (
            "v0.2.0 launchd agent found. Run 'launchctl unload && rm' "
            "then restart — otherwise two instances run in parallel."
        ),

        # ─── menubar ──────────────────────────────────────────────────
        "menubar.main_window": "Main Window…",
        "menubar.settings": "Settings…",
        "menubar.open_config": "Open Config",
        "menubar.quit": "Quit",
        "menubar.mode_submenu": "Mode",
        "menubar.mode.verbatim": "Verbatim",
        "menubar.mode.formal": "Formal",
        "menubar.mode.rage": "Anti-Rage",

        # ─── main window — tabs ───────────────────────────────────────
        "tab.history.title": "History",
        "tab.history.sub": "This week",
        "tab.dictionary.title": "Dictionary",
        "tab.dictionary.sub": "Your terms and corrections",
        "tab.commands.title": "Commands",
        "tab.commands.sub": "Custom modes and voice triggers",
        "tab.settings.title": "Settings",
        "tab.settings.sub": "API key, language, and hotkeys",

        # ─── main window — history ────────────────────────────────────
        "history.empty.title": "No dictations yet.",
        "history.empty.sub": "Double-tap fn to start recording.",
        "history.kpi.words": "Words",
        "history.kpi.speed": "faster",
        "history.unit.word.one": "word",
        "history.unit.word.other": "words",
        "history.meta.yesterday": "Yesterday",

        # ─── main window — coming soon ────────────────────────────────
        "coming_soon.template": "{label} is coming in a future release.",
        "coming_soon.sub": "Your terms, commands, and corrections will live here.",
        "coming_soon.settings_loading": "Loading settings…",

        # ─── settings form ────────────────────────────────────────────
        "settings.api_key.label": "Groq API key",
        "settings.api_key.hint": "Create one at console.groq.com/keys. Used to clean up dictations (Formal/Anti-Rage).",
        "settings.api_key.show": "Show",
        "settings.api_key.hide": "Hide",
        "settings.api_key.test": "Test",
        "settings.api_key.testing": "Testing…",
        "settings.api_key.empty": "Please paste an API key.",
        "settings.api_key.valid": "✓ Valid",
        "settings.api_key.invalid_prefix": "✗",
        "settings.language.label": "Dictation language",
        "settings.ui_locale.label": "Interface language",
        "settings.ui_locale.hint": "Auto follows your macOS language. Change takes effect immediately.",
        "settings.ui_locale.option.auto": "Auto (system)",
        "settings.ui_locale.option.en": "English",
        "settings.ui_locale.option.de": "Deutsch",
        "sidebar.start_recording": "Start recording",
        "settings.hotwords.label": "Hotwords",
        "settings.hotwords.hint": "One per line. Whisper gets these as a bias list so your proper nouns are transcribed correctly.",
        "settings.section.modes_hotkey": "Mode & Hotkey",
        "settings.default_mode.label": "Default mode",
        "settings.default_mode.hint": "Used when you record without holding a modifier key (Cmd/Ctrl/Shift).",
        "settings.hotkey_key.label": "Activation key",
        "settings.hotkey_key.hint": "Which key starts the recording. fn is the default — if your keyboard has no fn, pick right-Cmd / right-Shift.",
        "settings.hotkey_mode.label": "Activation behavior",
        "settings.hotkey_mode.hint": (
            "PTT = hold while speaking. Toggle = double-tap on/off. Both = either works."
        ),
        "settings.hotkey_mode.option.both": "Both (hold or double-tap)",
        "settings.hotkey_mode.option.ptt": "PTT (push-to-talk, hold)",
        "settings.hotkey_mode.option.toggle": "Toggle (double-tap to start/stop)",
        "settings.double_tap.label": "Double-tap window",
        "settings.double_tap.hint": "How quickly the two taps have to follow each other. Shorter = faster toggle, but more accidental triggers.",
        "settings.section.system": "System",
        "settings.login_item.label": "Launch on login",
        "settings.login_item.sub": "Flow loads into the menubar automatically when you sign in.",
        "settings.mute_bg.label": "Mute background while recording",
        "settings.mute_bg.sub": "Pauses Apple Music & co. while you dictate. Resumes after.",
        "settings.section.history": "History",
        "settings.history.empty": "No history yet",
        "settings.history.count.one": "{n} dictation saved",
        "settings.history.count.other": "{n} dictations saved",
        "settings.history.path": "Stored locally in ~/.worknetic-flow/history.json",
        "settings.history.clear_btn": "Delete all",
        "settings.history.clear_confirm": "{n} dictations will be deleted permanently. Continue?",
        "settings.save": "Save",
        "settings.back": "Back",
        "settings.saved_toast": "Saved ✓",

        # ─── hotkey-key option labels ────────────────────────────────
        "hotkey_key.fn": "fn (function key)",
        "hotkey_key.right_cmd": "Right Cmd",
        "hotkey_key.right_shift": "Right Shift",
        "hotkey_key.right_option": "Right Option",
        "hotkey_key.caps_lock": "Caps Lock",

        # ─── fn-conflict banner ──────────────────────────────────────
        "fn_banner.title": "fn key is reserved by macOS",
        "fn_banner.body": (
            "Your Mac is using fn for {usage}. While that setting is active, Flow "
            "cannot reliably detect the fn double-tap. Either change the system "
            "setting or pick a different hotkey."
        ),
        "fn_banner.usage.emoji": "the Emoji picker",
        "fn_banner.usage.input_source": "switching the input source",
        "fn_banner.usage.dictation": "macOS Dictation",
        "fn_banner.usage.fallback": "a system action",
        "fn_banner.open_settings": "Open keyboard settings",
        "fn_banner.pick_other": "Pick another hotkey",
    },
    "de": {
        # ─── notify / system notifications ────────────────────────────
        "notify.api_key_missing": "GROQ_API_KEY fehlt — Cleanup deaktiviert",
        "notify.hotkey_listener_failed": "Hotkey-Listener fehlgeschlagen: {error}",
        "notify.model_load_failed": "Modell-Load fehlgeschlagen: {error}",
        "notify.max_recording_reached": "Max-Aufnahmelänge erreicht — wird verarbeitet",
        "notify.transcription_failed": "Transkription fehlgeschlagen: {error}",
        "notify.paste_state_race": "State-Race beim Paste",
        "notify.paste_failed": "Paste fehlgeschlagen",
        "notify.paste_failed_clipboard": "Paste fehlgeschlagen — Text bleibt im Clipboard für manuelles Cmd+V",
        "notify.settings_save_failed": "Settings-Speichern fehlgeschlagen: {error}",
        "notify.hotkey_change_pending_restart": "Hotkey-Änderung wirkt nach Neustart",
        "notify.settings_saved": "Einstellungen gespeichert",
        "notify.permissions_missing": (
            "Berechtigungen fehlen. Systemeinstellungen → Datenschutz → Bedienungshilfen + Eingabeüberwachung"
        ),
        "notify.v020_legacy_plist": (
            "v0.2.0 launchd-Agent gefunden. Bitte 'launchctl unload && rm' "
            "und neu starten — sonst laufen 2 Instanzen parallel."
        ),

        # ─── menubar ──────────────────────────────────────────────────
        "menubar.main_window": "Hauptfenster…",
        "menubar.settings": "Einstellungen…",
        "menubar.open_config": "Konfigurationsdatei öffnen",
        "menubar.quit": "Beenden",
        "menubar.mode_submenu": "Modus",
        "menubar.mode.verbatim": "Verbatim",
        "menubar.mode.formal": "Formal",
        "menubar.mode.rage": "Anti-Wut",

        # ─── main window — tabs ───────────────────────────────────────
        "tab.history.title": "Verlauf",
        "tab.history.sub": "Diese Woche",
        "tab.dictionary.title": "Wörterbuch",
        "tab.dictionary.sub": "Eigene Begriffe und Korrekturen",
        "tab.commands.title": "Befehle",
        "tab.commands.sub": "Custom-Modi und Sprach-Triggers",
        "tab.settings.title": "Einstellungen",
        "tab.settings.sub": "API-Key, Sprache und Hotkeys",

        # ─── main window — history ────────────────────────────────────
        "history.empty.title": "Noch keine Diktate.",
        "history.empty.sub": "Doppel-Tap auf fn startet die Aufnahme.",
        "history.kpi.words": "Wörter",
        "history.kpi.speed": "schneller",
        "history.unit.word.one": "Wort",
        "history.unit.word.other": "Wörter",
        "history.meta.yesterday": "Gestern",

        # ─── main window — coming soon ────────────────────────────────
        "coming_soon.template": "{label} folgt in einem nächsten Release.",
        "coming_soon.sub": "Hier wirst du bald deine Begriffe, Befehle und Korrekturen pflegen.",
        "coming_soon.settings_loading": "Lade Einstellungen…",

        # ─── settings form ────────────────────────────────────────────
        "settings.api_key.label": "Groq API-Key",
        "settings.api_key.hint": "Auf console.groq.com/keys erstellen. Wird zum Bereinigen der Diktate (Formal/Anti-Wut) verwendet.",
        "settings.api_key.show": "Zeigen",
        "settings.api_key.hide": "Verbergen",
        "settings.api_key.test": "Testen",
        "settings.api_key.testing": "Teste…",
        "settings.api_key.empty": "Bitte API-Key einfügen.",
        "settings.api_key.valid": "✓ Valide",
        "settings.api_key.invalid_prefix": "✗",
        "settings.language.label": "Diktat-Sprache",
        "settings.ui_locale.label": "Sprache der Oberfläche",
        "settings.ui_locale.hint": "Auto folgt deiner macOS-Sprache. Änderung wirkt sofort.",
        "settings.ui_locale.option.auto": "Auto (System)",
        "settings.ui_locale.option.en": "English",
        "settings.ui_locale.option.de": "Deutsch",
        "sidebar.start_recording": "Diktat starten",
        "settings.hotwords.label": "Hotwords",
        "settings.hotwords.hint": "Eine pro Zeile. Whisper bekommt die als Bias-Liste, damit deine Eigennamen korrekt erkannt werden.",
        "settings.section.modes_hotkey": "Modus & Hotkey",
        "settings.default_mode.label": "Standard-Modus",
        "settings.default_mode.hint": "Wird genutzt, wenn beim Diktieren keine Modifier-Taste (Cmd/Ctrl/Shift) gedrückt wird.",
        "settings.hotkey_key.label": "Aktivierungs-Taste",
        "settings.hotkey_key.hint": "Welche Taste startet die Aufnahme. fn ist Default — manche Tastaturen haben kein fn, dann right_cmd/right_shift.",
        "settings.hotkey_mode.label": "Aktivierungs-Verhalten",
        "settings.hotkey_mode.hint": "PTT = halten während du sprichst. Toggle = doppel-tap startet, doppel-tap stoppt. Both = beide gleichzeitig.",
        "settings.hotkey_mode.option.both": "Both (halten oder doppel-tap)",
        "settings.hotkey_mode.option.ptt": "PTT (push-to-talk, halten)",
        "settings.hotkey_mode.option.toggle": "Toggle (doppel-tap zum An/Aus)",
        "settings.double_tap.label": "Doppel-Tap-Fenster",
        "settings.double_tap.hint": "Wie schnell die zwei Taps aufeinanderfolgen müssen. Kürzer = schneller Toggle, aber mehr Fehl-Trigger.",
        "settings.section.system": "System",
        "settings.login_item.label": "Beim Login automatisch starten",
        "settings.login_item.sub": "Flow lädt sich beim Anmelden in die Menüleiste.",
        "settings.mute_bg.label": "Hintergrund stummschalten während Aufnahme",
        "settings.mute_bg.sub": "Pausiert Apple Music & Co. solange du diktierst. Wird danach automatisch fortgesetzt.",
        "settings.section.history": "Verlauf",
        "settings.history.empty": "Kein Verlauf vorhanden",
        "settings.history.count.one": "{n} Diktat gespeichert",
        "settings.history.count.other": "{n} Diktate gespeichert",
        "settings.history.path": "Liegt lokal in ~/.worknetic-flow/history.json",
        "settings.history.clear_btn": "Alle löschen",
        "settings.history.clear_confirm": "{n} Diktate werden unwiderruflich gelöscht. Fortfahren?",
        "settings.save": "Speichern",
        "settings.back": "Zurück",
        "settings.saved_toast": "Gespeichert ✓",

        # ─── hotkey-key option labels ────────────────────────────────
        "hotkey_key.fn": "fn (Funktions-Taste)",
        "hotkey_key.right_cmd": "Rechte Cmd-Taste",
        "hotkey_key.right_shift": "Rechte Shift-Taste",
        "hotkey_key.right_option": "Rechte Option-Taste",
        "hotkey_key.caps_lock": "Caps Lock",

        # ─── fn-conflict banner ──────────────────────────────────────
        "fn_banner.title": "fn-Taste ist von macOS belegt",
        "fn_banner.body": (
            "Dein Mac nutzt die fn-Taste aktuell für {usage}. Solange diese Einstellung "
            "aktiv ist, kann Flow den fn-Doppel-Tap nicht zuverlässig erkennen. "
            "Ändere entweder die System-Einstellung oder wähle einen anderen Hotkey."
        ),
        "fn_banner.usage.emoji": "den Emoji-Picker",
        "fn_banner.usage.input_source": "den Wechsel der Eingabequelle",
        "fn_banner.usage.dictation": "das macOS-Diktat",
        "fn_banner.usage.fallback": "eine System-Aktion",
        "fn_banner.open_settings": "Tastatur-Einstellungen öffnen",
        "fn_banner.pick_other": "Anderen Hotkey wählen",
    },
}


def t(key: str) -> str:
    """Returns the translation for `key` in the current locale.
    Unknown keys are returned as `[key]` so missing translations are
    obvious in the UI without crashing."""
    locale = detect_locale()
    table = TRANSLATIONS.get(locale, TRANSLATIONS["en"])
    return table.get(key, f"[{key}]")
