#!/usr/bin/env python3
"""Reconstruct 18 employer evidence reports from source-scoped HTTP captures.

Strictly stop on gaps, repeated offsets, changed relevant-title counts, incomplete
sources or expired source observations. This merges already fetched real postings;
it does not claim to re-fetch HTML nor proves all 339 sources are good.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

GROUPS={
 "baltics":["vinted","verifo-lithuania","demivolt-lithuania","lt-neo-finance","swedbank","luminor"],
 "international":["n26","wise","corpay","openpayd","transfergo","bvnk"],
 "financial":["bnf-bank-malta","medirect-bank-malta","payabl","airwallex","mollie","truelayer"],
}
EXPECTED={name for group in GROUPS.values() for name in group}
EXPECTED_TOTAL=197

def at_utc(value):
    moment=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    if moment.tzinfo is None:raise ValueError("Naive source observation")
    return moment.astimezone(dt.timezone.utc)

def reconstruct(evidence,now=None,max_age_hours=12):
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:raise ValueError("Naive current time")
    indexed=defaultdict(dict)
    roots={}
    times=[]
    for p,data in evidence:
        if data.get("total_configured_sources")!=339 or data.get("mode")!="READ_ONLY_ISOLATED_NO_PRODUCTION_DATA":
            raise ValueError("Unexpected catalogue/mode in "+str(p))
        observed=at_utc(data["checked_at_utc"])
        age=(now-observed).total_seconds()/3600
        if not 0<=age<=max_age_hours:
            raise ValueError("Evidence too old/new: "+str(p)+" age="+str(round(age,2))+"h")
        times.append(observed)
        for source in data["sources"]:
            sid=source["source_id"]
            if sid not in EXPECTED:
                raise ValueError("Unexpected source "+sid)
            if source.get("state")!="listing_extracted" or source.get("list_complete") is not True:
                raise ValueError("Source not completely listed: "+sid)
            n=source.get("relevant_leads")
            if type(n) is not int or n<0 or n>5000:
                raise ValueError("Invalid lead count "+sid)
            if sid in roots and roots[sid]["relevant_leads"]!=n:
                raise ValueError("Listing changed between captures: "+sid)
            roots.setdefault(sid,source)
            offset=source.get("audited_offset")
            roles=source.get("audited")
            if type(offset) is not int or offset<0 or not isinstance(roles,list):
                raise ValueError("Bad offset/review slice "+sid)
            if offset+len(roles)>n:
                raise ValueError("Page overshoots title matches "+sid)
            for ix,role in enumerate(roles,offset):
                if ix in indexed[sid]:
                    raise ValueError("Overlapping role positions "+sid+":"+str(ix))
                if not role.get("title") or not role.get("url") or not isinstance(role.get("evaluation"),dict):
                    raise ValueError("Incomplete role evidence "+sid+":"+str(ix))
                indexed[sid][ix]=role
    if set(roots)!=EXPECTED:
        raise ValueError("Missing employer sources "+str(EXPECTED-set(roots)))
    out=[]
    for sid in sorted(EXPECTED):
        src=roots[sid]
        n=src["relevant_leads"]
        actual=set(indexed[sid])
        if actual!=set(range(n)):
            raise ValueError("Incomplete audit: "+sid+", missing "+str(sorted(set(range(n))-actual)[:20]))
        roles=[indexed[sid][i] for i in range(n)]
        keys={(r["url"],r["title"].casefold()) for r in roles}
        if len(keys)!=n:
            raise ValueError("Repeated posting URL and title in "+sid)
        out.append({"source_id":sid,"employer":src.get("employer"),
                    "state":"listing_extracted","list_complete":True,
                    "relevant_leads":n,"total_listed":src.get("total_listed"),
                    "audited_offset":0,"audited":roles,
                    "unreviewed_next":[],"skipped_after":0,"next_offset":None,
                    "merged_from_snapshot":True})
    total=sum(s["relevant_leads"] for s in out)
    if total!=EXPECTED_TOTAL:
        raise ValueError("Unexpected total audit size "+str(total))
    return {"checked_at_utc":now.isoformat(),"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
            "total_configured_sources":339,"sources_requested":sorted(EXPECTED),
            "evidence_method":"MERGED_VERIFIED_PREVIOUS_HTTP_SNAPSHOTS_NOT_NEW_HTTP",
            "oldest_source_observation_utc":min(times).isoformat(),
            "newest_source_observation_utc":max(times).isoformat(),
            "summary":{"sources":len(out),"roles":total,"all_positions_covered":True},
            "sources":out}

def tests():
    base=dt.datetime.now(dt.timezone.utc)
    # Inject fake sources for the complete 18-employer fixture using zero roles.
    fixture=[]
    for sid in EXPECTED:
        fixture.append({"source_id":sid,"state":"listing_extracted","list_complete":True,
                        "relevant_leads":0,"audited_offset":0,"audited":[]})
    d={"total_configured_sources":339,"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
       "checked_at_utc":base.isoformat(),"sources":fixture}
    try:reconstruct([("demo",d)],now=base)
    except ValueError as err:
        assert "Unexpected total audit size" in str(err),err
    else:raise AssertionError("Incorrect total accepted")
    d["sources"][0]["list_complete"]=False
    try:reconstruct([("demo",d)],now=base)
    except ValueError as err:assert "Source not completely listed" in str(err)
    else:raise AssertionError("Partial source was accepted")
    d["sources"][0]["list_complete"]=True
    try:reconstruct([("demo",d)],now=base+dt.timedelta(hours=24))
    except ValueError as err:assert "Evidence too old" in str(err)
    else:raise AssertionError("Stale content accepted")
    print("E2E18_RECONCILIATION_TESTS_PASSED",flush=True)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--out",default="e2e18_merged_quality.json")
    a.add_argument("--max-age-hours",type=float,default=12)
    a.add_argument("--self-test",action="store_true")
    a.add_argument("evidence",nargs="*")
    args=a.parse_args()
    tests()
    if args.self_test:return
    if not args.evidence:raise SystemExit("No source evidence files")
    data=[(p,json.loads(Path(p).read_text(encoding="utf-8"))) for p in args.evidence]
    merged=reconstruct(data,max_age_hours=args.max_age_hours)
    Path(args.out).write_text(json.dumps(merged,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("E2E18_RECONCILED",json.dumps(merged["summary"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
