#!/usr/bin/env python3
"""Read-only AML339 V1 release health: configured != verified != published.

Never treats researched EMI legal entities as scanned ATS sources.
Never reads, modifies or publishes personal application information.
"""
from __future__ import annotations
import argparse
import datetime as dt
import http.client
import json
import sys
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.aml339_source_manifest import CORE, EXPANSION, REGULATED, REGULATOR50, REG100_LIVE, EXTERNAL50_LIVE, CATALOG_LIVE, OPTIONAL
from scripts.aml339_site import FEED_FILES, ROOT as PUBLIC_URL


def check_pages(summary_path: Path) -> dict:
    """Check the exact release files delivered to an anonymous Pages reader."""
    results = {}
    for name in ("summary.json", "index.html", *FEED_FILES.values()):
        path = summary_path if name == "summary.json" else summary_path.with_name(name)
        try:
            expected = path.read_bytes()
            if not expected:
                raise ValueError("empty local release file")
            request = urllib.request.Request(PUBLIC_URL + name, headers={
                "User-Agent": "AML339-release-health",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")
                matches = response.read(len(expected) + 1) == expected
            results[name] = "match" if matches else "different from committed release"
        except (OSError, ValueError, http.client.HTTPException) as exc:
            results[name] = str(exc)
    return results


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
    quarantined=summary.get("missing_or_failed_core",{})
    # One known Workable provider's HTTP429 may be omitted, but no other
    # original core can fail silently. Never count the blocked source as live.
    valid_quarantine=isinstance(quarantined,dict) and (
        (core==18 and not quarantined)
        or (core==17 and set(quarantined)=={"payabl"})
    )
    complete_core=(summary.get("core_sources_expected")==18
                   and summary.get("strict_core_sources_complete")==17
                   and valid_quarantine)
    recent=0<=age<=36
    has_new_source_metadata=(
        summary.get("regulator50_live_expected")==len(REGULATOR50)
        and summary.get("reg100_live_expected")==len(REG100_LIVE)
        and summary.get("reg100_research_leads")==100
        and summary.get("external50_live_expected")==len(EXTERNAL50_LIVE)
        and summary.get("catalog_live_expected",0)==len(CATALOG_LIVE)
    )
    minimum_live_sources=130
    sufficient_coverage=sources>=minimum_live_sources
    # The launch is not verified until the publication actually reflects the
    # current code's schema and the mandatory complete core, within 36 h.
    v1_published_verified=bool(
        recent and complete_core and history_guard and has_new_source_metadata
        and sufficient_coverage
        and summary.get("regulator50_discovered")==50
        and summary.get("sources_expected")==len(CORE+OPTIONAL)
    )
    return {
        "status":"VERIFIED_PRODUCTION" if v1_published_verified else "PENDING_PRODUCTION_VALIDATION",
        "checked_at_utc":summary["checked_at_utc"],
        "age_hours":round(age,2),
        "actual_verified_live_sources":sources,
        "configured_maximum_live_sources":len(CORE+OPTIONAL),
        "minimum_live_sources_for_stable_v1":minimum_live_sources,
        "sufficient_live_coverage":sufficient_coverage,
        "mandatory_core_expected":17,
        "original_core_expected":len(CORE),
        "quarantined_core_source_ids":sorted(quarantined) if isinstance(quarantined,dict) else [],
        "degraded_core_but_safe":bool(quarantined) if isinstance(quarantined,dict) else False,
        "mandatory_core_verified":17 if complete_core else 0,
        "original_core_verified":core,
        "novelty_history_guard_confirmed":history_guard,
        "100_extra_regulated_company_leads_imported":100,
        "100_extra_company_leads_with_verified_active_ats":summary.get("reg100_live_verified",0),
        "100_extra_company_live_sources_configured":len(REG100_LIVE),
        "newly_discovered_regulator50_live_configured":len(REGULATOR50),
        "catalog_live_configured":len(CATALOG_LIVE),
        "catalog_live_verified":summary.get("catalog_live_verified",0),
        "external50_live_configured":len(EXTERNAL50_LIVE),
        "external50_live_verified":summary.get("external50_live_verified",0),
        "fresh_publish":recent,
        "v1_published_verified":v1_published_verified,
        "limitations":[
            "100 extra companies were found in a secondary EMI registry, not individually certified active by national regulators",
            "The 100-company queue is the original research snapshot; sources graduated later are verified separately in the live source manifest",
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
    if args.require_live:
        v["public_files"] = check_pages(Path(args.summary))
        if any(result != "match" for result in v["public_files"].values()):
            v["status"] = "PENDING_PRODUCTION_VALIDATION"
            v["v1_published_verified"] = False
    elif v["v1_published_verified"]:
        v["status"] = "SNAPSHOT_READY_TO_VERIFY"
        v["v1_published_verified"] = False
    if args.out:
        Path(args.out).write_text(json.dumps(v,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("AML339_V1_RELEASE_STATUS",json.dumps(v,ensure_ascii=False),flush=True)
    if args.require_live and not v["v1_published_verified"]:
        raise SystemExit("V1 is not published/verified yet; do NOT report launch as complete")


if __name__=="__main__":main()
