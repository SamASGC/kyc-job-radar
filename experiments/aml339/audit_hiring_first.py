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
 "vontobel":"https://www.vontobel.com/en-ch/about-vontobel/careers/open-positions/",
 "state-street":"https://statestreet.wd1.myworkdayjobs.com/en-US/Global/job/Registration-AML-KYC--Associate-1---German-Speaker_R-787109",
 "pwc-experienced":"https://pwc.wd3.myworkdayjobs.com/en-US/Global_Experienced_Careers/job/KYC-Associate_755776WD",
 "northern-trust":"https://ntrs.wd1.myworkdayjobs.com/en-US/northerntrust/job/AML-Analyst--Transfer-Agency_R155196-1",
 "guidehouse":"https://guidehouse.wd1.myworkdayjobs.com/en-US/External/job/GH-Office-Vilnius-Lithuania/Financial-Crime-Analyst--09-_41459",
 "loyens-loeff":"https://loyensloeff.wd3.myworkdayjobs.com/en-US/LL/job/KYC-Officer_JR001864",
 "robinhood":"https://job-boards.greenhouse.io/robinhood/jobs/7914059",
 "bjak":"https://jobs.ashbyhq.com/bjakcareer/41136dad-a373-4ad6-9c5c-df8c6b0173fe",
 "capco":"https://job-boards.greenhouse.io/capco/jobs/6282409",
}
EXTERNAL = {
 "external-arendt-group": ("Arendt", "arendt.wd3.myworkdayjobs.com", "Jobopportunities", "https://arendt.wd3.myworkdayjobs.com/Jobopportunities/job/AML-KYC-Analyst_JR000516", ["arendt"]),
 "external-saxo-bank": ("Saxo Bank", "saxobank.wd3.myworkdayjobs.com", "CareeratSaxoBank", "https://saxobank.wd3.myworkdayjobs.com/en-US/CareeratSaxoBank/job/Zurich/Senior-KYC-Analyst--Zurich_R-19422", ["saxo","saxobank"]),
 "external-fidelity-international": ("Fidelity International", "fil.wd3.myworkdayjobs.com", "001", "https://fil.wd3.myworkdayjobs.com/es/001/job/Associate---Client-Relationship-Management_J71300", ["fidelity","fidelity international"]),
 "external-mufg": ("MUFG", "mufgub.wd3.myworkdayjobs.com", "MUFG-Careers", "https://mufgub.wd3.myworkdayjobs.com/en-US/MUFG-Careers/job/Analyst--GCIB-Corporate-Coverage_10080139-WD", ["mufg","mitsubishi ufj"]),
 "external-mobilize-rci": ("Mobilize Financial Services / RCI", "alliancewd.wd3.myworkdayjobs.com", "renault-group-careers", "https://alliancewd.wd3.myworkdayjobs.com/en-GB/renault-group-careers/job/AML-Specialist_JOBREQ_50262980-1", ["mobilize","rci insurance","rci life","renault"]),
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
            name,host,token,reference,aliases=EXTERNAL[sid]
            row={"id":sid,"name":name,"careers_url":f"https://{host}/{token}","route":["workday",host,token],"aliases":aliases}
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
