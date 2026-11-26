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
CATALOG = {}
EXTERNAL = {
  "external-tipico": [
    "Tipico",
    "https://jobs.smartrecruiters.com/Tipico",
    [
      "smart_review",
      "Tipico",
      ""
    ],
    "https://jobs.smartrecruiters.com/Tipico/744000156536754-aml-analyst-m-f-x-",
    [
      "tipico"
    ]
  ],
  "external-bet365": [
    "bet365",
    "https://jobs.smartrecruiters.com/Bet3651",
    [
      "smart_review",
      "Bet3651",
      ""
    ],
    "https://jobs.smartrecruiters.com/Bet3651/744000158279578-senior-anti-financial-crime-manager",
    [
      "bet365"
    ]
  ],
  "external-bank-of-china": [
    "Bank of China",
    "https://jobs.smartrecruiters.com/BankOfChinaLuxembourg",
    [
      "smart_review",
      "BankOfChinaLuxembourg",
      ""
    ],
    "https://jobs.smartrecruiters.com/BankOfChinaLuxembourg/744000162290179-compliance-officer-intra-group-compliance-management-division-",
    [
      "bank of china",
      "bankofchina"
    ]
  ],
  "external-playtech": [
    "Playtech",
    "https://jobs.smartrecruiters.com/Playtech",
    [
      "smart_review",
      "Playtech",
      ""
    ],
    "https://jobs.smartrecruiters.com/Playtech/744000159097219-compliance-manager-",
    [
      "playtech"
    ]
  ],
  "external-talan": [
    "Talan",
    "https://jobs.smartrecruiters.com/Talan",
    [
      "smart_review",
      "Talan",
      ""
    ],
    "https://jobs.smartrecruiters.com/Talan/744000163618149-business-analyst-l-luxembourg",
    [
      "talan"
    ]
  ],
  "external-met-group": [
    "MET Group",
    "https://jobs.smartrecruiters.com/METGroup",
    [
      "smart_review",
      "METGroup",
      ""
    ],
    "https://jobs.smartrecruiters.com/METGroup/744000161240051-junior-credit-risk-analyst",
    [
      "met group",
      "metgroup"
    ]
  ],
  "external-accenture": [
    "Accenture",
    "https://accenture.wd103.myworkdayjobs.com/AccentureCareers",
    [
      "workday",
      "accenture.wd103.myworkdayjobs.com",
      "AccentureCareers"
    ],
    "https://accenture.wd103.myworkdayjobs.com/AccentureCareers/job/Brussels/Finance--Risk-and-Compliance-Compliance-Senior-Manager_R00354232",
    [
      "accenture"
    ]
  ],
  "external-morgan-stanley": [
    "Morgan Stanley",
    "https://ms.wd5.myworkdayjobs.com/External",
    [
      "workday",
      "ms.wd5.myworkdayjobs.com",
      "External"
    ],
    "https://ms.wd5.myworkdayjobs.com/External/job/Budapest-Hungary/AML---KYC-Risk-Specialist_JR041323",
    [
      "morgan stanley",
      "morganstanley"
    ]
  ],
  "external-vanguard": [
    "Vanguard",
    "https://vanguard.wd5.myworkdayjobs.com/vanguard_external",
    [
      "workday",
      "vanguard.wd5.myworkdayjobs.com",
      "vanguard_external"
    ],
    "https://vanguard.wd5.myworkdayjobs.com/vanguard_external/job/Dublin-Ireland/Financial-Crimes-Compliance-Analyst_177619-2",
    [
      "vanguard"
    ]
  ],
  "external-fnz": [
    "FNZ",
    "https://fnz.wd3.myworkdayjobs.com/fnz_careers",
    [
      "workday",
      "fnz.wd3.myworkdayjobs.com",
      "fnz_careers"
    ],
    "https://fnz.wd3.myworkdayjobs.com/en-US/fnz_careers/job/Kuala-Lumpur---Malaysia/AML-Analyst_REQ-16610",
    [
      "fnz"
    ]
  ],
  "external-cmc-markets": [
    "CMC Markets",
    "https://cmcmarkets.wd3.myworkdayjobs.com/CMC_Markets_Careers",
    [
      "workday",
      "cmcmarkets.wd3.myworkdayjobs.com",
      "CMC_Markets_Careers"
    ],
    "https://cmcmarkets.wd3.myworkdayjobs.com/en-US/cmc_markets_careers/job/Dubai/KYC---AML-Analyst_CMC5815",
    [
      "cmc markets",
      "cmcmarkets"
    ]
  ],
  "external-jll": [
    "JLL",
    "https://jll.wd1.myworkdayjobs.com/jllcareers",
    [
      "workday",
      "jll.wd1.myworkdayjobs.com",
      "jllcareers"
    ],
    "https://jll.wd1.myworkdayjobs.com/en-US/jllcareers/job/Analyst---AML--KYC-Sanctions-Screening_REQ539218",
    [
      "jll",
      "jones lang lasalle"
    ]
  ],
  "external-aduna": [
    "Aduna Global",
    "https://jobs.lever.co/adunaglobal",
    [
      "lever",
      "adunaglobal",
      ""
    ],
    "https://jobs.lever.co/adunaglobal/8a40bde2-d7e1-41af-ac98-fce330280e7c",
    [
      "aduna global",
      "adunaglobal"
    ]
  ],
  "external-jeeves": [
    "Jeeves",
    "https://jobs.lever.co/tryjeeves",
    [
      "lever",
      "tryjeeves",
      ""
    ],
    "https://jobs.lever.co/tryjeeves/?workplaceType=hybrid",
    [
      "jeeves",
      "tryjeeves"
    ]
  ],
  "external-everymatrix": [
    "EveryMatrix",
    "https://everymatrix.teamtailor.com/jobs",
    [
      "teamtailor",
      "everymatrix.teamtailor.com",
      ""
    ],
    "https://everymatrix.teamtailor.com/jobs",
    [
      "everymatrix"
    ]
  ],
  "external-kaizen": [
    "Kaizen Gaming",
    "https://careers.kaizengaming.com/apply",
    [
      "diagnostic",
      "careers.kaizengaming.com",
      "/job-details/"
    ],
    "https://careers.kaizengaming.com/apply",
    [
      "kaizen gaming",
      "kaizengaming",
      "betano",
      "stoiximan"
    ]
  ],
  "external-waystone": [
    "Waystone",
    "https://www.waystone.com/careers/",
    [
      "diagnostic",
      "www.waystone.com",
      "/careers/"
    ],
    "https://www.waystone.com/careers/",
    [
      "waystone"
    ]
  ],
  "external-universal-investment": [
    "Universal Investment",
    "https://www.universal-investment.com/en/corporate/career/open-positions/",
    [
      "diagnostic",
      "www.universal-investment.com",
      "/en/corporate/career/"
    ],
    "https://www.universal-investment.com/en/corporate/career/open-positions/",
    [
      "universal investment",
      "universal-investment"
    ]
  ],
  "external-platin-gaming": [
    "Platin Gaming",
    "https://platingaming.com/careers/jobs",
    [
      "diagnostic",
      "platingaming.com",
      "/careers/jobs"
    ],
    "https://platingaming.com/careers/jobs",
    [
      "platin gaming",
      "platingaming"
    ]
  ],
  "external-manulife": [
    "Manulife",
    "https://manulife.wd3.myworkdayjobs.com/MFCJH_Jobs",
    [
      "workday",
      "manulife.wd3.myworkdayjobs.com",
      "MFCJH_Jobs"
    ],
    "https://manulife.wd3.myworkdayjobs.com/en-US/MFCJH_Jobs/job/AML-Compliance-Manager_JR25101208-1",
    [
      "manulife",
      "john hancock"
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
            if match:
                if match in active:
                    raise ValueError("Already monitored group: "+str(match))
                found=[x for x in original if x["id"]==match]
                if len(found)!=1:
                    raise ValueError("Ambiguous catalog group: "+str(match))
                old=found[0]
                aliases_n={normalized(x) for x in aliases}
                exact=aliases_n.intersection({normalized(old.get("id","")),normalized(old.get("name",""))})
                if not exact and row["route"]!=old.get("route"):
                    raise ValueError("Potential original group alias; manual review required: "+str(match))
                row=dict(old)
                if any(x.get("route")==row.get("route") and x["id"] in active for x in original+registry):
                    raise ValueError("ATS route already monitored")
                result["origin"]="original_catalog"
                result["catalog_id"]=match
            else:
                result["origin"]="new_external_review"
                if route[0] in ("smart_review","lever"):
                    # Reuse only a known schema from the original catalog. Never invent
                    # a provider route when the public employer slug cannot be mapped.
                    kind=route[0]
                    slug=route[1]
                    examples=[x.get("route",[]) for x in original if len(x.get("route",[]))==3]
                    oldslug="wise" if kind=="smart_review" else "qonto"
                    templates=[r for r in examples if any(oldslug==str(v).lower() for v in r[1:]) and ((kind=="smart_review" and "smart" in str(r[0]).lower()) or (kind=="lever" and "lever" in str(r[0]).lower()))]
                    if len({tuple(r) for r in templates})!=1:
                        raise ValueError("No unique known original ATS route schema")
                    row["route"]=[slug if str(v).lower()==oldslug else v for v in templates[0]]
                    if any(x.get("route")==row["route"] for x in original+registry+live):
                        raise ValueError("ATS route already catalogued or monitored")

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
