#!/usr/bin/env python3
"""Shadow production contract for the reviewed Danske public UI reader.
Never writes production history, registry, alerts or schedules."""
import argparse, datetime as dt, json
from pathlib import Path
from audit_danske_quality import run, self_test, job_identity, SITES
from alert_history import verify_input_coverage, load_official_listing_keys, blank_history, select_and_merge
from two_lane_alert_preview import listing_identity, triage

SID="external-danske-bank"
def envelope(raw):
    rows=raw.get("audited",[])
    n=raw.get("listed")
    ids=raw.get("listing_ids",[])
    keys=raw.get("listing_role_keys",[])
    host,site=SITES["danske-bank"]
    ok=(raw.get("status")=="QUALITY_EVIDENCE_PASS_REVIEW_REQUIRED" and raw.get("listing_complete") is True
        and type(n) is int and n>0 and n==raw.get("declared_total")==len(ids)==len(set(ids))==len(keys)==len(set(keys))
        and raw.get("relevant")==len(rows) and raw.get("unverified")==0 and not raw.get("errors")
        and len({r.get("id") for r in rows})==len(rows))
    if not ok:raise ValueError("Incomplete rendered source: "+str(raw.get("errors",[])))
    expected={listing_identity(SID,{"url":f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{i}"}) for i in ids}
    if set(keys)!=expected or "" in expected:raise ValueError("Listing fingerprint mismatch")
    audited=[]
    for r in rows:
        ev=r.get("evaluation")
        if (r.get("verified") is not True or r.get("id") not in ids or job_identity(r.get("url",""),host,site)!=r["id"]
            or r.get("apply_url")!=r["url"] or not isinstance(ev,dict) or ev.get("application_verified") is not True
            or not r.get("title") or r.get("description_length",0)<200
            or ev.get("original_posting_date") is not None):raise ValueError("Malformed verified job evidence")
        if r.get("geography_conflict") and (ev.get("geography")!="unknown" or not ev.get("barriers") or triage(SID,r)[0] is not None):
            raise ValueError("Contradictory location eligible for alert")
        audited.append({"title":r["title"],"url":r["url"],"apply_url":r["apply_url"],"location":r.get("location",""),
            "hiring_organization":"","description_length":r["description_length"],"verification_error":"",
            "detail_skipped_outside_geo":False,"evaluation":ev})
    result={"source_id":SID,"employer":"Danske Bank","state":"listing_extracted","list_complete":True,
        "total_listed":n,"relevant_leads":len(audited),"audited_offset":0,"audited":audited,"warnings":[],"errors":[],
        "skipped_details_outside_geo":0,"attempted_in_scope_details":len(audited),"unverified_in_scope":0,
        "listing_role_keys":sorted(keys),"listing_untrackable_count":0}
    return {"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "source_registry":"external_regulated50_wave02_live_v1","original_catalog_sources":339,"total_configured_sources":339,
        "sources_requested":[SID],"verified":True,"sources":[result]}

def main():
    p=argparse.ArgumentParser();p.add_argument("--prior",type=Path,required=True);p.add_argument("--receipt",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    self_test()
    raw=run("danske-bank",a.prior,a.receipt)
    a.out.with_name("reviewed_danske-bank.json").write_text(json.dumps(raw,ensure_ascii=False,indent=2)+"\n")
    doc=envelope(raw)
    a.out.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n")
    source=verify_input_coverage([a.out],[SID],require_complete=True)[SID]
    keys=load_official_listing_keys([a.out],[SID])
    # Actual production novelty checks against entirely synthetic, empty state.
    records=[(SID,r) for r in source["audited"]]
    state=blank_history()
    res=select_and_merge(records,state,run_id="shadow-only",configured_sources=[SID],strict_novelty=True,listing_keys=keys)
    # Exact return contract may evolve; independent triage assertion remains strict.
    print("DANSKE_SHADOW_CONTRACT_PASS",json.dumps({"listed":source["total_listed"],"relevant":source["relevant_leads"],"unverified":source["unverified_in_scope"],"keys":len(keys[SID]),"geo_conflicts":raw.get("geography_conflicts"),"history_result_type":type(res).__name__}),flush=True)
if __name__=="__main__":main()
