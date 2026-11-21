#!/usr/bin/env python3
"""Audit potentially missed non-matching job titles against actual duties (read-only)."""
import argparse,datetime as dt,json,re,time
from collections import Counter
from pathlib import Path
from amlradar.sources import Board
from amlradar.net import Client
from amlradar.model import clean,plain
from quality_audit import candidate,evaluate,role_geography,prioritize,MAIN

HINT=re.compile(r"\b(?:operations?|payments?|merchant|customer|client|trust|safety|integrity|review|identit\w*|financial|finc\w*|legal|regulatory|account|fraud prevention|disputes?|verification|risk control|invest\w*)\b",re.I)
NON_FINANCIAL=re.compile(r"\b(?:marketing|copywriter|recruiting|sourcing|people partner|office manager|facilities|graphic|engineer|software|product designer|business development|sales|counsel|HR\b)\b",re.I)
CORE=MAIN-{"Financial crime investigations"}

def audit(source,max_details=8,timeout=10,minutes=3):
    board=Board(source,Client(timeout=timeout,deadline=time.monotonic()+minutes*60),max_minutes=minutes)
    result={"source_id":source["id"],"name":source["name"],"state":"listing_failed",
            "listed":None,"excluded_by_existing_title_filter":None,
            "eligible_for_detail_review":None,"examined":0,"unexamined":0,
            "potential_false_negatives":[],"negative_controls":[],"errors":[]}
    try:
        jobs=board.listing()
        raw=[j for j in jobs if not candidate(j)]
        # Only sample high-plausibility title misses; do not pretend all others were audited.
        ranked=[j for j in raw if HINT.search(clean(j.get("title"))) and not NON_FINANCIAL.search(clean(j.get("title")))]
        ranked.sort(key=lambda j:(0 if role_geography(j.get("location")) in ("target","remote_location_review") else 1,
                                  prioritize(j)))
        scope=lambda j: role_geography(j.get("location")) not in (
            "outside_scope","excluded_barcelona","swiss_future")
        scope_counts=dict(Counter(role_geography(j.get("location")) for j in ranked))
        still_plausible=[j for j in ranked[max_details:] if scope(j)]
        result.update(state="listing_extracted",listed=len(jobs),
                      excluded_by_existing_title_filter=len(raw),
                      eligible_for_detail_review=len(ranked),
                      plausible_geography_counts=scope_counts,
                      unexamined=max(0,len(ranked)-max_details),
                      unexamined_potentially_in_scope=len(still_plausible),
                      unexamined_target_examples=[{
                          "title":clean(j.get("title")),"location":clean(j.get("location")),
                          "url":j.get("url")} for j in still_plausible[:20]])
        for job in ranked[:max_details]:
            error=None;verified=False
            try:
                board.hydrate(job)
                if "_page" not in job:board.read_post(job)
                board.verify(job);verified=True
            except Exception as e:
                error=type(e).__name__+": "+str(e)[:190]
            analysis=evaluate(job,verified)
            duties=set(analysis["explicit_duties"])
            meaningful=duties & (CORE|{"Financial crime investigations"})
            record={"title":clean(job.get("title")),"url":job.get("url"),
                "location":clean(job.get("location")),"date":job.get("date"),
                "skills":analysis["functions"],"duties":analysis["explicit_duties"],
                "application_verified":verified,"class":analysis["class"],
                "geography":analysis["geography"],"barriers":analysis["barriers"],
                "requirement_evidence":analysis["requirement_evidence"],
                "duty_evidence":analysis.get("duty_evidence",[]),
                "error":error}
            if meaningful and not analysis["barriers"] and analysis["geography"] in ("target","remote_location_review","mixed_location_review"):
                result["potential_false_negatives"].append(record)
            else:
                result["negative_controls"].append(record)
            result["examined"]+=1
        print("FALSE_NEGATIVE_SOURCE",json.dumps({"source":result["source_id"],
            "listed":result["listed"],"nonmatches":len(raw),
            "reviewable":len(ranked),"examined":result["examined"],
            "potential_misses":len(result["potential_false_negatives"]),
            "remaining_not_checked":result["unexamined"],"remaining_possible_scope":result["unexamined_potentially_in_scope"],"geography_counts":result["plausible_geography_counts"]},ensure_ascii=False),flush=True)
    except Exception as e:
        result["errors"].append(type(e).__name__+": "+str(e)[:190])
        print("FALSE_NEGATIVE_ERROR",json.dumps(result["errors"],ensure_ascii=False),flush=True)
    return result

def run_tests():
    assert not HINT.search("Senior Software Engineer")
    assert HINT.search("Merchant Operations Associate")
    assert NON_FINANCIAL.search("Product Designer")
    assert not NON_FINANCIAL.search("Client Account Specialist")
    print("FALSE_NEGATIVE_TESTS_PASSED",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ids",required=True)
    p.add_argument("--max-details",type=int,default=6)
    p.add_argument("--minutes",type=int,default=3)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    run_tests()
    if not 1<=args.max_details<=8 or not 1<=args.minutes<=4:raise SystemExit("Invalid bounds")
    sources={x["id"]:x for x in json.loads(Path("fuentes.json").read_text(encoding="utf-8"))["sources"]}
    ids=[s.strip() for s in args.ids.split(",")]
    assert len(ids)<=5 and len(ids)==len(set(ids)) and all(x in sources for x in ids)
    before=Path("fuentes.json").read_bytes()
    entries=[audit(sources[x],max_details=args.max_details,minutes=args.minutes) for x in ids]
    assert before==Path("fuentes.json").read_bytes()
    summary={"sources":len(entries),
             "listings_extracted":sum(x["state"]=="listing_extracted" for x in entries),
             "title_filtered_out":sum(x["excluded_by_existing_title_filter"] or 0 for x in entries),
             "plausible_titles":sum(x["eligible_for_detail_review"] or 0 for x in entries),
             "details_examined":sum(x["examined"] for x in entries),
             "potential_false_negatives":sum(len(x["potential_false_negatives"]) for x in entries),
             "unexamined_plausible_titles":sum(x["unexamined"] for x in entries),
             "unexamined_possible_scope":sum(x.get("unexamined_potentially_in_scope") or 0 for x in entries)}
    Path(args.out).write_text(json.dumps({
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope":"Targeted, non-exhaustive false negative check of nonmatched job titles",
        "summary":summary,"sources":entries},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("FALSE_NEGATIVE_TOTAL",json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
