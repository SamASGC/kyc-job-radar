#!/usr/bin/env python3
"""Independent complete evidence for one employer of the 50-source bulk wave."""
import argparse,datetime as dt,json
from pathlib import Path
from batch50_sources import BATCH50
from live_e2e18_full import audit_one

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,choices=BATCH50)
    p.add_argument("--minutes",type=int,default=3)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    if not 1<=a.minutes<=5:raise ValueError("Invalid per-source rate-limit budget")
    src=Path("fuentes.json")
    raw=src.read_bytes()
    rows=json.loads(raw)["sources"]
    indexed={r["id"]:r for r in rows}
    if len(indexed)!=339 or len(rows)!=339 or not set(BATCH50).issubset(indexed):
        raise ValueError("Pinned source catalog is incomplete or source IDs not validated")
    result=audit_one(indexed[a.source],minutes=a.minutes)
    if src.read_bytes()!=raw:raise RuntimeError("Original source registry was modified")
    evidence={
       "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
       "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
       "source_registry":"original_339",
       "total_configured_sources":339,
       "batch":"bulk_50_regulated_fincrime_skills_first",
       "sources_requested":[a.source],
       "sources":[result],
    }
    Path(a.out).write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("AML339_BATCH50_SOURCE",json.dumps({
      "source":a.source,"state":result.get("state"),
      "list_complete":result.get("list_complete"),
      "total_listed":result.get("total_listed"),
      "relevant_leads":result.get("relevant_leads"),
      "detail_audited":len(result.get("audited",[])),
      "unverified_in_scope":result.get("unverified_in_scope"),
      "warnings":result.get("warnings",[])[:2],
      "errors":result.get("errors",[])[:2],
    },ensure_ascii=False),flush=True)
    if result["state"]!="listing_extracted" or result["list_complete"] is not True:
        raise SystemExit("Live employer board not completely verified: "+a.source)

if __name__=="__main__":main()
