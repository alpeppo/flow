"""history_store.clear() empties the file; chmod 0600 on every write."""

import stat
from pathlib import Path

import wnflow.history_store as hs


def _with_history_path(tmp_path: Path, monkeypatch):
    target = tmp_path / "history.json"
    monkeypatch.setattr(hs, "HISTORY_PATH", target)
    return target


def test_append_sets_owner_only_permissions(tmp_path, monkeypatch) -> None:
    target = _with_history_path(tmp_path, monkeypatch)
    hs.append(text="hello world", words=2, mode="verbatim", duration_s=1.5)
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600


def test_clear_empties_history(tmp_path, monkeypatch) -> None:
    target = _with_history_path(tmp_path, monkeypatch)
    hs.append(text="one", words=1, mode="verbatim", duration_s=1.0)
    hs.append(text="two", words=1, mode="verbatim", duration_s=1.0)
    assert len(hs.recent()) == 2

    hs.clear()

    assert hs.recent() == []
    assert target.exists(), "clear() should keep the empty file, not delete it"


def test_clear_is_idempotent(tmp_path, monkeypatch) -> None:
    _with_history_path(tmp_path, monkeypatch)
    hs.clear()
    hs.clear()
    assert hs.recent() == []
