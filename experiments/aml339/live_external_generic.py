#!/usr/bin/env python3
"""Audit a registered employer using independent official listing anchors.
Never accepts a guessed ATS or a zero-job board without explicit verification.
"""
import argparse,datetime as dt,json,re
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from live_external50_wave02 import Anchors,read_page,candidate
from live_e2e18_full import audit_one
import live_e2e18_full as audit
from amlradar.sources import Board

def audit_workday(row):
    """Use the same bounded, fail-closed Workday parser as original catalog.
    Only exact, independently reviewed Workday tenant/site routes are admitted.
    No fallback requests, guessed pages or zero-listing acceptance.
    """
    sid=row["id"]; url=row["careers_url"]; route=row["route"]
    u=urlsplit(url)
    if (len(route)!=3 or route[0]!="workday" or u.scheme!="https"
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.wd[0-9]+\.myworkdayjobs\.com",route[1])
        or u.hostname!=route[1] or u.netloc!=route[1] or u.query or u.fragment
        or not re.fullmatch(r"[A-Za-z0-9_-]+",route[2])
        or u.path.rstrip("/")!="/"+route[2]):
        raise ValueError("Unapproved Workday tenant/site route")
    result=audit_one({"id":sid,"name":row["name"],"careers_url":url,"route":route},minutes=4)
    n=result.get("total_listed")
    ok=(result.get("state")=="listing_extracted" and result.get("list_complete") is True
        and type(n) is int and n>0
        and result.get("relevant_leads")==len(result.get("audited",[]))
        and result.get("unverified_in_scope")==0
        and result.get("listing_untrackable_count")==0
        and len(result.get("listing_role_keys",[]))==n)
    if not ok:result.update(state="listing_failed",list_complete=False)
    return result,ok

def audit_greenhouse(row):
    """Cross-check the approved public board against its exact API listing."""
    url=row["careers_url"]; route=row["route"]; u=urlsplit(url)
    hosts={"boards-api.greenhouse.io":"job-boards.greenhouse.io",
           "boards-api.eu.greenhouse.io":"job-boards.eu.greenhouse.io"}
    if (len(route)!=3 or route[0]!="greenhouse" or route[1] not in hosts
        or not re.fullmatch(r"[a-z0-9_-]+",route[2])
        or u.scheme!="https" or u.netloc!=hosts[route[1]] or u.query or u.fragment
        or u.path.rstrip("/")!="/"+route[2]):
        raise ValueError("Unapproved Greenhouse board route")
    rx=re.compile(r"/"+re.escape(route[2])+r"/jobs/([0-9]+)/?")
    allowed={u.hostname,"job-boards.greenhouse.io","job-boards.eu.greenhouse.io",
             "boards.greenhouse.io","boards.eu.greenhouse.io"}
    def key(href):
        link=urlsplit(urljoin(url,href)); m=rx.fullmatch(link.path)
        return m[1] if link.scheme=="https" and link.netloc in allowed and m else None
    page=Anchors(); page.feed(read_page(url))
    expected={key(h):title for h,title in page.links.items() if key(h) and title}
    if not expected:raise ValueError("No independent positive job-link proof")
    original=Board.listing; previous=audit.candidate
    def checked(board):
        jobs=original(board)
        by={key(str(j.get("url",""))):j for j in jobs}
        if None in by or len(by)!=len(jobs) or set(expected)!=set(by):
            raise ValueError("Public ATS and visible board job identities disagree")
        for k,title in expected.items():
            if candidate({"title":title}) and not candidate(by[k]):by[k]["title"]=title
        return jobs
    Board.listing=checked; audit.candidate=candidate
    try:result=audit_one({"id":row["id"],"name":row["name"],"careers_url":url,"route":route},minutes=4)
    finally:Board.listing=original; audit.candidate=previous
    n=result.get("total_listed")
    ok=(result.get("state")=="listing_extracted" and result.get("list_complete") is True
        and n==len(expected) and result.get("relevant_leads")==len(result.get("audited",[]))
        and result.get("unverified_in_scope")==0 and result.get("listing_untrackable_count")==0
        and len(result.get("listing_role_keys",[]))==n)
    if not ok:result.update(state="listing_failed",list_complete=False)
    return result,ok

def audit_smart_external(row):
    """External SmartRecruiters: resolve the exact previously audited Wise
    route schema from the immutable, repaired original catalog. Never guess a
    provider route or accept an incomplete or duplicate listing."""
    url=row["careers_url"]; route=row["route"]; u=urlsplit(url)
    if (len(route)!=3 or route[:2]!=["smart_external","jobs.smartrecruiters.com"]
        or not re.fullmatch(r"[A-Za-z0-9_-]+",route[2])
        or u.scheme!="https" or u.netloc!="jobs.smartrecruiters.com"
        or u.query or u.fragment or u.path.rstrip("/")!="/"+route[2]):
        raise ValueError("Unapproved SmartRecruiters company route")
    original=json.loads(Path("fuentes.json").read_text())["sources"]
    if len(original)!=339 or len({x["id"] for x in original})!=339:
        raise ValueError("Unexpected original catalog")
    templates={tuple(r) for x in original for r in [x.get("route",[])]
               if len(r)==3 and "smart" in str(r[0]).lower()
               and sum(str(v).lower()=="wise" for v in r[1:])==1}
    if len(templates)!=1:
        raise ValueError("No unique known SmartRecruiters route")
    parsed=[route[2] if str(v).lower()=="wise" else v for v in next(iter(templates))]
    if any([str(v).lower() for v in x.get("route",[])]==[str(v).lower() for v in parsed] for x in original):
        raise ValueError("Original SmartRecruiters company already catalogued")
    previous=audit.candidate
    audit.candidate=candidate
    try:
        result=audit_one({"id":row["id"],"name":row["name"],"careers_url":url,"route":parsed},minutes=4)
    finally:
        audit.candidate=previous
    n=result.get("total_listed")
    ok=(result.get("state")=="listing_extracted" and result.get("list_complete") is True
        and type(n) is int and n>0
        and result.get("relevant_leads")==len(result.get("audited",[]))
        and result.get("unverified_in_scope")==0
        and result.get("listing_untrackable_count")==0
        and len(result.get("listing_role_keys",[]))==n)
    if not ok:result.update(state="listing_failed",list_complete=False)
    return result,ok

def audit_config(row):
    if row.get("route", [None])[0]=="smart_external":
        return audit_smart_external(row)
    if row.get("route", [None])[0]=="greenhouse":
        return audit_greenhouse(row)
    if row.get("route", [None])[0]=="workday":
        return audit_workday(row)
    sid=row["id"]; name=row["name"]; url=row["careers_url"]; route=row["route"]
    host=urlsplit(url).hostname
    if urlsplit(url).scheme!="https" or route[0] not in ("site_jobs","teamtailor") or route[1]!=host:
        raise ValueError("Only approved employer-owned or employer-linked ATS routes")
    pattern=re.compile(row["job_pattern"])
    page=Anchors();page.feed(read_page(url))
    expected={urlsplit(urljoin(url,h)).path.rstrip("/"):title for h,title in page.links.items()
              if urlsplit(urljoin(url,h)).hostname==host and pattern.fullmatch(urlsplit(urljoin(url,h)).path) and title}
    if not expected:raise ValueError("No independent positive job-link evidence; empty/inline/JS board needs dedicated adapter")
    original=Board.listing
    def checked(board):
        jobs=original(board)
        by={urlsplit(str(j.get("url",""))).path.rstrip("/"):j for j in jobs}
        if not set(expected).issubset(by):raise ValueError("Official job IDs missing")
        for key,title in expected.items():
            # A title-based selector must never silently drop a known relevant title.
            if candidate({"title":title}) and not candidate(by[key]):by[key]["title"]=title
            elif not str(by[key].get("title","")).strip():by[key]["title"]=title
        return jobs
    previous=audit.candidate
    Board.listing=checked; audit.candidate=candidate
    try:result=audit_one({"id":sid,"name":name,"careers_url":url,"route":route},minutes=4)
    finally:Board.listing=original; audit.candidate=previous
    ok=(result.get("state")=="listing_extracted" and result.get("list_complete") is True
        and isinstance(result.get("total_listed"),int) and result["total_listed"]>=len(expected)
        and result.get("relevant_leads")==len(result.get("audited",[]))
        and result.get("unverified_in_scope")==0 and result.get("listing_untrackable_count")==0)
    if not ok:result.update(state="listing_failed",list_complete=False)
    return result,ok

def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--out",required=True)
    p.add_argument("--production",action="store_true");p.add_argument("--candidates",type=Path)
    a=p.parse_args()
    if a.production:
        from external_live_registry import load_registry
        rows=load_registry()
        rows=[x for x in rows if x["driver"]=="generic"]
    else:
        if a.candidates is None:raise ValueError("Explicit reviewed candidate file required")
        rows=json.loads(a.candidates.read_text())["candidates"]
    row=next(x for x in rows if x["id"]==a.source)
    result,ok=audit_config(row)
    envelope={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA","source_registry":"external_regulated50_wave02_live_v1" if a.production else "external_batch_canary_v1","original_catalog_sources":339,"total_configured_sources":339,"sources_requested":[a.source],"verified":ok,"sources":[result]}
    Path(a.out).write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+"\n")
    print("GENERIC_EXTERNAL_AUDIT",json.dumps({"id":a.source,"verified":ok,"listed":result.get("total_listed"),"errors":result.get("errors")}),flush=True)
    if not ok:raise SystemExit("Incomplete employer audit")
if __name__=="__main__":main()
