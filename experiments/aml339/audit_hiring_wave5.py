#!/usr/bin/env python3
"""Hiring-first bounded live audits. Read-only; no enrollment or application."""
import argparse, json, re
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from live_e2e18_full import audit_one
import live_e2e18_full as audit
from live_external50_wave02 import candidate,Anchors,read_page

# Actual employer postings establish hiring relevance, not present vacancies,
# regulatory status, suitability for the user or technical completeness.
CATALOG = {
  "fdj-united": "https://groupefdj.wd103.myworkdayjobs.com/fdj-united/job/malta/aml---rg-specialist---market-portfolio_jr103224-1"
}
EXTERNAL = {
  "external-ssctech": [
    "SS&C Technologies",
    "https://ssctech.wd1.myworkdayjobs.com/SSCTechnologies",
    [
      "workday",
      "ssctech.wd1.myworkdayjobs.com",
      "SSCTechnologies"
    ],
    "https://ssctech.wd1.myworkdayjobs.com/en-US/SSCTechnologies/job/Manager--Investor-Services_R41596",
    [
      "ssctech",
      "ss&c technologies",
      "ss and c technologies"
    ]
  ],
  "external-us-bank": [
    "U.S. Bank / Elavon",
    "https://usbank.wd1.myworkdayjobs.com/US_Bank_Careers",
    [
      "workday",
      "usbank.wd1.myworkdayjobs.com",
      "US_Bank_Careers"
    ],
    "https://usbank.wd1.myworkdayjobs.com/en-US/US_Bank_Careers/job/AML-Manager_2026-0014737",
    [
      "usbank",
      "u.s. bank",
      "elavon"
    ]
  ],
  "external-vistra": [
    "Vistra",
    "https://careers.vistra.com/",
    [
      "diagnostic",
      "careers.vistra.com",
      "/job/"
    ],
    "https://careers.vistra.com/job/AML-KYC-Officer/18844-en_US/",
    [
      "vistra",
      "tricor"
    ]
  ],
  "external-deloitte-lu": [
    "Deloitte Luxembourg",
    "https://jobs.deloitte.lu/go/View-all-Jobs/9826901/",
    [
      "diagnostic",
      "jobs.deloitte.lu",
      "/job/"
    ],
    "https://jobs.deloitte.lu/job/Luxembourg-AMLKYC-Officer/14264-en_GB/",
    [
      "deloitte"
    ]
  ],
  "external-kpmg-lu": [
    "KPMG Luxembourg",
    "https://careers.kpmg.lu/go/All-Jobs/9266401/",
    [
      "diagnostic",
      "careers.kpmg.lu",
      "/job/"
    ],
    "https://careers.kpmg.lu/job/AML-%26-Compliance-Manager-%28mfd%29-Audit/2795-en_GB/",
    [
      "kpmg"
    ]
  ],
  "external-ey": [
    "EY",
    "https://careers.ey.com/ey/search/",
    [
      "diagnostic",
      "careers.ey.com",
      "/ey/job/"
    ],
    "https://careers.ey.com/ey/job/Luxembourg-AML-Analyst-Senior-L-1855/1287694701/",
    [
      "ernst young",
      "ernst & young",
      "careers.ey.com"
    ]
  ],
  "external-ao-shearman": [
    "A&O Shearman",
    "https://careers.aoshearman.com/en/location/luxembourg-jobs/3392/2960313/2",
    [
      "diagnostic",
      "careers.aoshearman.com",
      "/en/job/"
    ],
    "https://careers.aoshearman.com/en/job/luxembourg/aml-kyc-analyst/3392/45418610944",
    [
      "aoshearman",
      "allen overy",
      "shearman sterling"
    ]
  ],
  "external-bnp-paribas": [
    "BNP Paribas",
    "https://group.bnpparibas/en/careers/all-job-offers/compliance/spain",
    [
      "diagnostic",
      "group.bnpparibas",
      "/en/careers/job-offer/"
    ],
    "https://group.bnpparibas/en/careers/job-offer/business-group-coordinator-kyc-1",
    [
      "bnpparibas",
      "bnp paribas"
    ]
  ],
  "external-citco": [
    "Citco",
    "https://fa-euxc-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1",
    [
      "diagnostic",
      "fa-euxc-saasfaprod1.fa.ocs.oraclecloud.com",
      "/hcmUI/CandidateExperience/en/sites/CX_1/job/"
    ],
    "https://fa-euxc-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/21251",
    [
      "citco"
    ]
  ],
  "external-danske-bank": [
    "Danske Bank",
    "https://ejqi.fa.ocs.oraclecloud.eu/hcmUI/CandidateExperience/en/sites/CX_1001",
    [
      "diagnostic",
      "ejqi.fa.ocs.oraclecloud.eu",
      "/hcmUI/CandidateExperience/en/sites/CX_1001/job/"
    ],
    "https://ejqi.fa.ocs.oraclecloud.eu/hcmUI/CandidateExperience/en/sites/CX_1001/job/25149",
    [
      "danskebank",
      "danske bank"
    ]
  ],
  "external-caml": [
    "CAML UAB",
    "https://www.caml.lt/career",
    [
      "diagnostic",
      "www.caml.lt",
      "/career"
    ],
    "https://www.caml.lt/career",
    [
      "caml uab",
      "caml.lt"
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
        if row["route"][0]=="diagnostic":
            # Static/JS paginated portals require independent all-page coverage proof.
            # Record only observed anchors; never label a partial listing verified.
            page=Anchors();page.feed(read_page(row["careers_url"]))
            links={urljoin(row["careers_url"],h) for h,t in page.links.items() if t and urlsplit(urljoin(row["careers_url"],h)).hostname==row["route"][1] and urlsplit(urljoin(row["careers_url"],h)).path.startswith(row["route"][2])}
            result.update(status="DIAGNOSTIC_NEEDS_COMPLETE_LISTING",observed_job_links=len(links),observed_urls=sorted(links)[:15])
            a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
            print("HIRING_FIRST_AUDIT",json.dumps({k:v for k,v in result.items() if k!="config"},ensure_ascii=False),flush=True)
            return
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
