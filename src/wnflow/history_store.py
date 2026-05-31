"""History-Persistence für das Hauptfenster.

JSON-File unter ~/.worknetic-flow/history.json. Append-only, mit cap
auf MAX_ITEMS damit die Datei nicht explodiert.

Eintrag:
  {
    "ts": 1716987600.5,        # unix epoch seconds
    "text": "Antwort an Steffen ...",
    "words": 22,
    "mode": "verbatim",
    "duration_s": 8.4,
  }

KPIs (wöchentlich, Mo–So lokaler Zeitzone):
  - words_week: int       (Summe Wörter dieser Woche)
  - speed_factor: float   (gesprochen vs. tippen-Schätzung: ~40wpm tippen)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

HISTORY_PATH = Path.home() / ".worknetic-flow" / "history.json"
MAX_ITEMS = 500
# Annahme für "schneller als tippen": Durchschnittstipper schafft 40 WPM
# → 40/60 = 0.667 wörter pro sekunde. Wenn jemand schneller diktiert,
# fällt der Faktor höher aus.
TYPING_WPM = 40.0


_lock = threading.Lock()


def _ensure_dir() -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_raw() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        with HISTORY_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        log.exception("history load failed — starting fresh")
        return []


def _save_raw(items: list[dict[str, Any]]) -> None:
    _ensure_dir()
    tmp = HISTORY_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HISTORY_PATH)
    try:
        os.chmod(HISTORY_PATH, 0o600)
    except OSError:
        log.warning("Could not chmod %s to 0600", HISTORY_PATH)


def append(text: str, words: int, mode: str, duration_s: float) -> None:
    """Fuegt einen Eintrag hinzu. Thread-sicher."""
    if not text or words <= 0:
        return
    entry = {
        "ts": time.time(),
        "text": text,
        "words": int(words),
        "mode": str(mode),
        "duration_s": float(duration_s),
    }
    with _lock:
        items = _load_raw()
        items.append(entry)
        if len(items) > MAX_ITEMS:
            items = items[-MAX_ITEMS:]
        _save_raw(items)


def recent(limit: int = 50) -> list[dict[str, Any]]:
    """Gibt die letzten N Einträge zurück, neueste zuerst."""
    with _lock:
        items = _load_raw()
    items.sort(key=lambda it: it.get("ts", 0), reverse=True)
    return items[:limit]


def clear() -> None:
    """Löscht den gesamten Diktat-Verlauf. Thread-sicher."""
    with _lock:
        _save_raw([])


def kpis() -> dict[str, Any]:
    """Berechnet wöchentliche KPIs (Mo–So, lokale Zeit)."""
    with _lock:
        items = _load_raw()

    now = datetime.now()
    # Wochenstart: Montag 00:00 lokal
    start_of_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_ts = start_of_week.timestamp()

    week_items = [it for it in items if it.get("ts", 0) >= start_ts]
    words_week = sum(int(it.get("words", 0)) for it in week_items)

    total_duration = sum(float(it.get("duration_s", 0)) for it in week_items)
    if total_duration > 0 and words_week > 0:
        speak_wpm = words_week / (total_duration / 60.0)
        speed_factor = speak_wpm / TYPING_WPM
    else:
        speed_factor = None

    return {
        "words_week": words_week,
        "speed_factor": round(speed_factor, 1) if speed_factor else None,
    }


def payload(limit: int = 50) -> dict[str, Any]:
    """Bequeme Methode: Items + KPIs in einem Dict für JS."""
    return {"items": recent(limit), "kpis": kpis()}
