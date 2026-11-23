#!/usr/bin/env python3
"""Dry-run ONLY: second batch of FinCrime-relevant providers for AML339.

The eight candidates all appeared in the earlier 48-source listing probe;
no alert is sent, and the original 339-source archive is immutable.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from live_e2e18_full import audit_one
from two_lane_alert_preview import triage

BRIDGE_CANDIDATES = (
    "complyadvantage",
    "hawk",
    "clearbank",
    "modulr",
    "lemonway",
    "ecommpay",
    "crossmint",
    "moonpay",
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=BRIDGE_CANDIDATES + ("transfergo",), required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--minutes", type=int, default=4)
    args = p.parse_args()
    if not 1 <= args.minutes <= 5:
        raise SystemExit("Unexpected source time budget")
    path = Path("fuentes.json")
    original = path.read_bytes()
    rows = json.loads(original)["sources"]
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(rows) or len(rows) != 339:
        raise RuntimeError("Pinned original 339-source catalog invalid")
    if not set(BRIDGE_CANDIDATES + ("transfergo",)).issubset(by_id):
        raise RuntimeError("One or more bridge source IDs missing from immutable catalog")
    scanned = audit_one(by_id[args.source], minutes=args.minutes)
    if path.read_bytes() != original:
        raise RuntimeError("Source catalog mutated")
    for row in scanned.get("audited", []):
        item, reason = triage(args.source, row)
        print("BRIDGE_ROLE_TRIAGE", json.dumps({
            "source": args.source,
            "title": row.get("title"),
            "url": row.get("url"),
            "location": row.get("location"),
            "class": row.get("evaluation", {}).get("class"),
            "geography": row.get("evaluation", {}).get("geography"),
            "date_status": row.get("evaluation", {}).get("publication_status"),
            "date_field": row.get("evaluation", {}).get("date_field"),
            "explicit_duties": row.get("evaluation", {}).get("explicit_duties"),
            "barriers": row.get("evaluation", {}).get("barriers"),
            "uncertainties": row.get("evaluation", {}).get("uncertainties"),
            "triage_lane": item["lane"] if item else None,
            "triage_reason": reason,
        }, ensure_ascii=False), flush=True)
    document = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "evidence_method": "FRESH_LIVE_HTTP_GET_WITH_INDIVIDUAL_DETAILS_WHEN_GEO_POSSIBLE",
        "total_configured_sources": 339,
        "sources_requested": [args.source],
        "sources": [scanned],
    }
    Path(args.out).write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if scanned["state"] != "listing_extracted" or scanned["list_complete"] is not True:
        raise SystemExit("Bridge candidate listing incomplete: " + args.source)


if __name__ == "__main__":
    main()
