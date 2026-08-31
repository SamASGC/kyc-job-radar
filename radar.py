#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from job_radar.config import ROOT
import job_radar.scanner as scanner_module
from job_radar.state import load_state
from job_radar.dashboard import build_dashboard


_BASE_LOAD_JSON = scanner_module.load_json


def _load_json_with_expansions(path):
    data = _BASE_LOAD_JSON(path)
    if str(path) == "config/companies.json":
        try:
            extra = _BASE_LOAD_JSON("config/extra_companies.json")
        except FileNotFoundError:
            extra = []
        if extra:
            existing = {str(x.get("name", "")).casefold() for x in data}
            data = list(data) + [x for x in extra if str(x.get("name", "")).casefold() not in existing]
    return data


# Keep expansion targets separate from the large original company file while making
# every normal scan (local and GitHub Actions) consume both lists transparently.
scanner_module.load_json = _load_json_with_expansions


def cmd_scan(args):
    stats = asyncio.run(scanner_module.run_scan())
    print(json.dumps(stats, indent=2, ensure_ascii=False))


def cmd_build(args):
    state = load_state()
    jobs = list(state.get("jobs", {}).values())
    jobs.sort(key=lambda x: (-int(x.get("score", 0)), x.get("company", ""), x.get("title", "")))
    build_dashboard(jobs, state.get("stats", {}), "public/index.html", state.get("dataset_updated_at", ""))
    print(f"Built: {ROOT / 'public/index.html'}")


def cmd_health(args):
    p = ROOT / "data/health.json"
    if not p.exists():
        print("No health report yet. Run: python radar.py scan")
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("sources", [])
    failed = [x for x in rows if not x.get("ok")]
    print(f"Sources: {len(rows)} | OK: {len(rows)-len(failed)} | Failed: {len(failed)}")
    for x in failed:
        print(f"- {x.get('company')}: {x.get('error')}")


def main():
    ap = argparse.ArgumentParser(description="KYC/KYB/AML hourly job radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="Fetch sources, score, dedupe, update state and dashboard").set_defaults(func=cmd_scan)
    sub.add_parser("build", help="Rebuild HTML from existing state without network").set_defaults(func=cmd_build)
    sub.add_parser("health", help="Show source failures from last scan").set_defaults(func=cmd_health)
    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
