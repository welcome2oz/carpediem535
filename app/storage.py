"""Persistent storage for ocean freight rates.

Rates are keyed by "ORIGIN-DEST" country code pairs and stored as a flat JSON
file so they survive restarts and can be hand-edited if needed. A file lock
keeps concurrent API/scraper writes safe.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

DATA_DIR = Path(__file__).parent / "data"
RATES_FILE = DATA_DIR / "freight_rates.json"

Source = Literal["seed", "manual", "scraped"]

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_raw() -> dict:
    if not RATES_FILE.exists():
        return {}
    with RATES_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_raw(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = RATES_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
    tmp.replace(RATES_FILE)


def get_all() -> dict:
    with _lock:
        return _read_raw()


def get_rate(route_key: str) -> dict | None:
    with _lock:
        return _read_raw().get(route_key)


def set_rate(route_key: str, rate: float, source: Source, note: str = "") -> dict:
    with _lock:
        data = _read_raw()
        entry = {
            "rate": rate,
            "currency": "USD",
            "updatedAt": _now(),
            "source": source,
            "note": note,
        }
        data[route_key] = entry
        _write_raw(data)
        return entry


def set_many(entries: dict[str, float], source: Source, note: str = "") -> int:
    with _lock:
        data = _read_raw()
        ts = _now()
        count = 0
        for route_key, rate in entries.items():
            if not isinstance(rate, (int, float)):
                continue
            data[route_key] = {
                "rate": rate,
                "currency": "USD",
                "updatedAt": ts,
                "source": source,
                "note": note,
            }
            count += 1
        _write_raw(data)
        return count


def seed_if_empty(country_codes: list[str]) -> None:
    """Populate a baseline mock rate for every route so the app is usable out of the box."""
    with _lock:
        data = _read_raw()
        if data:
            return
        ts = _now()
        for i, origin in enumerate(country_codes):
            for j, dest in enumerate(country_codes):
                if origin == dest:
                    continue
                distance = abs(i - j)
                mock_rate = 1000 + distance * 600
                data[f"{origin}-{dest}"] = {
                    "rate": mock_rate,
                    "currency": "USD",
                    "updatedAt": ts,
                    "source": "seed",
                    "note": "초기 샘플 값 (실제 운임 아님)",
                }
        _write_raw(data)
