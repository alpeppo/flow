"""Config-Modul: TOML laden + Defaults schreiben + ENV-Override.

Default-Pfad: ~/.worknetic-flow/config.toml
Wenn Datei fehlt, wird sie mit Defaults erzeugt.
ENV-Override nur für Secrets (GROQ_API_KEY).
"""

import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

log = logging.getLogger(__name__)

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("worknetic-flow")
except Exception:
    # Source checkouts without install: fall back to reading pyproject.toml
    _pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        __version__ = tomllib.loads(_pyproject.read_text())["project"]["version"]
    except (OSError, tomllib.TOMLDecodeError, KeyError):
        __version__ = "0.0.0+unknown"

# v0.4.0 migration: bekannte alte Defaults werden beim Laden auf den neuen
# 10-min-Cap angehoben. Explizite User-Werte (nicht in dieser Menge) bleiben.
_STALE_MAX_DURATION_DEFAULTS = {0.0, 60.0}

DEFAULT_CONFIG_PATH = Path.home() / ".worknetic-flow" / "config.toml"

# Sprach-Liste für Settings-Window (Code, Display-Name)
LANGUAGES = [
    ("de", "Deutsch"),
    ("en", "English"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("nl", "Nederlands"),
]

DEFAULTS_TOML = """\
[stt]
model = "mlx-community/whisper-large-v3-turbo-q4"
language = "de"

[hotkey]
mode = "both"  # ptt | toggle | both
key = "fn"  # POC 2 validiert via pyobjc — siehe hotkey.py MODIFIER_FLAGS für Alternativen
double_tap_window_ms = 350

[recording]
min_duration_s = 0.5
max_duration_s = 600.0  # 10 minutes; pill warns at 9:00 / 9:30 / 9:45
sample_rate = 16000

[cleanup]
enabled = true
provider = "groq"
model = "llama-3.3-70b-versatile"
timeout_s = 5.0
retry = 1

[cleanup.hotwords]
words = ["Worknetic", "Ridersystem", "BZKI", "Pannhausen", "Polyamor", "Antbees"]

[commands]
enabled = true
triggers = ["Befehl:", "Mach das", "Übersetze", "Schreib das"]

[output]
clipboard_restore_delay_ms = 300

[logging]
level = "info"
keep_transcripts = false

[modes]
default = "verbatim"  # verbatim | formal | rage

[pill]
enabled = true
mode_indicator = true
waveform_bar_count = 5
fade_out_ms = 200

[audio]
mute_background = false  # pausiert Medien + mutet Volume waehrend Recording
"""


@dataclass
class STTConfig:
    model: str = "mlx-community/whisper-large-v3-turbo-q4"
    language: str = "de"


@dataclass
class HotkeyConfig:
    mode: str = "both"
    key: str = "fn"  # POC 2 validiert via pyobjc
    double_tap_window_ms: int = 350


@dataclass
class RecordingConfig:
    min_duration_s: float = 0.5
    max_duration_s: float = 600.0  # 10 minutes; pill warns at 9:00 / 9:30 / 9:45
    sample_rate: int = 16000


@dataclass
class CleanupConfig:
    enabled: bool = True
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    timeout_s: float = 5.0
    retry: int = 1
    hotwords: list[str] = field(default_factory=list)
    api_key: str = ""


@dataclass
class CommandsConfig:
    enabled: bool = True
    triggers: list[str] = field(default_factory=lambda: ["Befehl:"])


@dataclass
class OutputConfig:
    clipboard_restore_delay_ms: int = 300


@dataclass
class LoggingConfig:
    level: str = "info"
    keep_transcripts: bool = False


@dataclass
class ModesConfig:
    default: str = "verbatim"  # verbatim | formal | rage


@dataclass
class PillConfig:
    enabled: bool = True
    mode_indicator: bool = True
    waveform_bar_count: int = 5
    fade_out_ms: int = 200


@dataclass
class AudioConfig:
    mute_background: bool = False


@dataclass
class Config:
    stt: STTConfig = field(default_factory=STTConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    commands: CommandsConfig = field(default_factory=CommandsConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    modes: ModesConfig = field(default_factory=ModesConfig)  # NEU
    pill: PillConfig = field(default_factory=PillConfig)  # NEU
    audio: AudioConfig = field(default_factory=AudioConfig)  # NEU v0.3.0


def load(config_path: Path | None = None) -> Config:
    """Lädt Config aus TOML, erzeugt Defaults wenn Datei fehlt."""
    path = config_path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        path.write_text(DEFAULTS_TOML)

    with path.open("rb") as f:
        data = tomllib.load(f)

    cfg = Config()
    if "stt" in data:
        cfg.stt = STTConfig(**data["stt"])
    if "hotkey" in data:
        cfg.hotkey = HotkeyConfig(**data["hotkey"])
    if "recording" in data:
        cfg.recording = RecordingConfig(**data["recording"])

    if cfg.recording.max_duration_s in _STALE_MAX_DURATION_DEFAULTS:
        log.info(
            "Migrating recording.max_duration_s from %.1fs to 600.0s (v0.4.0 default)",
            cfg.recording.max_duration_s,
        )
        cfg.recording.max_duration_s = 600.0

    if "cleanup" in data:
        cleanup_data = {k: v for k, v in data["cleanup"].items() if k != "hotwords"}
        cfg.cleanup = CleanupConfig(**cleanup_data)
        if "hotwords" in data["cleanup"]:
            cfg.cleanup.hotwords = data["cleanup"]["hotwords"].get("words", [])
    if "commands" in data:
        cfg.commands = CommandsConfig(**data["commands"])
    if "output" in data:
        cfg.output = OutputConfig(**data["output"])
    if "logging" in data:
        cfg.logging = LoggingConfig(**data["logging"])
    if "modes" in data:
        cfg.modes = ModesConfig(**data["modes"])
    if "pill" in data:
        cfg.pill = PillConfig(**data["pill"])
    if "audio" in data:
        cfg.audio = AudioConfig(**data["audio"])

    # API-Key-Priorität: ENV > TOML > leer
    env_key = os.environ.get("GROQ_API_KEY", "")
    if env_key:
        cfg.cleanup.api_key = env_key
    elif "cleanup" in data and "api_key" in data["cleanup"]:
        cfg.cleanup.api_key = data["cleanup"]["api_key"]
    # sonst: bleibt "" (Default aus dataclass)

    return cfg


def save(config: Config, config_path: Path | None = None) -> None:
    """Atomic write: tmpfile + rename. Result is chmod 0600 (Bearer token inside)."""
    path = config_path or DEFAULT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    data = _serialize(config)
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_bytes(tomli_w.dumps(data).encode("utf-8"))
    tmp.replace(path)  # atomic on POSIX
    try:
        os.chmod(path, 0o600)
    except OSError:
        log.warning("Could not chmod %s to 0600", path)


def _serialize(config: Config) -> dict:
    """Config-dataclass zu dict für TOML-Schreiben."""
    return {
        "stt": {
            "model": config.stt.model,
            "language": config.stt.language,
        },
        "hotkey": {
            "mode": config.hotkey.mode,
            "key": config.hotkey.key,
            "double_tap_window_ms": config.hotkey.double_tap_window_ms,
        },
        "recording": {
            "min_duration_s": config.recording.min_duration_s,
            "max_duration_s": config.recording.max_duration_s,
            "sample_rate": config.recording.sample_rate,
        },
        "cleanup": {
            "enabled": config.cleanup.enabled,
            "provider": config.cleanup.provider,
            "model": config.cleanup.model,
            "timeout_s": config.cleanup.timeout_s,
            "retry": config.cleanup.retry,
            "api_key": config.cleanup.api_key,
            "hotwords": {"words": config.cleanup.hotwords},
        },
        "commands": {
            "enabled": config.commands.enabled,
            "triggers": config.commands.triggers,
        },
        "output": {
            "clipboard_restore_delay_ms": config.output.clipboard_restore_delay_ms,
        },
        "logging": {
            "level": config.logging.level,
            "keep_transcripts": config.logging.keep_transcripts,
        },
        "modes": {
            "default": config.modes.default,
        },
        "pill": {
            "enabled": config.pill.enabled,
            "mode_indicator": config.pill.mode_indicator,
            "waveform_bar_count": config.pill.waveform_bar_count,
            "fade_out_ms": config.pill.fade_out_ms,
        },
        "audio": {
            "mute_background": config.audio.mute_background,
        },
    }
