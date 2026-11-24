#!/usr/bin/env python3
"""Reconcile a whole batch, maintain durable research state, and emit review proposals.
Never modifies the production registry, public pages or alert history."""
import argparse,json,datetime as dt
from collections import Counter
from pathlib import Path
STATUSES={"NO_CONFIRMED_CAREERS","MULTIPLE_ATS_REVIEW_REQUIRED","PORTAL_NEEDS_ADAPTER","TECHNICAL_PASS_REVIEW_REQUIRED","INCOMPLETE_AUDIT","ERROR_OR_UNSUPPORTED","AUDIT_TIMEOUT_OR_MISSING"}
def reconcile(selection,previous,reports):
    rows=selection["selected"]
    expected={r["key"]:r for r in rows}
    if len(expected)!=len(rows) or len(rows)>50:raise ValueError("Invalid batch")
    if previous.get("schema")!="aml339_growth_ledger_v1":raise ValueError("Invalid prior ledger")
    old=previous["records"];records=dict(old)
    by={}
    for r in reports:
        k=r["key"]
        if k not in expected or k in by or r["id"]!=expected[k]["id"] or r["name"]!=expected[k]["name"]:raise ValueError("Unexpected or duplicate evidence")
        if r["status"] not in STATUSES or type(r["verified"]) is not bool:raise ValueError("Invalid source disposition")
        if r["verified"]!=(r["status"]=="TECHNICAL_PASS_REVIEW_REQUIRED"):raise ValueError("Inconsistent verification")
        if r["verified"] and (not isinstance(r.get("config"),dict) or type(r.get("listed")) is not int or r["listed"]<=0 or r.get("unverified")!=0):raise ValueError("Incomplete verified evidence")
        by[k]=r
    if set(by)!=set(expected):raise ValueError("Missing individual source report")
    for k,r in by.items():
        records[k]={**r,"checked_at":selection["checked_at"],"run_id":selection["run_id"]}
    proposals=[r for r in records.values() if r.get("verified") is True and r.get("status")=="TECHNICAL_PASS_REVIEW_REQUIRED"]
    summary={"schema":"aml339_growth_report_v1","run_id":selection["run_id"],"checked_at":selection["checked_at"],"selected":len(rows),"eligible_pending_before_batch":selection["eligible_pending"],"register_profiles_observed":selection["new_register_profiles_observed"],"discovery_errors":selection["discovery_errors"],"dispositions":dict(Counter(r["status"] for r in by.values())),"technical_passes":sum(r["verified"] for r in by.values()),"total_researched_unique_keys":len(records),"review_proposals_total":len(proposals),"results":list(by.values())}
    return {"schema":"aml339_growth_ledger_v1","records":records},summary,proposals
def main():
    p=argparse.ArgumentParser();p.add_argument("--selection",type=Path,required=True);p.add_argument("--previous",type=Path,required=True);p.add_argument("--reports",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--run-id",type=int,required=True);a=p.parse_args()
    selection=json.loads(a.selection.read_text());selection["run_id"]=a.run_id
    previous=json.loads(a.previous.read_text()) if a.previous.exists() else {"schema":"aml339_growth_ledger_v1","records":{}}
    reports=[json.loads(p.read_text()) for p in sorted(a.reports.rglob("result_*.json"))]
    ledger,summary,proposals=reconcile(selection,previous,reports)
    a.out.mkdir(parents=True,exist_ok=True)
    for name,obj in (("ledger.json",ledger),("latest.json",summary),("review_proposals.json",proposals)):
        (a.out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
    print("AML339_GROWTH_REPORT",json.dumps({k:v for k,v in summary.items() if k!="results"},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
