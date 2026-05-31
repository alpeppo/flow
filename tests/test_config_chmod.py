"""config.save() must set 0600 permissions, and load() must migrate stale max_duration_s defaults."""

import os
import stat
from pathlib import Path

import tomli_w

from wnflow.config import Config, load, save


def test_save_sets_owner_only_permissions(tmp_path: Path) -> None:
    cfg = Config()
    cfg.cleanup.api_key = "gsk_test_value"
    target = tmp_path / "config.toml"

    save(cfg, target)

    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"


def test_save_overwrites_world_readable_permissions(tmp_path: Path) -> None:
    """If the file already exists with 0644, save() must tighten it."""
    target = tmp_path / "config.toml"
    target.write_text("[stt]\nmodel = \"x\"\n")
    target.chmod(0o644)

    cfg = Config()
    save(cfg, target)

    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600


def test_max_duration_default_is_600s() -> None:
    """v0.4.0 reintroduces a 10-minute cap (Finding 6)."""
    cfg = Config()
    assert cfg.recording.max_duration_s == 600.0


def test_load_migrates_v02_default_max_duration(tmp_path: Path) -> None:
    """Old 60.0 (v0.2 default) is migrated to 600.0 (v0.4.0 default)."""
    target = tmp_path / "config.toml"
    target.write_bytes(tomli_w.dumps({
        "recording": {"min_duration_s": 0.5, "max_duration_s": 60.0, "sample_rate": 16000}
    }).encode("utf-8"))

    cfg = load(target)

    assert cfg.recording.max_duration_s == 600.0


def test_load_migrates_v030_uncapped_max_duration(tmp_path: Path) -> None:
    """0.0 (v0.3 unbounded) is also migrated to 600.0."""
    target = tmp_path / "config.toml"
    target.write_bytes(tomli_w.dumps({
        "recording": {"min_duration_s": 0.5, "max_duration_s": 0.0, "sample_rate": 16000}
    }).encode("utf-8"))

    cfg = load(target)

    assert cfg.recording.max_duration_s == 600.0


def test_load_keeps_explicit_user_override(tmp_path: Path) -> None:
    """If the user has chosen something explicit (e.g. 300s), we don't touch it."""
    target = tmp_path / "config.toml"
    target.write_bytes(tomli_w.dumps({
        "recording": {"min_duration_s": 0.5, "max_duration_s": 300.0, "sample_rate": 16000}
    }).encode("utf-8"))

    cfg = load(target)

    assert cfg.recording.max_duration_s == 300.0
