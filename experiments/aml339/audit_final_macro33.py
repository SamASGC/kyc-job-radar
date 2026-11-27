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
  "visa-currencycloud": "https://visa.wd5.myworkdayjobs.com/en-US/Visa",
  "bjak": "https://jobs.ashbyhq.com/bjakcareer/f2a12019-1971-45c2-88cc-9280c4e6d01d",
  "binance": "https://jobs.lever.co/binance?department=Legal%20%26%20Compliance",
  "booming-games": "https://booming-games.jobs.personio.com/",
  "b2spin": "https://jobs.ashbyhq.com/b2spin/ccf678a3-1504-4389-b979-03ffc9b677f2",
  "yassir": "https://jobs.smartrecruiters.com/YassirGmbh/744000055579539-mlro-compliance-officer",
  "nexo": "https://nexo.breezy.hr/",
  "finary": "https://jobs.ashbyhq.com/finary/5fae2eb4-a35d-4f36-b547-f26d28715b48",
  "sportygroup": "https://job-boards.greenhouse.io/sportygroup",
  "primexbt": "https://job-boards.greenhouse.io/primexbt",
  "21shares": "https://job-boards.greenhouse.io/21shares",
  "capimoney": "https://jobs.ashbyhq.com/capimoney",
  "lt-nayax-global-legal-compliance": "https://www.nayax.com/careers/department/legal-compliance/"
}
EXTERNAL = {
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
      "morgan stanley"
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
      "cmc markets"
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
  "external-aduna": [
    "Aduna",
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
      "manulife"
    ]
  ],
  "external-american-express": [
    "American Express",
    "https://careers.americanexpress.com/en/sites/CX_1/jobs",
    [
      "diagnostic",
      "careers.americanexpress.com",
      "/en/sites/CX_1/job/"
    ],
    "https://careers.americanexpress.com/en/sites/CX_1/job/26016192",
    [
      "american express",
      "amex"
    ]
  ],
  "external-citi": [
    "Citi",
    "https://jobs.citi.com/search-jobs",
    [
      "diagnostic",
      "jobs.citi.com",
      "/job/"
    ],
    "https://lu.linkedin.com/jobs/view/transfer-agency-aml-kyc-analyst-at-citi-3865286922",
    [
      "citigroup",
      "citibank",
      "citi careers"
    ]
  ],
  "external-bny": [
    "BNY",
    "https://eofe.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/BNY-Careers/jobs",
    [
      "diagnostic",
      "eofe.fa.us2.oraclecloud.com",
      "/hcmUI/CandidateExperience/en/sites/BNY-Careers/job/"
    ],
    "https://lu.linkedin.com/jobs/view/senior-associate-anti-money-laundering-prevention-know-your-client-at-bny-4372754722",
    [
      "bny mellon",
      "bank of new york",
      "bny careers"
    ]
  ],
  "external-deutsche-boerse": [
    "Deutsche Börse / Clearstream",
    "https://careers.deutsche-boerse.com/control-functions",
    [
      "diagnostic",
      "careers.deutsche-boerse.com",
      "/jobs/"
    ],
    "https://careers.deutsche-boerse.com/jobs/intern-compliance-fcc-projects-data-analyst-associate-f-m-d/5ef6a2ab-0728-4a24-8aad-81d8882a332c",
    [
      "deutsche boerse",
      "deutsche börse",
      "clearstream"
    ]
  ],
  "external-barclays": [
    "Barclays",
    "https://search.jobs.barclays/en/search-jobs",
    [
      "diagnostic",
      "search.jobs.barclays",
      "/job/"
    ],
    "https://search.jobs.barclays/search-jobs/kyc/22545/1/1",
    [
      "barclays"
    ]
  ],
  "external-kroll": [
    "Kroll",
    "https://careers.kroll.com/en/listing-page",
    [
      "diagnostic",
      "careers.kroll.com",
      "/en/job/"
    ],
    "https://hcxs.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs?keyword=analyst&mode=location",
    [
      "kroll"
    ]
  ],
  "external-inetum": [
    "Inetum",
    "https://jobs.smartrecruiters.com/Inetum2",
    [
      "smart_review",
      "Inetum2",
      ""
    ],
    "https://jobs.smartrecruiters.com/Inetum2/744000138298449",
    [
      "inetum"
    ]
  ],
  "external-fayara": [
    "Fayara",
    "https://jobs.ashbyhq.com/fayaracareers",
    [
      "ashby",
      "api.ashbyhq.com",
      "fayaracareers"
    ],
    "https://jobs.ashbyhq.com/fayaracareers/dfd81c91-d4c7-4ba1-89ed-5299bbc21ccd",
    [
      "fayara"
    ]
  ],
  "external-langham-hall": [
    "Langham Hall",
    "https://careers.langhamhall.com/",
    [
      "diagnostic",
      "careers.langhamhall.com",
      "/postings/"
    ],
    "https://careers.langhamhall.com/postings/3c6230e1-d674-4521-befb-697ee54ea6a1",
    [
      "langham hall",
      "langhamhall"
    ]
  ],
  "external-ao-shearman": [
    "A&O Shearman",
    "https://careers.aoshearman.com/en/search-jobs",
    [
      "diagnostic",
      "careers.aoshearman.com",
      "/en/job/"
    ],
    "https://careers.aoshearman.com/en/job/luxembourg/aml-kyc-analyst/3392/45418610944",
    [
      "ao shearman",
      "aoshearman",
      "allen overy",
      "shearman sterling"
    ]
  ],
  "external-hsf-kramer": [
    "Herbert Smith Freehills Kramer",
    "https://careers.hsfkramer.com/global/en/search-results/",
    [
      "diagnostic",
      "careers.hsfkramer.com",
      "/global/en/job/"
    ],
    "https://lu.linkedin.com/jobs/view/kyc-analyst-aml-ctf-compliance-officer-at-herbert-smith-freehills-kramer-4467838773",
    [
      "herbert smith freehills",
      "hsfkramer"
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
      "vistra group"
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
    result={"id":sid,"verified":False,"enrollment_authorized":False,"reference_scope":"historical hiring or official portal lead; confirm current role, target geography and regulatory/employer identity before enrollment"}
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
            if route[0]=="site_jobs":row["job_pattern"]=route[2]
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
                    oldslug="wise" if kind=="smart_review" else "crypto"
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
            pagination=[{"href":urljoin(row["careers_url"],h),"label":t} for h,t in page.links.items() if urlsplit(urljoin(row["careers_url"],h)).hostname==row["route"][1] and re.search(r"\b(?:next|more|page|suivant|voir plus)\b",t,re.I)][:40]
            result.update(status="DIAGNOSTIC_NEEDS_COMPLETE_LISTING",observed_job_links=len(links),observed_urls=sorted(links)[:15],pagination_controls=pagination)
            a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
            print("HIRING_FIRST_AUDIT",json.dumps({k:v for k,v in result.items() if k!="config"},ensure_ascii=False),flush=True)
            return
        # Reuse the exact proven production driver where supported. Original
        # catalogue rows use the same audit as the catalog live worker.
        # Other approved original ATS route types remain research-only.
        if result.get("origin")=="new_external_review" and row["route"][0] in ("workday","greenhouse","teamtailor","site_jobs","smart_external"):
            from live_external_generic import audit_config
            report,driver_ok=audit_config(row)
        else:
            old=audit.candidate
            if result.get("origin")=="new_external_review":audit.candidate=candidate
            try:report=audit_one(row,minutes=4)
            finally:audit.candidate=old
            driver_ok=True
        n=report.get("total_listed")
        ok=(driver_ok and report.get("state")=="listing_extracted" and report.get("list_complete") is True
            and type(n) is int and n>0
            and report.get("relevant_leads")==len(report.get("audited",[]))
            and report.get("unverified_in_scope")==0 and report.get("listing_untrackable_count")==0)
        if not ok:report.update(state="listing_failed",list_complete=False)
        result.update(verified=ok,audit=report,status="TECHNICAL_PASS_REVIEW_REQUIRED" if ok else "INCOMPLETE")
        result["target_detail_leads"]=[{"title":j.get("title"),"location":j.get("location"),"url":j.get("url"),"functions":j.get("evaluation",{}).get("functions",[]),"barriers":j.get("evaluation",{}).get("barriers",[])} for j in report.get("audited",[]) if j.get("evaluation",{}).get("application_verified") is True and j.get("evaluation",{}).get("geography") in ("target","swiss_future")]
    except Exception as exc:
        result.update(status="HELD",error=type(exc).__name__+": "+str(exc)[:250])
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    report=result.get("audit",{})
    print("HIRING_FIRST_AUDIT",json.dumps({"id":sid,"verified":result["verified"],"status":result.get("status"),"listed":report.get("total_listed"),"relevant":report.get("relevant_leads"),"unverified":report.get("unverified_in_scope"),"error":result.get("error"),"errors":report.get("errors"),"plausible_geo":[{"title":j.get("title"),"location":j.get("location"),"url":j.get("url"),"error":j.get("verification_error")} for j in report.get("audited",[]) if j.get("evaluation",{}).get("geography") in ("target","swiss_future","remote_location_review","mixed_location_review","unknown")]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
