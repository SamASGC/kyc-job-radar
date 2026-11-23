#!/usr/bin/env python3
"""Expansion candidates: independent LIVE detail audit; no history or notifications.

Reuses exactly the published 18-source pilot's audit_one implementation.
Each of these employer listings passed the earlier 48-source listing-only
exploration, but NONE is enabled for real alerts until a full canary passes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from live_e2e18_full import audit_one

CANDIDATES = (
    "iq-eq",
    "aztec-group",
    "ebury",
    "nexpay",
    "nium",
    "keyrock",
    "mirabaud",
    "convera",
    "complyadvantage",
    "hawk",
    "clearbank",
    "modulr",
    "lemonway",
    "ecommpay",
    "crossmint",
    "moonpay",
    "genome",
    "wallester",
    "bybit",
    "zilch",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, choices=CANDIDATES)
    parser.add_argument("--minutes", type=int, default=4)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not 1 <= args.minutes <= 5:
        raise SystemExit("Unexpected source time budget")
    source_file = Path("fuentes.json")
    original = source_file.read_bytes()
    sources = json.loads(original)["sources"]
    ids = [s["id"] for s in sources]
    if len(ids) != 339 or len(set(ids)) != 339:
        raise RuntimeError("339-source archive has unexpected schema/catalog size")
    if not set(CANDIDATES).issubset(set(ids)):
        raise RuntimeError("Expansion candidates missing from original 339-source catalog")
    by_id = {x["id"]: x for x in sources}
    result = audit_one(by_id[args.source], minutes=args.minutes)
    if source_file.read_bytes() != original:
        raise RuntimeError("Immutable source catalog was mutated")
    data = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "evidence_method": "FRESH_LIVE_HTTP_GET_WITH_INDIVIDUAL_DETAILS_WHEN_GEO_POSSIBLE",
        "total_configured_sources": 339,
        "sources_requested": [args.source],
        "sources": [result],
    }
    Path(args.out).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if result["state"] != "listing_extracted" or result["list_complete"] is not True:
        raise SystemExit("Expansion source audit incomplete: " + args.source)


if __name__ == "__main__":
    main()
