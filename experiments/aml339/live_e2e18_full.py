#!/usr/bin/env python3
"""Full current HTTP refresh of one of 18 audit-source employers.

Every title-matched row is accounted for. Detail HTTP is skipped ONLY for a
geographically explicit out-of-scope listing; other rows are hydrated, their
application route is checked, and requirements are re-evaluated. No alert ever
sent by this script; no production state touched.
"""
from __future__ import annotations
import argparse,datetime as dt,json,time
from pathlib import Path
from amlradar.net import Client
from amlradar.sources import Board
from amlradar.model import clean,plain
from quality_audit import candidate,prioritize,role_geography,evaluate
from two_lane_alert_preview import listing_identity

OUTSIDE={"outside_scope","excluded_barcelona"}
SOURCES={
 "vinted","verifo-lithuania","demivolt-lithuania","lt-neo-finance","swedbank","luminor",
 "n26","wise","corpay","openpayd","transfergo","bvnk",
 "bnf-bank-malta","medirect-bank-malta","payabl","airwallex","mollie","truelayer"
}

def audit_one(source,minutes=4):
    client=Client(timeout=12,deadline=time.monotonic()+minutes*60)
    board=Board(source,client,max_minutes=minutes)
    result={"source_id":source["id"],"employer":source["name"],"state":"listing_failed",
        "list_complete":False,"relevant_leads":None,"total_listed":None,
        "audited_offset":0,"audited":[],"warnings":[],"errors":[],
        "skipped_details_outside_geo":0,"attempted_in_scope_details":0,
        "unverified_in_scope":0,"listing_role_keys":[],"listing_untrackable_count":0}
    try:
        full=board.listing()
        # Observe ALL official listing identifiers, not just the jobs our current
        # title/skill parser selects. This stops a later parser improvement from
        # presenting an old vacancy as a genuinely new discovery.
        all_keys=[listing_identity(source["id"],job) for job in full]
        result["listing_role_keys"]=sorted({k for k in all_keys if k})
        result["listing_untrackable_count"]=sum(not bool(k) for k in all_keys)
        selected=[j for j in full if candidate(j)]
        selected.sort(key=prioritize)
        result.update(state="listing_extracted",list_complete=board.complete,
            total_listed=len(full),relevant_leads=len(selected))
        for i,job in enumerate(selected):
            loc=role_geography(job.get("location"))
            verified=False
            error=None
            if loc in OUTSIDE:
                result["skipped_details_outside_geo"]+=1
                error="LOCATION_OUTSIDE_SCOPE: detail not fetched; source listing location used"
            else:
                result["attempted_in_scope_details"]+=1
                try:
                    board.hydrate(job)
                    if "_page" not in job:board.read_post(job)
                    board.verify(job)
                    verified=True
                except Exception as exc:
                    error=type(exc).__name__+": "+str(exc)[:190]
                    result["unverified_in_scope"]+=1
            evaluation=evaluate(job,verified)
            result["audited"].append({"title":clean(job.get("title")),
                "url":job.get("url"),"apply_url":job.get("apply_url") if verified else None,
                "location":clean(job.get("location")),
                "hiring_organization":clean(job.get("hiring_organization")),
                "description_length":len(plain(job.get("description"))),
                "verification_error":error or "",
                "detail_skipped_outside_geo":loc in OUTSIDE,"evaluation":evaluation})
        result["warnings"]=board.warnings[:8]
        if not board.complete or len(result["audited"])!=result["relevant_leads"]:
            raise ValueError("Incomplete detail coverage")
    except Exception as exc:
        result.update(state="listing_failed",list_complete=False,
            errors=result["errors"]+[type(exc).__name__+": "+str(exc)[:220]])
    print("LIVE_FULL_SOURCE",json.dumps({"source":source["id"],
        "state":result["state"],"listed":result["total_listed"],
        "matched":result["relevant_leads"],"covered":len(result["audited"]),
        "skipped_outside":result["skipped_details_outside_geo"],
        "details_attempted":result["attempted_in_scope_details"],
        "unverified_in_scope":result["unverified_in_scope"],
        "errors":result["errors"]},ensure_ascii=False),flush=True)
    return result

def self_tests():
    assert len(SOURCES)==18
    assert OUTSIDE=={"outside_scope","excluded_barcelona"}
    assert "unknown" not in OUTSIDE and "mixed_location_review" not in OUTSIDE
    print("LIVE_FULL_18_SOURCE_TESTS_PASSED",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--minutes",type=int,default=4)
    a=p.parse_args()
    self_tests()
    if a.source not in SOURCES or not 1<=a.minutes<=5:
        raise SystemExit("Source/budget outside isolated pilot")
    path=Path("fuentes.json")
    original=path.read_bytes()
    sources=json.loads(original)["sources"]
    by={x["id"]:x for x in sources}
    assert len(sources)==len(by)==339
    result=audit_one(by[a.source],minutes=a.minutes)
    assert path.read_bytes()==original,"Source catalogue unexpectedly modified"
    out={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "evidence_method":"FRESH_LIVE_HTTP_GET_WITH_INDIVIDUAL_DETAILS_WHEN_GEO_POSSIBLE",
        "total_configured_sources":len(by),"sources_requested":[a.source],
        "sources":[result]}
    Path(a.out).write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    # Report captures errors; return nonzero for an incomplete listing/partial
    # detail scan so CI never publishes a new history state.
    if result["state"]!="listing_extracted" or not result["list_complete"]:
        raise SystemExit("Source failed: "+a.source)

if __name__=="__main__":main()
