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
  "dinotech": "https://dinotech.teamtailor.com/jobs/8306881-aml-analyst",
  "betsson": "https://job-boards.greenhouse.io/betsson/jobs/8050531",
  "nubank": "https://jobs.ashbyhq.com/nubank/0c9eb4e0-aa11-427a-97e4-160a98bb24d3",
  "dourolabs": "https://jobs.ashbyhq.com/dourolabs.xyz/20f3e7d8-6fd4-4d05-8eab-e0b69d04ead4"
}
EXTERNAL = {
  "external-sei": [
    "SEI",
    "https://seic.wd1.myworkdayjobs.com/SEI_Global_Services",
    [
      "workday",
      "seic.wd1.myworkdayjobs.com",
      "SEI_Global_Services"
    ],
    "https://seic.wd1.myworkdayjobs.com/SEI_Global_Services/job/LUX---Luxembourg/AML-Specialist_R0038767-1",
    [
      "sei investments",
      "seic.wd1"
    ]
  ],
  "external-lgt-bank": [
    "LGT Bank",
    "https://lgt.wd3.myworkdayjobs.com/lgtcurrentvacancies",
    [
      "workday",
      "lgt.wd3.myworkdayjobs.com",
      "lgtcurrentvacancies"
    ],
    "https://lgt.wd3.myworkdayjobs.com/en-US/lgtcurrentvacancies/job/Senior-Compliance-Officer--100---f-m-d-_JR7907-2",
    [
      "lgt bank",
      "lgt capital partners",
      "lgt.wd3"
    ]
  ],
  "external-flutter-international": [
    "Flutter International",
    "https://flutterbe.wd3.myworkdayjobs.com/FlutterInt_External",
    [
      "workday",
      "flutterbe.wd3.myworkdayjobs.com",
      "FlutterInt_External"
    ],
    "https://flutterbe.wd3.myworkdayjobs.com/en-US/FlutterInt_External/job/Financial-Crime-Analytics-and-Innovation-Manager_JR142539-1",
    [
      "flutter",
      "pokerstars",
      "betfair",
      "paddy power"
    ]
  ],
  "external-light-wonder": [
    "Light & Wonder",
    "https://lnw.wd5.myworkdayjobs.com/LightWonderExternalCareers",
    [
      "workday",
      "lnw.wd5.myworkdayjobs.com",
      "LightWonderExternalCareers"
    ],
    "https://lnw.wd5.myworkdayjobs.com/en-US/LightWonderExternalCareers/job/Compliance-Analyst_R322521",
    [
      "light wonder",
      "light and wonder",
      "scientific games"
    ]
  ],
  "external-stream": [
    "Stream / Wagestream",
    "https://wagestream-1683299953.teamtailor.com/jobs",
    [
      "teamtailor",
      "wagestream-1683299953.teamtailor.com",
      "/jobs"
    ],
    "https://wagestream-1683299953.teamtailor.com/jobs/7808074-risk-operations-analyst",
    [
      "wagestream"
    ]
  ],
  "external-exante": [
    "EXANTE",
    "https://job-boards.greenhouse.io/xntltd",
    [
      "greenhouse",
      "boards-api.greenhouse.io",
      "xntltd"
    ],
    "https://job-boards.greenhouse.io/xntltd/jobs/5044173101",
    [
      "exante",
      "xntltd",
      "xnt ltd"
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
