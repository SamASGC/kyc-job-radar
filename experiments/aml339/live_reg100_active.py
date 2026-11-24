#!/usr/bin/env python3
"""Two audited official ATS sources from the 100-entity regulator research queue.

An isolated live audit MUST verify full source positive controls and every
geographically plausible AML job detail, with an official application URL.
Failed/partial sources cannot publish and never close previously seen roles.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path

from live_e2e18_full import audit_one
from live_reg100_pilot import SOURCES as RESEARCH_SOURCES

# No broader 7-source promotion: 3 failed and 2 only returned a single page
# even though their employer career sites expose more jobs. Only these two
# passed source-specific listing positive controls on a real Github runner.
LIVE_SOURCE_MINIMUM = {
    "reg100-be-paynovate": 5,
    "reg100-lu-pingpong-europe-s-a": 4,
}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True,choices=tuple(LIVE_SOURCE_MINIMUM))
    parser.add_argument("--out",required=True)
    parser.add_argument("--minutes",type=int,default=4)
    args=parser.parse_args()
    if not 1<=args.minutes<=5:raise SystemExit("Invalid bounded source budget")
    original=json.loads(Path("experiments/aml339/regulator100_discovery_queue.json").read_text(encoding="utf-8"))
    ids={row["id"] for row in original["candidates"]}
    if original["count"]!=100 or len(ids)!=100 or args.source not in ids:
        raise ValueError("Not a known legal entity of regulator100 discovery")
    config=RESEARCH_SOURCES[args.source]
    result=audit_one(config,minutes=args.minutes)
    min_count=LIVE_SOURCE_MINIMUM[args.source]
    if result.get("state")=="listing_extracted" and result.get("list_complete") is True:
        if not isinstance(result.get("total_listed"),int) or result["total_listed"]<min_count:
            result["state"]="listing_failed"
            result["list_complete"]=False
            result.setdefault("errors",[]).append(
                f"Official listing incomplete relative to confirmed baseline of {min_count} jobs")
    if result.get("unverified_in_scope",0):
        result["state"]="listing_failed"
        result["list_complete"]=False
        result.setdefault("errors",[]).append("Official in-scope job detail/application failed")
    result["employer_legal_entity_discovery_id"]=args.source
    report={
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "source_registry":"regulated_emi_reg100_live_v1",
        "original_catalog_sources":339,
        "total_configured_sources":339,
        "sources_requested":[args.source],
        "sources":[result],
    }
    Path(args.out).write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("REG100_PRODUCTION_ELIGIBLE",json.dumps({
       "id":args.source,"complete":result["list_complete"],
       "total_listed":result["total_listed"],
       "relevant":result["relevant_leads"],
       "audited":len(result["audited"]),
       "errors":result.get("errors",[]),
       "unverified_in_scope":result["unverified_in_scope"]
    },ensure_ascii=False),flush=True)
    if result["state"]!="listing_extracted" or result["list_complete"] is not True:
        raise SystemExit("Fail-closed source audit: "+args.source)

if __name__=="__main__":
    main()
