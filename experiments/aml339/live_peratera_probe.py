#!/usr/bin/env python3
"""Read-only full official Personio ATS audit of small FCA-authorised UK EMI.

Peratera UK Limited states FCA e-money registration reference 1023849 on its
own official terms. That is an employer assertion; check FCA register again
before describing current authorisation as regulator-confirmed. A job tagged
"Remote Global" is NOT proof that a Spain-based applicant is eligible.
"""
import datetime as dt
import json
from pathlib import Path

from live_e2e18_full import audit_one
from two_lane_alert_preview import triage

SOURCE={
    "id":"emi-peratera-uk",
    "name":"Peratera UK Limited",
    "route":["personio","peratera.jobs.personio.com",""],
    "careers_url":"https://peratera.jobs.personio.com/",
    "company_terms":"https://www.peratera.co.uk/payment-services-terms",
    "claimed_fca_firm_reference":"1023849",
}

def main():
    result=audit_one(SOURCE,minutes=4)
    selected=[]
    for role in result.get("audited",[]):
        alert,reason=triage(SOURCE["id"],role)
        selected.append({
            "title":role.get("title"),
            "url":role.get("url"),
            "location":role.get("location"),
            "duty_evidence":role.get("evaluation",{}).get("explicit_duties"),
            "application_verified":role.get("evaluation",{}).get("application_verified"),
            "publication":role.get("evaluation",{}).get("publication_status"),
            "candidate_lane":alert["lane"] if alert else None,
            "blocker_or_reason":reason,
        })
    print("PERATERA_OFFICIAL_JOBS",json.dumps(selected,ensure_ascii=False),flush=True)
    payload={
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "source_registry":"employer_regulated_external_v1",
        "original_catalog_sources":339,
        "total_configured_sources":339,
        "sources_requested":[SOURCE["id"]],
        "sources":[result],
    }
    Path("peratera_live_audit.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n")
    print("PERATERA_AUDIT_RESULT",json.dumps({
       "source":SOURCE["id"],"state":result.get("state"),
       "listed":result.get("total_listed"),"relevant":result.get("relevant_leads"),
       "audited":len(result.get("audited",[])),
       "unverified":result.get("unverified_in_scope"),
       "errors":result.get("errors",[])
    },ensure_ascii=False),flush=True)
    if not (result.get("state")=="listing_extracted" and result.get("list_complete") is True
            and result.get("relevant_leads")==len(result.get("audited",[]))
            and result.get("unverified_in_scope")==0
            and result.get("total_listed",0)>=2):
        raise SystemExit("Company Personio job board not fully verified")

if __name__=="__main__":
    main()
