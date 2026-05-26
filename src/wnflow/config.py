"""Config-Modul: TOML laden + Defaults schreiben + ENV-Override.

Default-Pfad: ~/.worknetic-flow/config.toml
Wenn Datei fehlt, wird sie mit Defaults erzeugt.
ENV-Override nur für Secrets (GROQ_API_KEY).
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".worknetic-flow" / "config.toml"

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
max_duration_s = 60.0
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
    max_duration_s: float = 60.0
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
class Config:
    stt: STTConfig = field(default_factory=STTConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    commands: CommandsConfig = field(default_factory=CommandsConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


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

    # ENV-Override für Secrets
    cfg.cleanup.api_key = os.environ.get("GROQ_API_KEY", "")

    return cfg
