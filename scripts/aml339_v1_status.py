#!/usr/bin/env python3
"""Read-only AML339 V1 release health: configured != verified != published.

Never treats researched EMI legal entities as scanned ATS sources.
Never reads, modifies or publishes personal application information.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.aml339_source_manifest import CORE, EXPANSION, REGULATED, REGULATOR50, OPTIONAL


def evaluate(summary: dict, candidates: dict, *, now: dt.datetime | None=None) -> dict:
    if not isinstance(summary,dict) or not isinstance(candidates,dict):
        raise ValueError("Missing or invalid release evidence")
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Release health requires an offset-aware current time")
    scan=dt.datetime.fromisoformat(summary["checked_at_utc"].replace("Z","+00:00"))
    if scan.tzinfo is None:
        raise ValueError("Untrusted timestamp without timezone")
    if candidates.get("count")!=100 or len(candidates.get("candidates",[]))!=100:
        raise ValueError("Incomplete 100-company discovery registry")
    if len({c["id"] for c in candidates["candidates"]})!=100:
        raise ValueError("Duplicate researched entity IDs")
    for item in candidates["candidates"]:
        if item.get("live_monitoring_enabled") is not False:
            raise ValueError("A research-only EMI entity cannot claim live monitoring")
        if item.get("licence_verified_national_authority") is not False:
            raise ValueError("Unverified EMI licence reported as proven")
        if item.get("official_ats_verified") is not False:
            raise ValueError("Unverified official ATS reported as proven")

    sources=summary.get("sources_complete")
    if type(sources) is not int or sources<0 or sources>len(CORE+OPTIONAL):
        raise ValueError("Invalid production source count")
    core=summary.get("core_sources_complete")
    if type(core) is not int or not 0<=core<=len(CORE):
        raise ValueError("Invalid core verification count")
    age=(now-scan).total_seconds()/3600
    history_guard=summary.get("novelty_guard_enabled") is True
    complete_core=core==len(CORE)
    recent=0<=age<=36
    has_new_source_metadata=summary.get("regulator50_live_expected")==len(REGULATOR50)
    # The launch is not verified until the publication actually reflects the
    # current code's schema and the mandatory complete core, within 36 h.
    v1_published_verified=bool(
        recent and complete_core and history_guard and has_new_source_metadata
        and summary.get("regulator50_discovered")==50
        and summary.get("sources_expected")==len(CORE+OPTIONAL)
    )
    return {
        "status":"VERIFIED_PRODUCTION" if v1_published_verified else "PENDING_PRODUCTION_VALIDATION",
        "checked_at_utc":summary["checked_at_utc"],
        "age_hours":round(age,2),
        "actual_verified_live_sources":sources,
        "configured_maximum_live_sources":len(CORE+OPTIONAL),
        "mandatory_core_expected":len(CORE),
        "mandatory_core_verified":core,
        "novelty_history_guard_confirmed":history_guard,
        "100_extra_regulated_company_leads_imported":100,
        "100_extra_company_leads_with_verified_active_ats":0,
        "newly_discovered_regulator50_live_configured":len(REGULATOR50),
        "fresh_publish":recent,
        "v1_published_verified":v1_published_verified,
        "limitations":[
            "100 extra companies were found in a secondary EMI registry, not individually certified active by national regulators",
            "No official ATS or jobs verified for any of the extra 100 research-only entries",
            "The 100 research-only leads are excluded from daily live source count and alert notifications",
            "Only a completed and published production scan confirms actual V1 readiness",
        ],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--summary",default=str(ROOT/"public/aml339/summary.json"))
    p.add_argument("--candidates",default=str(ROOT/"experiments/aml339/regulator100_discovery_queue.json"))
    p.add_argument("--require-live",action="store_true",
                   help="Exit failure unless V1 actually verified in the published production data")
    p.add_argument("--out",help="Optional local status artifact; never writes production state")
    args=p.parse_args()
    v=evaluate(json.loads(Path(args.summary).read_text(encoding="utf-8")),
               json.loads(Path(args.candidates).read_text(encoding="utf-8")))
    if args.out:
        Path(args.out).write_text(json.dumps(v,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("AML339_V1_RELEASE_STATUS",json.dumps(v,ensure_ascii=False),flush=True)
    if args.require_live and not v["v1_published_verified"]:
        raise SystemExit("V1 is not published/verified yet; do NOT report launch as complete")


if __name__=="__main__":main()
