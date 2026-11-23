#!/usr/bin/env python3
"""Read-only full job auditing of regulator-sourced employer portals.

Both legal entities are independent from the 339 original catalog, and are
NOT automatically promoted to active alerts unless official listing, job
identity, jobs-by-country and relevant role details verify in production.
"""
import argparse,datetime as dt,json
from pathlib import Path
from live_e2e18_full import audit_one
from two_lane_alert_preview import triage

SOURCES={
 "reg50-nomupay-europe":{
   "id":"reg50-nomupay-europe","name":"NomuPay / UAB NomuPay Europe",
   "route":["personio","nomupay.jobs.personio.com",""],
   "careers_url":"https://nomupay.jobs.personio.com/",
   "regulatory_reference":"https://www.lb.lt/en/sfi-financial-market-participants//uab-nomupay-europe",
   "review_undated":True,
 },
 "reg50-mifinity-malta":{
   "id":"reg50-mifinity-malta","name":"MiFinity Malta Limited",
   "route":["site_jobs","mifinity.com","^/career/[a-z0-9-]+/?$"],
   "careers_url":"https://mifinity.com/careers/",
   "default_location":"Malta/UK/Ireland (confirm EACH listing)",
   "regulatory_reference":"https://fsr.mfsa.mt/Licences/",
   "review_undated":True,
 },
}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,choices=tuple(SOURCES))
    p.add_argument("--minutes",type=int,default=4)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    from pathlib import Path
    data=json.loads(Path("experiments/aml339/regulator50_external_candidates.json").read_text(encoding="utf-8"))
    originals={c["id"]:c for c in data["candidates"]}
    assert a.source in originals
    assert originals[a.source]["careers_url"]==SOURCES[a.source]["careers_url"]
    role=evaluate=audit_one(SOURCES[a.source],minutes=a.minutes)
    for row in role.get("audited",[]):
       item,reason=triage(a.source,row)
       print("REG50_EVALUATED_JOB",json.dumps({
          "source":a.source,"title":row.get("title"),"url":row.get("url"),
          "location":row.get("location"),
          "evaluation":row.get("evaluation"),
          "lane":item["lane"] if item else None,"reason":reason
       },ensure_ascii=False)[:2800],flush=True)
    envelope={
       "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
       "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
       "source_registry":"regulated_employer_sidecar_v2",
       "original_catalog_sources":339,
       "total_configured_sources":339,
       "sources_requested":[a.source],
       "sources":[role],
    }
    Path(a.out).write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("REG50_LIVE_SOURCE",json.dumps({
        "id":a.source,
        "state":role.get("state"),"list_complete":role.get("list_complete"),
        "total_listed":role.get("total_listed"),
        "title_matched":role.get("relevant_leads"),
        "roles_checked":len(role.get("audited",[])),
        "unverified_in_scope":role.get("unverified_in_scope"),
        "errors":role.get("errors"),"warnings":role.get("warnings")
    },ensure_ascii=False),flush=True)
    # Independent positive-control against actual employer pages: three
    # Personio and six MiFinity cards in the previous direct source inspection.
    if role.get("state")!="listing_extracted" or role.get("list_complete") is not True:
        raise SystemExit("Live original job listing NOT fully verified: "+a.source)
    if role.get("total_listed",0) < (3 if a.source=="reg50-nomupay-europe" else 6):
        raise SystemExit("Parser missed known active jobs; cannot promote "+a.source)
    if role.get("unverified_in_scope",0)!=0:
        raise SystemExit("In-scope job verification incomplete; cannot promote "+a.source)

if __name__=="__main__":main()
