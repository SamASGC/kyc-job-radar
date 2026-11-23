#!/usr/bin/env python3
"""Live read-only source audit for five skill-relevant employer portals.

All five are ALREADY present in the immutable 339-company catalog but are not
part of the currently published 34-source radar. No alerts, state writes or
application submission may happen in this probe.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path

from live_e2e18_full import audit_one
from two_lane_alert_preview import triage

PRIORITY = (
    "colibrix-one",
    "genome",
    "wallester",
    "bybit",
    "zilch",
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=PRIORITY, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--minutes", type=int, default=4)
    args = p.parse_args()
    if not 1 <= args.minutes <= 5:
        raise SystemExit("Invalid live source audit budget")
    catalog = Path("fuentes.json")
    original = catalog.read_bytes()
    sources = json.loads(original)["sources"]
    indexed = {entry["id"]: entry for entry in sources}
    if len(sources)!=339 or len(indexed)!=339 or not set(PRIORITY).issubset(indexed):
        raise RuntimeError("Original 339-source catalog or priority IDs mismatched")
    report = audit_one(indexed[args.source], minutes=args.minutes)
    if catalog.read_bytes() != original:
        raise RuntimeError("Immutable catalog modified")
    for job in report.get("audited", []):
        item, reason = triage(args.source, job)
        e = job.get("evaluation") or {}
        print("PRIORITY5_ROLE", json.dumps({
            "employer_id": args.source,
            "title": job.get("title"),
            "url": job.get("url"),
            "location": job.get("location"),
            "class": e.get("class"),
            "duties": e.get("explicit_duties"),
            "barriers": e.get("barriers"),
            "uncertainties": e.get("uncertainties"),
            "date_status": e.get("publication_status"),
            "date_field": e.get("date_field"),
            "triage_lane": item.get("lane") if item else None,
            "triage_reason": reason,
            "application_verified": e.get("application_verified")
        }, ensure_ascii=False), flush=True)
    path = Path(args.out)
    path.write_text(json.dumps({
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "evidence_method": "FRESH_LIVE_HTTP_GET_WITH_INDIVIDUAL_DETAILS_WHEN_GEO_POSSIBLE",
        "total_configured_sources":339,
        "sources_requested":[args.source],
        "sources":[report]
    },indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if report.get("state")!="listing_extracted" or report.get("list_complete") is not True:
        raise SystemExit("Priority source incomplete")


if __name__=="__main__":
    main()
