from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from job_radar.config import load_json, save_json, ROOT


def default_state() -> dict:
    return {
        "version": 1,
        "seen": {},
        "jobs": {},
        "discovery": {},
        "last_scan": "",
        "stats": {},
    }


def load_state(path: str = "data/state.json") -> dict:
    p = ROOT / path
    if not p.exists():
        return default_state()
    data = load_json(path)
    base = default_state()
    base.update(data)
    base.setdefault("seen", {})
    base.setdefault("jobs", {})
    base.setdefault("discovery", {})
    return base


def save_state(state: dict, path: str = "data/state.json") -> None:
    save_json(path, state)
