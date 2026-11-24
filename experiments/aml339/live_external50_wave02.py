#!/usr/bin/env python3
"""Read-only canary for externally discovered employer boards. Never publishes alerts."""
import argparse, datetime as dt, json
from pathlib import Path
from live_e2e18_full import audit_one
from two_lane_alert_preview import triage

# Observed official links on 2026-11-24. Positive controls for this one canary,
# not permanent minimum headcounts. External provider matching may need a
# dedicated parser; failure is explicitly retained.
SOURCES={
 "external50b-lv-paybis":("Paybis","https://paybis.com/career/",["site_jobs","talent.sage.hr",r"^/jobs/[0-9a-f-]{36}/?$"],20),
 "external50b-lv-neverless":("Neverless","https://neverless.com/es-eea/careers",["site_jobs","neverless.com",r"^/(?:[a-z]{2}[-_][a-zA-Z]{2}/)?careers/[a-z0-9-]+/?$"],3),
 "external50b-lv-noah":("Noah","https://noah.com/careers",["site_jobs","noah.com",r"^/careers/[0-9a-f-]{36}/?$"],8),
}

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--source",required=True,choices=SOURCES)
 p.add_argument("--out",required=True)
 a=p.parse_args()
 names=json.loads(Path("experiments/aml339/external_regulated50_wave02.json").read_text())["candidates"]
 assert len(names)==50 and a.source in {x["id"] for x in names}
 name,url,route,minimum=SOURCES[a.source]
 result=audit_one({"id":a.source,"name":name,"careers_url":url,"route":route},minutes=4)
 ok=(result.get("state")=="listing_extracted" and result.get("list_complete") is True and
     isinstance(result.get("total_listed"),int) and result["total_listed"]>=minimum and
     result.get("relevant_leads")==len(result.get("audited",[])) and result.get("unverified_in_scope")==0
     and result.get("listing_untrackable_count")==0)
 print("EXTERNAL50_CANARY",json.dumps({"id":a.source,"verified":ok,"listed":result.get("total_listed"),"errors":result.get("errors"),"unverified":result.get("unverified_in_scope")}),flush=True)
 for job in result.get("audited",[]):
  alert,reason=triage(a.source,job)
  print("EXTERNAL50_ROLE",json.dumps({"title":job.get("title"),"url":job.get("url"),"lane":alert.get("lane") if alert else None,"reason":reason,"duties":job.get("evaluation",{}).get("explicit_duties")},ensure_ascii=False),flush=True)
 Path(a.out).write_text(json.dumps({"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA","source_registry":"external_regulated50_wave02_canary","original_catalog_sources":339,"total_configured_sources":339,"sources_requested":[a.source],"verified":ok,"sources":[result]},ensure_ascii=False,indent=2)+"\n")
 if not ok:raise SystemExit("Unverified employer feed: do not promote")

if __name__=="__main__":main()
