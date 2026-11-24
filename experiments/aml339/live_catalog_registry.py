#!/usr/bin/env python3
"""Daily live audit of previously proven, enrolled original catalog sources."""
import argparse,datetime as dt,json
from pathlib import Path
from external_live_registry import ids
from live_e2e18_full import audit_one

def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True,choices=ids(catalog=True));p.add_argument("--out",required=True);a=p.parse_args()
    catalog=Path("fuentes.json")
    original=catalog.read_bytes()
    rows=json.loads(original)["sources"]; by={x["id"]:x for x in rows}
    if len(rows)!=339 or len(by)!=339 or not set(ids(catalog=True)).issubset(by):raise ValueError("Original catalog identity mismatch")
    row=by[a.source]
    if "workable" in str(row.get("route",[])).lower():raise ValueError("Blocked provider not enrolled")
    r=audit_one(row,minutes=4)
    if catalog.read_bytes()!=original:raise ValueError("Catalog mutated during audit")
    ok=(r.get("state")=="listing_extracted" and r.get("list_complete") is True
        and type(r.get("total_listed")) is int and r["total_listed"]>0
        and r.get("relevant_leads")==len(r.get("audited",[])) and r.get("unverified_in_scope")==0
        and r.get("listing_untrackable_count")==0)
    if not ok:r.update(state="listing_failed",list_complete=False)
    envelope={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA","source_registry":"original_339","total_configured_sources":339,"sources_requested":[a.source],"verified":ok,"sources":[r]}
    Path(a.out).write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+"\n")
    print("CATALOG_REGISTRY_AUDIT",json.dumps({"id":a.source,"verified":ok,"listed":r.get("total_listed"),"errors":r.get("errors")}),flush=True)
    if not ok:raise SystemExit("Incomplete or unproven empty source")
if __name__=="__main__":main()
