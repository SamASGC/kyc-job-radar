#!/usr/bin/env python3
"""Isolated read-only full audit for each of the third fifty candidate portals."""
import argparse
import datetime as dt
import json
from pathlib import Path

from third_wave50_sources import WAVE50_C
from live_e2e18_full import audit_one
from two_lane_alert_preview import triage


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,choices=WAVE50_C)
    p.add_argument("--minutes",type=int,default=3)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    if not 1<=a.minutes<=5:
        raise SystemExit("Invalid source budget")
    catalog=Path("fuentes.json")
    before=catalog.read_bytes()
    rows=json.loads(before)["sources"]
    index={row["id"]:row for row in rows}
    if len(rows)!=339 or len(index)!=339:
        raise RuntimeError("Pinned source catalog invalid")
    if not set(WAVE50_C).issubset(index):
        raise RuntimeError("Unexpected employer not in pinned catalog")
    if "workable" in str(index[a.source].get("route",[])).lower():
        raise RuntimeError("Workable provider is excluded from this canary during cooldown")
    result=audit_one(index[a.source],minutes=a.minutes)
    if catalog.read_bytes()!=before:
        raise RuntimeError("Read-only original 339 source catalog was modified")
    eligible={}
    for job in result.get("audited",[]):
        alert,reason=triage(a.source,job)
        lane=alert["lane"] if alert else "filtered"
        eligible[lane]=eligible.get(lane,0)+1
        if alert:
            print("THIRD50_JOB",json.dumps({
                "source":a.source,"title":job.get("title"),
                "location":job.get("location"),"lane":lane,
                "url":job.get("url"),"original_date_status":job.get("evaluation",{}).get("publication_status"),
                "verified_duties":job.get("evaluation",{}).get("explicit_duties")
            },ensure_ascii=False)[:1600],flush=True)
    data={
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "source_registry":"original_339",
        "batch":"THIRD50_C_20261124",
        "total_configured_sources":339,
        "sources_requested":[a.source],
        "sources":[result],
    }
    Path(a.out).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    complete=(result.get("state")=="listing_extracted" and
              result.get("list_complete") is True and
              isinstance(result.get("relevant_leads"),int) and
              result["relevant_leads"]==len(result.get("audited",[])) and
              result.get("unverified_in_scope")==0 and
              isinstance(result.get("listing_role_keys"),list))
    print("THIRD50_SOURCE",json.dumps({
        "source":a.source,"complete":bool(complete),
        "listed":result.get("total_listed"),"matching_titles":result.get("relevant_leads"),
        "full_details_checked":len(result.get("audited",[])),
        "unverified_in_scope":result.get("unverified_in_scope"),
        "qualified_lanes":eligible,
        "errors":result.get("errors",[])[:2]
    },ensure_ascii=False),flush=True)
    if not complete:
        raise SystemExit("Full official source audit incomplete; reject from live coverage")


if __name__=="__main__":
    main()
