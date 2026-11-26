#!/usr/bin/env python3
"""Hiring-first bounded live audits. Read-only; no enrollment or application."""
import argparse, json, re
from pathlib import Path
from urllib.parse import urlsplit
from live_e2e18_full import audit_one
import live_e2e18_full as audit
from live_external50_wave02 import candidate

# Actual employer postings establish hiring relevance, not present vacancies,
# regulatory status, suitability for the user or technical completeness.
CATALOG = {
  "leovegasgroup": "https://jobs.ashbyhq.com/leovegasgroup/2bcdf602-14b2-49a4-b104-6fd813cd2ec6",
  "playson": "https://jobs.ashbyhq.com/playson/6e7d87fe-b564-4424-9c78-4cffcf7d7dc8/",
  "b2spin": "https://jobs.ashbyhq.com/b2spin/bb58be47-f4b7-487f-923c-a7165881b65e",
  "finary": "https://jobs.ashbyhq.com/finary/5fae2eb4-a35d-4f36-b547-f26d28715b48"
}
EXTERNAL = {
  "external-juniper-square": [
    "Juniper Square",
    "https://jobs.ashbyhq.com/junipersquare",
    [
      "ashby",
      "api.ashbyhq.com",
      "junipersquare"
    ],
    "https://jobs.ashbyhq.com/junipersquare/a1630470-78c1-40d7-b1d0-523d447d5ccc",
    [
      "juniper square",
      "junipersquare"
    ]
  ],
  "external-rothschild-co": [
    "Rothschild & Co",
    "https://rothschildandco.wd3.myworkdayjobs.com/Rothschildandco_Lateral",
    [
      "workday",
      "rothschildandco.wd3.myworkdayjobs.com",
      "Rothschildandco_Lateral"
    ],
    "https://rothschildandco.wd3.myworkdayjobs.com/en-US/Rothschildandco_Lateral/job/Junior-AML---Compliance-Specialist_JR016277",
    [
      "rothschildandco",
      "rothschild & co",
      "rothschild co"
    ]
  ],
  "external-infinit": [
    "INFINIT",
    "https://jobs.lever.co/infinit",
    [
      "lever",
      "api.lever.co",
      "infinit"
    ],
    "https://jobs.lever.co/infinit/dc1eff3c-fe76-44fa-9cb1-e10b55a9eeac",
    [
      "infinit"
    ]
  ],
  "external-hostinger": [
    "Hostinger",
    "https://jobs.ashbyhq.com/hostinger",
    [
      "ashby",
      "api.ashbyhq.com",
      "hostinger"
    ],
    "https://jobs.ashbyhq.com/hostinger/49089a19-95d0-425c-be42-25d72c47c2b2",
    [
      "hostinger"
    ]
  ],
  "external-barclays": [
    "Barclays",
    "https://barclays.wd3.myworkdayjobs.com/External_Career_Site_Barclays",
    [
      "workday",
      "barclays.wd3.myworkdayjobs.com",
      "External_Career_Site_Barclays"
    ],
    "https://barclays.wd3.myworkdayjobs.com/en-US/External_Career_Site_Barclays/job/Governance---Control-Senior-Manager---VP_JR-0000120623",
    [
      "barclays"
    ]
  ]
}
IDS = tuple(CATALOG)+tuple(EXTERNAL)
def normalized(s):
    return re.sub(r"[^a-z0-9]","",str(s).lower())
def same_group(row, others):
    aliases=[normalized(a) for a in row.get("aliases",[])]
    for old in others:
        vals=[normalized(old.get(k,"")) for k in ("id","name","careers_url")]
        vals.extend(normalized(a) for a in old.get("aliases",[]))
        if old.get("route")==row.get("route") or any(a and a in v for a in aliases for v in vals):
            return old.get("id")
    return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,choices=IDS)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--live",type=Path,required=True)
    p.add_argument("--registry",type=Path,required=True)
    a=p.parse_args(); sid=a.source
    result={"id":sid,"verified":False}
    try:
        original=json.loads(Path("fuentes.json").read_text())["sources"]
        assert len(original)==len({x["id"] for x in original})==339
        live=json.loads(a.live.read_text())["sources"]
        registry=json.loads(a.registry.read_text())["sources"]
        assert len(live)==len({x["id"] for x in live})
        active={x["id"] for x in live}|{x["id"] for x in registry}
        if sid in active:
            raise ValueError("Already monitored; no duplicate audit")
        if sid in CATALOG:
            row=dict(next(x for x in original if x["id"]==sid))
            reference=CATALOG[sid]
            if any(x.get("route")==row.get("route") and x["id"] in active for x in original+registry):
                raise ValueError("ATS route already monitored")
            result["origin"]="original_catalog"
        else:
            name,careers_url,route,reference,aliases=EXTERNAL[sid]
            row={"id":sid,"name":name,"careers_url":careers_url,"route":route,"aliases":aliases}
            if route[0]=="teamtailor":row["job_pattern"]=r"^/jobs/[0-9]+-[^/]+/?$"
            match=same_group(row,original+registry+live)
            if match:raise ValueError("Original or monitored group match: "+str(match))
            result["origin"]="new_external_review"
        if urlsplit(reference).scheme!="https" or "workable" in str(row.get("route",[])).lower():
            raise ValueError("Unsupported or restricted route")
        result.update(config=row,hiring_reference=reference)
        old=audit.candidate
        audit.candidate=candidate
        try:report=audit_one(row,minutes=4)
        finally:audit.candidate=old
        n=report.get("total_listed")
        ok=(report.get("state")=="listing_extracted" and report.get("list_complete") is True
            and type(n) is int and n>0
            and report.get("relevant_leads")==len(report.get("audited",[]))
            and report.get("unverified_in_scope")==0 and report.get("listing_untrackable_count")==0)
        if not ok:report.update(state="listing_failed",list_complete=False)
        result.update(verified=ok,audit=report,status="TECHNICAL_PASS_REVIEW_REQUIRED" if ok else "INCOMPLETE")
    except Exception as exc:
        result.update(status="HELD",error=type(exc).__name__+": "+str(exc)[:250])
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    report=result.get("audit",{})
    print("HIRING_FIRST_AUDIT",json.dumps({"id":sid,"verified":result["verified"],"status":result.get("status"),"listed":report.get("total_listed"),"relevant":report.get("relevant_leads"),"unverified":report.get("unverified_in_scope"),"error":result.get("error"),"errors":report.get("errors"),"plausible_geo":[{"title":j.get("title"),"location":j.get("location"),"url":j.get("url"),"error":j.get("verification_error")} for j in report.get("audited",[]) if j.get("evaluation",{}).get("geography") in ("target","swiss_future","remote_location_review","mixed_location_review","unknown")]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
