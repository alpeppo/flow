"""Audio-Ducker: pausiert Medien + drosselt System-Volume waehrend Recording.

Aktiviert via Config-Toggle (audio.mute_background). Beim Recording-Start:
- Sendet System-Media-Pause (pausiert Spotify, Music, YouTube/Browser-Video etc.)
- Speichert aktuelles System-Volume und setzt auf 0

Beim Recording-Stop:
- Stellt das gespeicherte Volume wieder her
- Schickt KEIN auto-Play (User entscheidet selbst ob er weiter hören will)

Implementierung via osascript — kein extra Permission, kein Audio-Routing.
Side-Effect-frei wenn mute_background=False (Methoden sind no-ops).

WICHTIG Threading: mute/restore werden synchron aufgerufen, blockieren ~50ms.
Aufrufer sollte das wissen (hier vom Main-Thread).
"""

import logging
import subprocess

log = logging.getLogger(__name__)


class AudioDucker:
    """System-Mute + Media-Pause Wrapper. Stateless wenn enabled=False.

    Beim Recording-Start: speichert was gerade spielt (Spotify / Music),
    pausiert, mutet System-Volume. Beim Restore: setzt Volume zurueck und
    startet die zuvor spielenden Apps automatisch wieder.
    """

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled
        self._saved_volume: int | None = None
        self._was_playing: list[str] = []  # ['Spotify', 'Music', ...]
        self._muted = False

    def set_enabled(self, enabled: bool) -> None:
        """Live-Reload Hook für Settings-Toggle."""
        if enabled == self._enabled:
            return
        # Wenn gerade aktiv gemuted und User schaltet aus: aufräumen.
        if not enabled and self._muted:
            self.restore()
        self._enabled = enabled
        log.info("AudioDucker enabled=%s", enabled)

    def _is_app_playing(self, app_name: str) -> bool:
        """Prüfen ob App laeuft UND gerade spielt (via player state)."""
        # 'running of application "X"' ist robust auch wenn App nicht offen.
        try:
            check = subprocess.run(
                ["osascript", "-e",
                 f'tell application "System Events" to (name of processes) contains "{app_name}"'],
                capture_output=True, text=True, timeout=1.0, check=True,
            )
            if check.stdout.strip().lower() != "true":
                return False
        except subprocess.SubprocessError:
            return False
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 f'tell application "{app_name}" to player state as string'],
                capture_output=True, text=True, timeout=1.5, check=True,
            )
            return result.stdout.strip().lower() == "playing"
        except subprocess.SubprocessError:
            return False

    def mute(self) -> None:
        """Pausiert Medien + setzt System-Volume auf 0."""
        if not self._enabled:
            return
        if self._muted:
            log.debug("AudioDucker.mute called while already muted — skip")
            return

        # 1. Vor dem Pausieren: festhalten welche Apps gerade spielen,
        # damit wir sie beim restore() gezielt wieder starten können.
        self._was_playing = []
        for app in ("Spotify", "Music"):
            if self._is_app_playing(app):
                self._was_playing.append(app)
        log.debug("AudioDucker: apps playing before mute: %s", self._was_playing)

        # 2. Volume sichern + auf 0
        try:
            result = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True, text=True, timeout=2.0, check=True,
            )
            self._saved_volume = int(result.stdout.strip())
            subprocess.run(
                ["osascript", "-e", "set volume output volume 0"],
                capture_output=True, timeout=2.0, check=True,
            )
        except (subprocess.SubprocessError, ValueError) as e:
            log.warning("AudioDucker volume mute failed: %s", e)
            self._saved_volume = None

        # 3. Media pausieren via Pause-Key (Spotify, Music, YouTube, ...)
        try:
            subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to key code 49 using {function down}'],
                capture_output=True, timeout=2.0, check=False,
            )
        except subprocess.SubprocessError as e:
            log.debug("AudioDucker media pause failed (non-fatal): %s", e)

        # 4. Fallback: direkt Spotify und Music pausieren (falls Media-Key
        # nicht ankommt). Best-effort, Fehler ignoriert.
        for app_cmd in (
            'tell application "Spotify" to pause',
            'tell application "Music" to pause',
        ):
            try:
                subprocess.run(
                    ["osascript", "-e", app_cmd],
                    capture_output=True, timeout=1.0, check=False,
                )
            except subprocess.SubprocessError:
                pass

        self._muted = True
        log.debug(
            "AudioDucker muted (saved_volume=%s, was_playing=%s)",
            self._saved_volume, self._was_playing,
        )

    def restore(self) -> None:
        """Stellt System-Volume wieder her + startet pausierte Apps neu."""
        if not self._muted:
            return

        # 1. Volume zurueck
        if self._saved_volume is not None:
            try:
                subprocess.run(
                    ["osascript", "-e",
                     f"set volume output volume {self._saved_volume}"],
                    capture_output=True, timeout=2.0, check=True,
                )
            except subprocess.SubprocessError as e:
                log.warning("AudioDucker volume restore failed: %s", e)

        # 2. Vorher spielende Apps wieder starten (nur die)
        for app in self._was_playing:
            try:
                subprocess.run(
                    ["osascript", "-e", f'tell application "{app}" to play'],
                    capture_output=True, timeout=1.5, check=False,
                )
                log.debug("AudioDucker: resumed %s", app)
            except subprocess.SubprocessError as e:
                log.debug("AudioDucker resume %s failed: %s", app, e)

        self._muted = False
        self._saved_volume = None
        self._was_playing = []
        log.debug("AudioDucker restored")
