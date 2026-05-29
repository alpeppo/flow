"""macOS Login-Item via SMAppService (macOS 13+).

v0.3.0: Ersetzt v0.2.0 launchd-Agent für Auto-Start beim Login.

Funktioniert NUR in PyInstaller-Bundles (.app). In Dev-Mode (uv run):
graceful fallback mit klarer Fehlermeldung.
"""

import logging
import sys
from typing import Optional

log = logging.getLogger(__name__)


def is_in_app_bundle() -> bool:
    """True wenn Code aus einem PyInstaller-/macOS-.app-Bundle läuft."""
    if not getattr(sys, "frozen", False):
        return False
    return "Contents/MacOS" in sys.executable


def is_login_enabled() -> bool:
    """Prüft ob App als Login-Item registriert ist. Dev-Mode: False."""
    if not is_in_app_bundle():
        return False
    try:
        from ServiceManagement import SMAppService  # type: ignore[import-not-found]

        # SMAppServiceStatusEnabled = 1
        return SMAppService.mainAppService().status() == 1
    except Exception as exc:
        log.warning("is_login_enabled failed: %s", exc)
        return False


def set_login_enabled(enabled: bool) -> Optional[str]:
    """Aktiviert/deaktiviert Login-Item.

    Returns None bei Erfolg, error-message bei Fehler.
    """
    if not is_in_app_bundle():
        return "Login-Item nur in installierter App verfügbar (nicht in Dev-Mode)"
    try:
        from ServiceManagement import SMAppService  # type: ignore[import-not-found]

        svc = SMAppService.mainAppService()
        if enabled:
            success, err = svc.registerAndReturnError_(None)
        else:
            success, err = svc.unregisterAndReturnError_(None)

        if not success and err is not None:
            return str(err)
        return None
    except Exception as exc:
        return str(exc)
