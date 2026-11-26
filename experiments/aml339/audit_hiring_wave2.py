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
CATALOG = {}
EXTERNAL = {
 "external-blackstone": ("Blackstone", "blackstone.wd1.myworkdayjobs.com", "Blackstone_Careers", "https://blackstone.wd1.myworkdayjobs.com/en-US/Blackstone_Careers/job/Luxembourg/Anti-Money-Laundering--Associate-AVP_44158", ["blackstone"]),
 "external-invesco": ("Invesco", "invesco.wd1.myworkdayjobs.com", "IVZ", "https://invesco.wd1.myworkdayjobs.com/IVZ/job/EMEA-AML-Officer_R-14513", ["invesco"]),
 "external-lgt-capital-partners": ("LGT Capital Partners", "lgtcp.wd502.myworkdayjobs.com", "lgtcpcurrentvacancies", "https://lgtcp.wd502.myworkdayjobs.com/lgtcpcurrentvacancies/job/Student-Support---Compliance-40-80-_JR1939", ["lgtcapitalpartners","lgtcp","lgtbank"]),
 "external-pgim-prudential": ("PGIM / Prudential", "pru.wd5.myworkdayjobs.com", "Careers", "https://pru.wd5.myworkdayjobs.com/en-US/Careers/job/PGIM---Inter--Fund-Legal-and-Governance--all-genders---Based-in-Luxembourg_R-124581-1", ["pgim","prudential"]),
 "external-swiss-life-international": ("Swiss Life International", "swisslife.wd3.myworkdayjobs.com", "Swiss_Life_International_Division_Career_Site", "https://swisslife.wd3.myworkdayjobs.com/Swiss_Life_International_Division_Career_Site/job/Luxembourg---Cloche-dOr/XMLNAME--Senior--Compliance-Officer---French-speaking_R11185", ["swisslife"]),
 "external-ardian": ("Ardian", "ardian.wd103.myworkdayjobs.com", "ArdianCareers", "https://ardian.wd103.myworkdayjobs.com/ArdianCareers/job/Compliance-Analyst-Intern---January-2026---Luxembourg--M-F-_JR1002099", ["ardian"]),
 "external-cibc": ("CIBC", "cibc.wd3.myworkdayjobs.com", "search", "https://cibc.wd3.myworkdayjobs.com/search/job/K2-Dolce/Associate--Corporate-Banking--Luxembourg_2614501-1", ["cibc","canadianimperialbank"]),
 "external-gunvor": ("Gunvor", "gunvor.wd3.myworkdayjobs.com", "Gunvor_Careers", "https://gunvor.wd3.myworkdayjobs.com/en-US/Gunvor_Careers/job/KYC-Analyst_JR102589-1", ["gunvor"]),
 "external-trafigura": ("Trafigura", "trafigura.wd3.myworkdayjobs.com", "TrafiguraCareerSite", "https://trafigura.wd3.myworkdayjobs.com/TrafiguraCareerSite/job/Geneva-Switzerland/Senior-Compliance-Manager_R-018600", ["trafigura"]),
 "external-ares-management": ("Ares Management", "aresmgmt.wd1.myworkdayjobs.com", "External", "https://aresmgmt.wd1.myworkdayjobs.com/en-US/External/job/Analyst--Investor-Services_R8277", ["aresmanagement","aresmgmt"]),
 "external-mg": ("M&G", "mgpru.wd3.myworkdayjobs.com", "mandgprudential", "https://mgpru.wd3.myworkdayjobs.com/en-US/mandgprudential/job/Senior-Transaction-Monitoring---Investigations-Specialist-1LoD_R19234", ["mandgprudential","mgpru","mandg"]),
 "external-franklin-templeton": ("Franklin Templeton", "franklintempleton.wd5.myworkdayjobs.com", "Primary-External-1", "https://franklintempleton.wd5.myworkdayjobs.com/en-US/Primary-External-1/job/New-York-New-York-United-States-of-America/Client-Onboarding-Associate_868221", ["franklintempleton"]),
 "external-brookfield": ("Brookfield", "brookfield.wd5.myworkdayjobs.com", "brookfield", "https://brookfield.wd5.myworkdayjobs.com/en-US/brookfield/job/Sr-Analyst--Capital-Markets---Treasury_R2053131", ["brookfield"]),
 "external-wellington-management": ("Wellington Management", "wellington.wd5.myworkdayjobs.com", "efc", "https://wellington.wd5.myworkdayjobs.com/en-US/efc/job/Boston-MA-United-States/Director--Investor-Services-US-Wealth_R94264", ["wellingtonmanagement","wellingtonwd"]),
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
