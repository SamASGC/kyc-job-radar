#!/usr/bin/env python3
"""Read-only audit for the next two official boards. Does not publish alerts."""
import argparse, datetime as dt, json, re
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from live_external50_wave02 import Anchors, read_page, candidate
from live_e2e18_full import audit_one
import live_e2e18_full as audit
from amlradar.sources import Board

SOURCES={
 "external50b-es-unnax":("Powens / Unnax","https://careers.powens.com/jobs",["teamtailor","careers.powens.com",""],r"^/jobs/[0-9]+-[^/]+/?$"),
 "external50b-es-onyx":("Onyx CenterSource","https://ats.rippling.com/onyxcentersource/jobs",["site_jobs","ats.rippling.com",r"^/onyxcentersource/jobs/[0-9a-f-]{36}/?$"],r"^/onyxcentersource/jobs/[0-9a-f-]{36}/?$"),
}

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--source",required=True,choices=SOURCES)
 p.add_argument("--out",required=True)
 a=p.parse_args()
 data=json.loads(Path("experiments/aml339/external_regulated50_wave02.json").read_text())
 assert len(data["candidates"])==50 and a.source in {x["id"] for x in data["candidates"]}
 name,url,route,pattern=SOURCES[a.source]
 page=Anchors();page.feed(read_page(url))
 expected={urlsplit(urljoin(url,h)).path.rstrip("/"):title for h,title in page.links.items() if urlsplit(urljoin(url,h)).hostname==urlsplit(url).hostname and re.fullmatch(pattern,urlsplit(urljoin(url,h)).path) and title}
 if not expected:raise RuntimeError("No independent official positive listing evidence")
 raw=Board.listing
 def checked_listing(board):
  jobs=raw(board)
  by={urlsplit(str(j.get("url",""))).path.rstrip("/"):j for j in jobs}
  if not set(expected).issubset(by):raise RuntimeError("Incomplete official job identity coverage")
  for key,title in expected.items():
   if not str(by[key].get("title","")).strip():by[key]["title"]=title
  print("NEXT_EXTERNAL_LINK_CONTROL",json.dumps({"source":a.source,"official":len(expected),"parser":len(by),"titles":list(expected.values())},ensure_ascii=False),flush=True)
  return jobs
 Board.listing=checked_listing
 audit.candidate=candidate
 result=audit_one({"id":a.source,"name":name,"careers_url":url,"route":route},minutes=4)
 ok=(result.get("state")=="listing_extracted" and result.get("list_complete") is True
     and isinstance(result.get("total_listed"),int) and result["total_listed"]>=len(expected)
     and result.get("relevant_leads")==len(result.get("audited",[]))
     and result.get("unverified_in_scope")==0 and result.get("listing_untrackable_count")==0)
 print("NEXT_EXTERNAL_AUDIT",json.dumps({"source":a.source,"verified":ok,"listed":result.get("total_listed"),"relevant":result.get("relevant_leads"),"errors":result.get("errors")}),flush=True)
 Path(a.out).write_text(json.dumps({"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA","source_registry":"external50_next_canary","original_catalog_sources":339,"total_configured_sources":339,"sources_requested":[a.source],"verified":ok,"sources":[result]},ensure_ascii=False,indent=2)+"\n")
 if not ok:raise SystemExit("Incomplete employer audit; not eligible for promotion")

if __name__=="__main__":main()
