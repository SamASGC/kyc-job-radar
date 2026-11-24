#!/usr/bin/env python3
"""Read-only full official ATS canary for seven companies from the new 100 EMI leads.

This probe does not enrol candidates into daily publication. Each source must
pass a positive-control listing count and its official employer application
route must be verified for all geographically plausible AML-matching roles.
Date and licence claims are never inferred from the company name alone.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from live_e2e18_full import audit_one
from two_lane_alert_preview import triage

# These IDs MUST correspond to entries in the 100-company discovery JSON.
# Site_jobs is a temporary prototype route. It may miss jobs on ATS providers;
# this is why each company needs a live positive-control audit before merging.
SOURCES = {
    "reg100-be-paynovate": {
        "id": "reg100-be-paynovate", "name": "Paynovate (Belgian EMI)",
        "route": ["site_jobs", "paynovate.breezy.hr", r"^/p/[a-z0-9-]+/?$"],
        "careers_url": "https://paynovate.breezy.hr/",
        "reference_job": "https://paynovate.breezy.hr/p/b818e181519e01-kyt-analyst",
        "regulator_reference": "https://www.nbb.be/doc/dq/cis/f/s122_list_3.htm",
    },
    "reg100-ie-currenxie-technologies-limited": {
        "id": "reg100-ie-currenxie-technologies-limited",
        "name": "Currenxie Technologies Limited (Irish EMI)",
        "route": ["site_jobs", "currenxie.com", r"^/eu/company/careers/?.*$"],
        "careers_url": "https://currenxie.com/eu/company/careers",
        "regulator_reference": "https://registers.centralbank.ie/",
    },
    "reg100-lu-pingpong-europe-s-a": {
        "id": "reg100-lu-pingpong-europe-s-a",
        "name": "PingPong Europe S.A. (Luxembourg EMI)",
        "route": ["site_jobs", "www.pingpongx.com", r"^/global/career-detail/[a-z0-9-]+/?$"],
        "careers_url": "https://www.pingpongx.com/global/career",
        "regulator_reference": "https://www.dnb.nl/en/public-register/information-detail/?registerCode=WFTEG&relationNumber=R180541",
    },
    "reg100-mt-payfuture-fs-mt-ltd": {
        "id": "reg100-mt-payfuture-fs-mt-ltd",
        "name": "PAYFUTURE FS MT LTD. (Malta EMI)",
        "route": ["site_jobs", "www.payfuture.net", r"^/careers/[a-z0-9-]+/?$"],
        "careers_url": "https://www.payfuture.net/careers/",
        "regulator_reference": "https://www.lb.lt/en/sfi-financial-market-participants/payfuture-fs-mt-ltd",
    },
    "reg100-de-allunity-gmbh": {
        "id": "reg100-de-allunity-gmbh",
        "name": "AllUnity GmbH (Germany EMI)",
        "route": ["site_jobs", "allunity.com", r"^/careers/[a-z0-9-]+/?$"],
        "careers_url": "https://allunity.com/careers",
        "regulator_reference": "https://allunity.com/trust-center",
    },
    "reg100-es-outpayce-s-a": {
        "id": "reg100-es-outpayce-s-a",
        "name": "OUTPAYCE S.A. (Spanish EMI, Amadeus group)",
        "route": ["site_jobs", "outpayce.com", r"^/en/company/careers/.+$"],
        "careers_url": "https://outpayce.com/en/company/careers",
        "regulator_reference": "https://www.bde.es/webbe/es/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-instituciones-financieras-monetarias-pais/lista-mfi-es.html",
        "employer_identity_warning": "Amadeus Workday positions not automatically attributable to Outpayce",
    },
    "reg100-lt-uab-monavate": {
        "id": "reg100-lt-uab-monavate",
        "name": "UAB Monavate (Lithuanian EMI)",
        "route": ["site_jobs", "www.monavate.com", r"^/careers/[a-z0-9-]+/?$"],
        "careers_url": "https://www.monavate.com/careers",
        "regulator_reference": "https://www.lb.lt/en/sfi-financial-market-participants/uab-monavate",
    },
}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True, choices=tuple(SOURCES))
    p.add_argument("--out", required=True)
    p.add_argument("--minutes", type=int, default=3)
    args = p.parse_args()
    if not 1 <= args.minutes <= 5:
        raise ValueError("Unexpected per-provider request budget")
    directory=json.loads(Path("experiments/aml339/regulator100_discovery_queue.json").read_text(encoding="utf-8"))
    included={x["id"]:x for x in directory["candidates"]}
    if len(included)!=100 or args.source not in included:
        raise ValueError("Employer not in the immutable 100-entity research list")
    result=audit_one(SOURCES[args.source],minutes=args.minutes)
    for job in result.get("audited",[]):
        alert,reason=triage(args.source,job)
        print("REG100_JOB_TRIAGE",json.dumps({
            "source":args.source,"title":job.get("title"),"url":job.get("url"),
            "location":job.get("location"),
            "explicit_duties":job.get("evaluation",{}).get("explicit_duties"),
            "barriers":job.get("evaluation",{}).get("barriers"),
            "lane":alert.get("lane") if alert else None,
            "reason":reason,
        },ensure_ascii=False)[:3500],flush=True)
    envelope={
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "source_registry":"regulated_emi_reg100_canary_v1",
        "original_catalog_sources":339,
        "total_configured_sources":339,
        "sources_requested":[args.source],
        "sources":[result],
    }
    Path(args.out).write_text(json.dumps(envelope,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("REG100_EMPLOYER_SOURCE",json.dumps({
        "source":args.source,"state":result.get("state"),
        "listed":result.get("total_listed"),"matched":result.get("relevant_leads"),
        "audited":len(result.get("audited",[])),
        "unverified_in_scope":result.get("unverified_in_scope"),
        "errors":result.get("errors"),"warnings":result.get("warnings")
    },ensure_ascii=False),flush=True)
    if result.get("state")!="listing_extracted" or result.get("list_complete") is not True:
        raise SystemExit("Official listing incomplete; NOT promoting "+args.source)
    if result.get("unverified_in_scope")!=0:
        raise SystemExit("Not all relevant official application routes verified")

if __name__=="__main__":
    main()
