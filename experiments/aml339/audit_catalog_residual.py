#!/usr/bin/env python3
"""Read-only next-50 catalog audit. Preserve each individual failed or valid result."""
import argparse,datetime as dt,json
from pathlib import Path
from live_e2e18_full import audit_one
from two_lane_alert_preview import triage

def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--selection",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    selection=json.loads(a.selection.read_text());rows=selection["candidates"]
    if not 1<=len(rows)<=50 or len({x["id"] for x in rows})!=len(rows):raise ValueError("Invalid selection")
    catalog=Path("fuentes.json");before=catalog.read_bytes();original=json.loads(before)["sources"]
    by={x["id"]:x for x in original}
    row=by[a.source]
    selected=next(x for x in rows if x["id"]==a.source)
    if row["route"]!=selected["route"] or row["careers_url"]!=selected["careers_url"]:raise ValueError("Selected route differs from original catalog")
    if any(x in str(row).casefold() for x in ("workable.com","sage.hr","linkedin.com/jobs")):raise ValueError("Blocked provider")
    r=audit_one(row,minutes=4)
    if catalog.read_bytes()!=before:raise ValueError("Catalog modified")
    ok=(r.get("state")=="listing_extracted" and r.get("list_complete") is True
        and type(r.get("total_listed")) is int and r["total_listed"]>0
        and r.get("relevant_leads")==len(r.get("audited",[])) and r.get("unverified_in_scope")==0
        and r.get("listing_untrackable_count")==0)
    matches=[]
    for j in r.get("audited",[]):
        alert,reason=triage(a.source,j)
        if alert:matches.append({"title":j.get("title"),"url":j.get("url"),"location":j.get("location"),"lane":alert.get("lane")})
    data={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA","source_registry":"original_339","total_configured_sources":339,"sources_requested":[a.source],"verified":ok,"sources":[r],"qualifying":matches}
    a.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    print("CATALOG_RESIDUAL_AUDIT",json.dumps({"id":a.source,"verified":ok,"listed":r.get("total_listed"),"errors":r.get("errors"),"qualifying":len(matches)}),flush=True)
    if not ok:raise SystemExit("Incomplete or unproven empty source")
if __name__=="__main__":main()
