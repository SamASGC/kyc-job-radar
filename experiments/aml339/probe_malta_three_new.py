#!/usr/bin/env python3
"""Official site/ATS LIVE verification of additional Malta-licensed payment EMIs.

Research-only mode. Original 339 ZIP is immutable. No alert/public page writes.
Andaria: employer-linked BambooHR ATS.
FinXP and PayDo: owned domain careers listing with actual role detail pages.
"""
import argparse,datetime as dt,json
from pathlib import Path


REGULATED_CANDIDATES={
 "emi-andaria-mt":{
   "id":"emi-andaria-mt","name":"Andaria Financial Services Limited (MT EMI C97170)",
   "careers_url":"https://andaria.bamboohr.com/careers",
   "route":["bamboohr","andaria.bamboohr.com",""],
   "regulator_evidence":"https://andaria.com/legal-and-regulatory/",
 },
 "emi-finxp-mt":{
   "id":"emi-finxp-mt","name":"FinXP Limited (MT EMI C65783)",
   "careers_url":"https://finxp.com/careers/",
   "route":["site_jobs","finxp.com",r"^/careers/[^/?#]+/?$"],
   "regulator_evidence":"https://finxp.com/about-us/",
 },
 "emi-paydo-mt":{
   "id":"emi-paydo-mt","name":"Paydo EU Ltd (MT EMI C109162)",
   "careers_url":"https://paydo.com/career/",
   "route":["site_jobs","paydo.com",r"^/career/[^/?#]+/?$"],
   "regulator_evidence":"https://paydo.com/news-category/announcements/",
 },
}
def main():
  from live_e2e18_full import audit_one
  parser=argparse.ArgumentParser()
  parser.add_argument("--source",required=True,choices=tuple(REGULATED_CANDIDATES))
  parser.add_argument("--minutes",type=int,default=3)
  parser.add_argument("--out",required=True)
  a=parser.parse_args()
  if not 1<=a.minutes<=5:raise ValueError("Invalid per-source live HTTP budget")
  src=Path("fuentes.json")
  archive=src.read_bytes()
  original=json.loads(archive)["sources"]
  if len(original)!=339 or a.source in {s["id"] for s in original}:
      raise ValueError("Not a genuinely outside-catalog EMI source")
  cfg=REGULATED_CANDIDATES[a.source]
  report=audit_one(cfg,minutes=a.minutes)
  if src.read_bytes()!=archive:
      raise RuntimeError("Source archive mutated")
  data={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_registry":"regulated_emi_sidecar_v1",
        "original_catalog_sources":339,
        "total_configured_sources":339,
        "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "sources_requested":[a.source],
        "sources":[report]}
  Path(a.out).write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
  print("NEW_EMI_MALTA_OFFICIAL",json.dumps({
    "id":a.source,"state":report["state"],"complete":report["list_complete"],
    "listed":report["total_listed"],"matches":report["relevant_leads"],
    "audited":len(report["audited"]),
    "unverified":report["unverified_in_scope"],
    "errors":report["errors"],"warnings":report["warnings"][:3]
  },ensure_ascii=False),flush=True)
  if report["state"]!="listing_extracted" or report["list_complete"] is not True:
      raise SystemExit("Unverified EMI listing; refuse production promotion")

if __name__=="__main__":main()
