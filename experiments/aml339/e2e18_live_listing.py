#!/usr/bin/env python3
"""Live HTTP title-match inventory; compares to independently audited source snapshots.

Public GET only; no job state, emails or application submission. Never interpret a
missing/failed listing as zero vacancies, or a changed timestamp as a new posting.
"""
from __future__ import annotations
import argparse,datetime as dt,json,time,hashlib
from pathlib import Path
from amlradar.net import Client
from amlradar.sources import Board
from amlradar.model import clean
from quality_audit import candidate
from two_lane_alert_preview import canonical_url

def ident(job):
    return canonical_url(job.get("url"))+"|"+clean(job.get("title")).casefold()

def live(source,minutes=3):
    client=Client(timeout=12,deadline=time.monotonic()+minutes*60)
    board=Board(source,client,max_minutes=minutes)
    entry={"source_id":source["id"],"state":"listing_failed","jobs":None,"title_matches":None,
           "complete":False,"records":[]}
    try:
        jobs=board.listing()
        matching=[job for job in jobs if candidate(job)]
        records=[{"identity":ident(j),"url":j.get("url"),"title":clean(j.get("title")),
                  "location":clean(j.get("location")),"date":j.get("date"),
                  "date_field":j.get("date_field")} for j in matching]
        duplicates=len(records)-len({x["identity"] for x in records})
        entry.update(state="listing_extracted",jobs=len(jobs),
                     title_matches=len(matching),complete=board.complete,
                     duplicates=duplicates,records=records,warnings=board.warnings[:6])
        if duplicates:entry["anomaly"]="Duplicate title+URL in current listing"
        print("E2E18_LIVE_SOURCE",json.dumps({
            "id":source["id"],"state":entry["state"],"jobs":entry["jobs"],
            "matches":entry["title_matches"],"complete":entry["complete"],
            "duplicate_identity":duplicates},ensure_ascii=False),flush=True)
    except Exception as exc:
        entry["error"]=type(exc).__name__+": "+str(exc)[:230]
        print("E2E18_LIVE_ERROR",json.dumps({"id":source["id"],"error":entry["error"]},flush=True))
    return entry

def compare(snapshot,live_manifest):
    known={s["source_id"]:s for s in snapshot["sources"]}
    current={s["source_id"]:s for s in live_manifest["sources"]}
    if len(known)!=18 or len(current)!=18 or set(known)!=set(current):
        raise ValueError("Source coverage mismatch")
    records=[]
    for name in sorted(known):
        old=known[name];new=current[name]
        if new["state"]!="listing_extracted" or not new["complete"]:
            records.append({"source_id":name,"status":"blocked_unavailable",
                            "reason":new.get("error"),"existing":old["relevant_leads"]})
            continue
        old_records={ident(r):r for r in old["audited"]}
        new_records={r["identity"]:r for r in new["records"]}
        added=sorted(set(new_records)-set(old_records))
        removed=sorted(set(old_records)-set(new_records))
        changed_dates=[]
        for key in set(old_records)&set(new_records):
            old_date=old_records[key]["evaluation"].get("original_posting_date")
            new_date=new_records[key]["date"]
            if old_date and new_date and old_date!=new_date:
                changed_dates.append({"title":new_records[key]["title"],"prior":old_date,"live":new_date,
                                      "field":new_records[key]["date_field"]})
        state="unchanged" if not added and not removed and not changed_dates else "changed_needs_detail_review"
        records.append({"source_id":name,"status":state,"previous_title_matches":len(old_records),
                        "live_title_matches":len(new_records),
                        "new_identity_count":len(added),"disappeared_identity_count":len(removed),
                        "changed_declared_date_count":len(changed_dates),
                        "added":[new_records[k] for k in added[:20]],"removed":[old_records[k].get("title") for k in removed[:20]],
                        "dates_changed":changed_dates[:15],"duplicates":new.get("duplicates",0)})
    return {"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "scope":"18 first-party portals; listing-only refresh, not full individual job verification",
            "summary":{"sources":18,
                "unchanged":sum(r["status"]=="unchanged" for r in records),
                "changed_needs_detail_review":sum(r["status"]=="changed_needs_detail_review" for r in records),
                "blocked_unavailable":sum(r["status"]=="blocked_unavailable" for r in records),
                "new_listing_identities":sum(r.get("new_identity_count",0) for r in records),
                "disappeared_listing_identities":sum(r.get("disappeared_identity_count",0) for r in records)},
            "sources":records}

def tests():
    a={"url":"https://example.com/jobs/123?utm_source=mail","title":"KYC Analyst"}
    b={"url":"https://example.com/jobs/123","title":"KYC Analyst"}
    assert ident(a)==ident(b)
    c={**a,"title":"AML Screening Analyst"}
    assert ident(a)!=ident(c)
    print("E2E18_LISTING_COMPARISON_TESTS_PASSED",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ids",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--minutes",type=int,default=3)
    a=p.parse_args()
    tests()
    if a.minutes<1 or a.minutes>4:raise SystemExit("minutes exceeded")
    rows=json.loads(Path("fuentes.json").read_text(encoding="utf-8"))["sources"]
    by={s["id"]:s for s in rows}
    ids=[s.strip() for s in a.ids.split(",") if s.strip()]
    if not 1<=len(ids)<=6 or len(ids)!=len(set(ids)) or any(s not in by for s in ids):
        raise SystemExit("Invalid isolated source subset")
    before=Path("fuentes.json").read_bytes()
    entries=[live(by[s],minutes=a.minutes) for s in ids]
    assert before==Path("fuentes.json").read_bytes()
    doc={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
         "mode":"READ_ONLY_PUBLIC_HTTP_GET","configured_sources":len(by),"sources":entries}
    Path(a.out).write_text(json.dumps(doc,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("E2E18_LIVE_TOTAL",json.dumps({
        "requested":len(entries),"successful":sum(x["state"]=="listing_extracted" and x["complete"] for x in entries),
        "failed_or_partial":sum(x["state"]!="listing_extracted" or not x["complete"] for x in entries)},
        ensure_ascii=False),flush=True)

if __name__=="__main__":main()
