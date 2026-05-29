"""Tests für config.py — TOML laden mit Defaults und ENV-Override."""

import os
from pathlib import Path

import pytest

from wnflow.config import Config, load


def test_load_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "nonexistent.toml"
    cfg = load(config_path=config_path)
    assert cfg.stt.model == "mlx-community/whisper-large-v3-turbo-q4"
    assert cfg.stt.language == "de"
    assert cfg.hotkey.key == "fn"
    assert cfg.hotkey.double_tap_window_ms == 350
    assert cfg.recording.max_duration_s == 60.0


def test_load_creates_default_file_if_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    load(config_path=config_path)
    assert config_path.exists()
    content = config_path.read_text()
    assert "[stt]" in content
    assert "mlx-community" in content


def test_load_respects_existing_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[hotkey]\nkey = "right_shift"\ndouble_tap_window_ms = 500\n'
    )
    cfg = load(config_path=config_path)
    assert cfg.hotkey.key == "right_shift"
    assert cfg.hotkey.double_tap_window_ms == 500
    # Defaults werden für nicht angegebene Werte verwendet
    assert cfg.stt.language == "de"


def test_groq_api_key_from_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_123")
    config_path = tmp_path / "config.toml"
    cfg = load(config_path=config_path)
    assert cfg.cleanup.api_key == "gsk_test_123"


def test_hotwords_loaded_as_list(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        '[cleanup.hotwords]\nwords = ["Worknetic", "Ridersystem", "BZKI"]\n'
    )
    cfg = load(config_path=config_path)
    assert cfg.cleanup.hotwords == ["Worknetic", "Ridersystem", "BZKI"]


def test_command_triggers_loaded(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    cfg = load(config_path=config_path)
    assert "Befehl:" in cfg.commands.triggers


def test_modes_default_is_verbatim(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    cfg = load(config_path=config_path)
    assert cfg.modes.default == "verbatim"


def test_pill_default_enabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    cfg = load(config_path=config_path)
    assert cfg.pill.enabled is True
    assert cfg.pill.mode_indicator is True
    assert cfg.pill.waveform_bar_count == 5


def test_modes_default_can_be_overridden(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[modes]\ndefault = "formal"\n')
    cfg = load(config_path=config_path)
    assert cfg.modes.default == "formal"


def test_pill_can_be_disabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text('[pill]\nenabled = false\n')
    cfg = load(config_path=config_path)
    assert cfg.pill.enabled is False


def test_config_save_writes_toml(tmp_path: Path) -> None:
    from wnflow.config import save

    config_path = tmp_path / "config.toml"
    cfg = load(config_path=config_path)
    cfg.stt.language = "en"
    cfg.cleanup.api_key = "gsk_test_123"
    save(cfg, config_path=config_path)

    # Reload und checken
    cfg2 = load(config_path=config_path)
    assert cfg2.stt.language == "en"


def test_config_save_atomic_via_tmp_file(tmp_path: Path) -> None:
    """Save soll atomic sein: tmpfile, dann rename."""
    from wnflow.config import save

    config_path = tmp_path / "config.toml"
    cfg = load(config_path=config_path)
    save(cfg, config_path=config_path)
    # Nach save existiert keine .tmp Datei
    assert not (tmp_path / "config.toml.tmp").exists()
    assert config_path.exists()


def test_config_language_default_is_de(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    cfg = load(config_path=config_path)
    assert cfg.stt.language == "de"


def test_config_save_preserves_modes_section(tmp_path: Path) -> None:
    """Save soll alle Sections schreiben — auch wenn nur ein Feld geändert."""
    from wnflow.config import save

    config_path = tmp_path / "config.toml"
    cfg = load(config_path=config_path)
    cfg.modes.default = "formal"
    save(cfg, config_path=config_path)
    cfg2 = load(config_path=config_path)
    assert cfg2.modes.default == "formal"


def test_config_save_writes_api_key_when_set(tmp_path: Path, monkeypatch) -> None:
    """Wenn api_key aus Settings-Window kommt, soll save es persistieren."""
    from wnflow.config import save

    # ENV temporär leeren
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    config_path = tmp_path / "config.toml"
    cfg = load(config_path=config_path)
    cfg.cleanup.api_key = "gsk_persistent"
    save(cfg, config_path=config_path)

    # Re-load liest aus TOML wenn ENV leer
    cfg2 = load(config_path=config_path)
    assert cfg2.cleanup.api_key == "gsk_persistent"
