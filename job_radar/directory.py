"""Rotating discovery of long-tail fintech company career pages.

A directory row is NOT a live job source until it has a real HTTPS website
and the radar has discovered its ATS. This prevents marketing a 4,291-firm
directory as 4,291 verified/monitored vacancy feeds.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def usable_website(url: str) -> bool:
    try:
        p = urlsplit(url)
        return p.scheme == "https" and bool(p.hostname) and "." in p.hostname and not p.username
    except (ValueError, TypeError):
        return False


def rotate_company_directory(
    rows: list[dict],
    discovered: dict,
    configured_names: set[str],
    hour: int,
    cold_per_hour: int = 180,
    hot_per_hour: int = 250,
) -> tuple[list[dict], dict]:
    """Choose previously discovered ATS targets first, plus rotating prospects."""
    seen = {n.casefold().strip() for n in configured_names}
    candidates = [
        x for x in rows if isinstance(x, dict)
        and x.get("name") and usable_website(x.get("website", ""))
        and x.get("enabled", True) and x["name"].casefold().strip() not in seen
    ]
    candidates.sort(key=lambda x: (x.get("priority", 50), x["name"].casefold()))
    hot, cold = [], []
    for x in candidates:
        item = {
            "name": x["name"],
            "careers_url": x["website"],
            "sector": x.get("sector", "Fintech"),
            "priority": x.get("priority", 50),
            "enabled": True,
        }
        if discovered.get(x["name"], {}).get("targets"):
            hot.append(item)
        else:
            cold.append(item)

    def chunk(items: list, limit: int, offset_hour: int) -> list:
        if not items or limit <= 0:
            return []
        count = min(limit, len(items))
        start = (offset_hour * count) % len(items)
        return [items[(start + i) % len(items)] for i in range(count)]

    chosen_hot = chunk(hot, hot_per_hour, hour)
    chosen_cold = chunk(cold, cold_per_hour, hour)
    return chosen_hot + chosen_cold, {
        "directory_rows": len(rows),
        "with_valid_websites": len(candidates),
        "discovered_ats": len(hot),
        "sampled_this_run": len(chosen_hot) + len(chosen_cold),
        "sampled_this_hour": len(chosen_hot) + len(chosen_cold),
    }


def load_directory_batch(
    path: Path,
    discovered: dict,
    configured_names: set[str],
    cold_per_hour: int = 180,
    hot_per_hour: int = 250,
    now: datetime | None = None,
) -> tuple[list[dict], dict]:
    if not path.exists():
        return [], {"directory_rows": 0, "with_valid_websites": 0,
                    "discovered_ats": 0, "sampled_this_hour": 0}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Directory must contain a list of companies")
    # Enrichment records are independently verified leads; preserve the
    # attributed upstream licensed register byte-for-byte.
    overlay_path = path.parent / "verified_company_websites.json"
    if overlay_path.exists():
        from job_radar.website_enrichment import overlay_directory
        overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        if isinstance(overlay, list):
            data = overlay_directory(data, overlay)
    now = now or datetime.now(timezone.utc)
    # Main workflow runs at :17 and :47, so successive half-hour slots
    # should inspect different businesses, not the same hourly slice twice.
    scan_slot = int(now.timestamp() // 1800)
    return rotate_company_directory(data, discovered, configured_names, scan_slot,
                                    cold_per_hour, hot_per_hour)
