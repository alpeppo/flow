"""macOS Permission-Check via pyobjc.

Verwendet AXIsProcessTrustedWithOptions aus dem ApplicationServices-Framework
um zu prüfen ob die App Accessibility-Permission hat. Wenn nicht, öffnet der
Aufruf automatisch den System-Dialog (wenn prompt=True).

Microphone-Permission wird NICHT hier geprüft — sounddevice raised PortAudioError
beim ersten Recording, das fangen wir dort ab.

Input-Monitoring-Permission gibt es kein direktes API für — pynput-Listener
schlägt einfach still fehl wenn fehlt. Wir prüfen indirekt: wenn Accessibility
ok ist, klappt meistens auch Input-Monitoring (Apple koppelt das mehr und mehr).

pyobjc bridged Python-dicts automatisch zu CFDictionary, deshalb der einfache
dict-Aufruf statt manuellem CFDictionaryCreate.
"""

import logging

log = logging.getLogger(__name__)


def ensure_permissions(prompt: bool = True) -> bool:
    """Prüft ob Accessibility-Permission vorhanden ist.

    Wenn `prompt=True`, öffnet macOS den System-Dialog falls Permission fehlt.
    Returns True wenn Permission da ist, sonst False.

    Bei pyobjc-Import-Fehler: returns True (silent fallback, App versucht es
    trotzdem — pynput-Listener wird dann fehlschlagen aber das ist gehandled).
    """
    try:
        from ApplicationServices import (  # type: ignore[import-not-found]
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )
    except ImportError as exc:
        log.warning("pyobjc/ApplicationServices nicht verfügbar, skip permission check: %s", exc)
        return True

    # pyobjc bridged Python-dict automatisch zu CFDictionary
    options = {kAXTrustedCheckOptionPrompt: bool(prompt)}
    trusted = AXIsProcessTrustedWithOptions(options)
    log.info("Accessibility trusted: %s", bool(trusted))
    return bool(trusted)
