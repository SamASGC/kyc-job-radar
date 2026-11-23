#!/usr/bin/env python3
"""LIVE source audits for two regulator-checked EMIs OUTSIDE pinned 339 catalog.

Trumia Limited (Malta, company C96757, Greenhouse ATS) and ZEN.COM
(UAB ZEN.COM, Lithuania, Traffit ATS) have independent immutable configs.
The pinned 339-source archive is not modified. No applications, no private
candidate data and no notification delivery occurs in this module.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

from amlradar.model import clean, plain
from quality_audit import candidate, evaluate, prioritize, role_geography
from live_e2e18_full import audit_one, OUTSIDE
from two_lane_alert_preview import listing_identity

SOURCES={
 "emi-trumia-mt":{
    "id":"emi-trumia-mt", "name":"Trumia Limited (Malta EMI)",
    "route":["greenhouse","boards-api.greenhouse.io","trumia"],
    "careers_url":"https://job-boards.eu.greenhouse.io/trumia",
    "regulatory_reference":"https://www.lb.lt/en/sfi-financial-market-participants/trumia-limited",
 },
 "emi-zen-lt":{
    "id":"emi-zen-lt", "name":"ZEN.COM (UAB ZEN.COM, Lithuania EMI)",
    "route":["traffit_public","zen.traffit.com","/public/an/list/"],
    "careers_url":"https://zen.traffit.com/career/",
    "regulatory_reference":"https://www.lb.lt/en/sfi-financial-market-participants/uab-zen-com",
 },
}
REGISTRY="regulated_emi_sidecar_v1"
PINNED_CATALOG_SIZE=339


def fetch(url,timeout=12,limit=750000):
    split=urllib.parse.urlsplit(url)
    if (split.scheme!="https" or split.hostname!="zen.traffit.com"
            or not (split.path.startswith("/public/an/") or
                    split.path.startswith("/public/form/"))):
        raise ValueError("Unexpected ATS host, protocol or request path")
    req=urllib.request.Request(url,headers={
        "Accept":"application/json, text/html;q=0.8",
        "User-Agent":"AML339-employer-public-jobs/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        if response.status!=200:
            raise ValueError("Official ATS not HTTP 200")
        raw=response.read(limit+1)
        if len(raw)>limit:raise ValueError("Official ATS response exceeds size budget")
        return raw.decode("utf-8",errors="replace")


def zen_active_rows():
    """Use fully paginated *official active-posts* API, never default ten results."""
    combined=[]
    count=None
    for offset in range(0,500,100):
        url=f"https://zen.traffit.com/public/an/list/?limit=100&offset={offset}"
        result=json.loads(fetch(url))
        if not isinstance(result,dict) or not isinstance(result.get("count"),int):
            raise ValueError("Malformed paginated Traffit count")
        if count is None:count=result["count"]
        if result["count"]!=count or count>500:raise ValueError("Inconsistent/oversized live listing")
        items=result.get("items")
        if not isinstance(items,list) or len(items)>100:
            raise ValueError("Malformed Traffit job results")
        combined+=items
        if len(combined)>=count:break
        if not items:raise ValueError("Incomplete Traffit pagination")
    if len(combined)!=count:raise ValueError("Incomplete Traffit page results")
    ids=[x.get("advertPublishId") for x in combined if isinstance(x,dict)]
    if len(ids)!=len(set(ids)) or any(not isinstance(x,int) for x in ids):
        raise ValueError("Duplicate or missing Traffit publication identity")
    return combined


def location_of(row):
    # Traffit locations are employer-maintained; do not turn "Remote" into
    # permission to work anywhere in Europe or a user's residence country.
    candidates=[]
    values=row.get("locations")
    if isinstance(values,list):
        for value in values:
            if isinstance(value,str):
                candidates.append(value)
            elif isinstance(value,dict):
                parts=[value.get(k) for k in ("city","locality","name","country")
                       if isinstance(value.get(k),str)]
                if parts:candidates.append(", ".join(parts))
    elif isinstance(values,str):
        candidates.append(values)
    geo=row.get("geolocation")
    if isinstance(geo,str):
        try:geo=json.loads(geo)
        except ValueError:pass
    if isinstance(geo,dict):
        parts=[geo.get(k) for k in ("locality","country")
               if isinstance(geo.get(k),str)]
        if parts:candidates.append(", ".join(parts))
    return clean("; ".join(dict.fromkeys(candidates)))[:400]


def zen_job(row):
    title=row.get("title") or row.get("name")
    desc="\n".join([
        "About the position",plain(row.get("description") or ""),
        "Key responsibilities",plain(row.get("responsibilities") or ""),
        "Requirements",plain(row.get("requirements") or ""),
    ])
    # Traffit's validStart is the start of a visible advert, not demonstrably
    # the FIRST original publication of the role. Never claim recent 72h.
    return {
        "title":clean(title),"url":row.get("url"),
        "apply_url":row.get("applicationForm"),"location":location_of(row),
        "description":desc,"date":None,
        "date_field":"Traffit.validStart (not original publication)",
        "date_semantics":"start of active advert, NOT confirmed first post",
    }


def audit_zen(minutes=4):
    deadline=time.monotonic()+minutes*60
    sid="emi-zen-lt"
    result={"source_id":sid,"employer":SOURCES[sid]["name"],
        "state":"listing_failed","list_complete":False,"relevant_leads":None,
        "total_listed":None,"audited_offset":0,"audited":[],
        "warnings":[],"errors":[],"skipped_details_outside_geo":0,
        "attempted_in_scope_details":0,"unverified_in_scope":0,
        "listing_role_keys":[],"listing_untrackable_count":0}
    try:
        raw=zen_active_rows()
        jobs=[zen_job(row) for row in raw]
        keys=[listing_identity(sid,job) for job in jobs]
        result["listing_role_keys"]=sorted(set(k for k in keys if k))
        result["listing_untrackable_count"]=sum(not bool(k) for k in keys)
        selected=[job for job in jobs if candidate(job)]
        selected.sort(key=prioritize)
        result.update(state="listing_extracted",list_complete=True,
                      total_listed=len(jobs),relevant_leads=len(selected))
        for job in selected:
            loc=role_geography(job["location"])
            error=""
            verified=False
            if loc in OUTSIDE:
                result["skipped_details_outside_geo"]+=1
                error="LOCATION_OUTSIDE_SCOPE: official country not in target"
            else:
                result["attempted_in_scope_details"]+=1
                try:
                    if time.monotonic()>deadline:
                        raise TimeoutError("Exceeded per-source budget")
                    url=job.get("url") or ""
                    apply=job.get("apply_url") or ""
                    # Read-only GET of the two employer-operated ATS pages.
                    detail=fetch(url)
                    form=fetch(apply)
                    if len(detail)<120 or len(form)<120:
                        raise ValueError("Job detail/application form incomplete")
                    if "/public/an/" not in url or "/public/form/" not in apply:
                        raise ValueError("Not an official Traffit job and apply form")
                    verified=True
                except Exception as exc:
                    error=type(exc).__name__+": "+str(exc)[:180]
                    result["unverified_in_scope"]+=1
            evaluation=evaluate(job,verified)
            result["audited"].append({
                "title":job["title"],"url":job["url"],
                "apply_url":job.get("apply_url") if verified else None,
                "location":job["location"],"hiring_organization":SOURCES[sid]["name"],
                "description_length":len(job["description"]),
                "verification_error":error,
                "detail_skipped_outside_geo":loc in OUTSIDE,
                "evaluation":evaluation,
            })
        if len(result["audited"])!=result["relevant_leads"]:
            raise ValueError("Incomplete Traffit job detail coverage")
    except Exception as exc:
        result.update(state="listing_failed",list_complete=False,
            errors=result["errors"]+[type(exc).__name__+": "+str(exc)[:200]])
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,choices=tuple(SOURCES))
    p.add_argument("--out",required=True)
    p.add_argument("--minutes",type=int,default=4)
    a=p.parse_args()
    if not 1<=a.minutes<=5:raise SystemExit("Budget out of range")
    if a.source=="emi-trumia-mt":
        result=audit_one(SOURCES[a.source],minutes=a.minutes)
    else:
        result=audit_zen(minutes=a.minutes)
    payload={
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "source_registry":REGISTRY,
        "original_catalog_sources":PINNED_CATALOG_SIZE,
        "total_configured_sources":PINNED_CATALOG_SIZE,
        "sources_requested":[a.source],"sources":[result],
    }
    Path(a.out).write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("NEW_EMI_FULL_AUDIT",json.dumps({
        "source":a.source,"state":result["state"],
        "total_listed":result["total_listed"],
        "title_matches":result["relevant_leads"],
        "detail_audited":len(result["audited"]),
        "unverified_in_scope":result["unverified_in_scope"],
        "errors":result["errors"],
    },ensure_ascii=False),flush=True)
    if result["state"]!="listing_extracted" or result["list_complete"] is not True:
        raise SystemExit("New EMI source incomplete: "+a.source)


if __name__=="__main__":main()
