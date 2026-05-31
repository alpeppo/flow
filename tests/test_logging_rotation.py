"""Logging uses RotatingFileHandler (not plain FileHandler) and silences
chatty third-party libraries at INFO/DEBUG."""

import logging
from logging.handlers import RotatingFileHandler


def test_root_logger_uses_rotating_file_handler(tmp_path, monkeypatch) -> None:
    """After _configure_logging runs, the root logger should have a
    RotatingFileHandler — not the bare FileHandler."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for h in list(logging.getLogger().handlers):
        logging.getLogger().removeHandler(h)

    from wnflow.config import LoggingConfig
    from wnflow.app import _configure_logging

    _configure_logging(LoggingConfig(level="info"))

    rotating = [
        h for h in logging.getLogger().handlers
        if isinstance(h, RotatingFileHandler)
    ]
    assert len(rotating) == 1


def test_chatty_libraries_are_warned_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for h in list(logging.getLogger().handlers):
        logging.getLogger().removeHandler(h)

    from wnflow.config import LoggingConfig
    from wnflow.app import _configure_logging

    _configure_logging(LoggingConfig(level="debug"))

    for name in ("httpx", "httpcore", "urllib3", "huggingface_hub"):
        assert logging.getLogger(name).level == logging.WARNING, \
            f"{name} should be WARNING, was {logging.getLogger(name).level}"


def test_keep_transcripts_default_is_false() -> None:
    """Audit Finding 3 follow-up: dataclass default stays False so
    new installations don't log raw dictations by default."""
    from wnflow.config import LoggingConfig

    assert LoggingConfig().keep_transcripts is False
