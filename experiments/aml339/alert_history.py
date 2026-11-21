#!/usr/bin/env python3
"""Isolated read-only AML339 end-to-end alert-state engine.

Input: source-by-source quality audit with original extractor evidence.
Output: JSON and Markdown simulated alerts + separate persistent state.
It NEVER sends emails, modifies production deduplication, or applies for jobs.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

from two_lane_alert_preview import triage, read_evidence, role_template

STATE_VERSION=1
LANES=("confirmed_recent","promising_date_unconfirmed")
RUN_MODE="E2E_DRY_RUN_NO_NOTIFICATIONS"
MAX_RECORDS=100000
HEX_KEY=re.compile(r"^[0-9a-f]{24}$")

def iso_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def blank_history():
    return {"schema":STATE_VERSION,"created_at":iso_utc(),
            "updated_at":None,"prior_run_id":None,"records":{}}

def check_history(state):
    if not isinstance(state,dict) or state.get("schema")!=STATE_VERSION:
        raise ValueError("Unknown/invalid history schema; refusing to reset past alerts")
    if not isinstance(state.get("records"),dict):
        raise ValueError("History records missing")
    if len(state["records"])>MAX_RECORDS:
        raise ValueError("Unexpected large history")
    for rid,value in state["records"].items():
        if not HEX_KEY.fullmatch(rid):
            raise ValueError("Invalid historical role key")
        if not isinstance(value,dict) or not isinstance(value.get("delivered_lanes"),list):
            raise ValueError("Malformed historical record")
        if any(x not in LANES for x in value["delivered_lanes"]):
            raise ValueError("Unexpected historical lane")
        if len(value["delivered_lanes"])!=len(set(value["delivered_lanes"])):
            raise ValueError("Duplicate lane in history")
    return state

def load_history(path):
    if path is None:
        return blank_history()
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    return check_history(data)

def verify_input_coverage(paths,expected_sources,require_complete=True):
    if not paths:
        raise ValueError("No input evidence")
    all_sources={}
    for path in paths:
        d=json.loads(Path(path).read_text(encoding="utf-8"))
        if d.get("total_configured_sources")!=339:
            raise ValueError("Unexpected catalog size")
        if d.get("mode")!="READ_ONLY_ISOLATED_NO_PRODUCTION_DATA":
            raise ValueError("Expected read-only source evidence")
        for source in d["sources"]:
            sid=source["source_id"]
            if sid in all_sources:
                raise ValueError("Duplicate source in run evidence")
            if source.get("state")!="listing_extracted":
                raise ValueError("Partial or failed source listing: "+sid)
            if require_complete and source.get("list_complete") is not True:
                raise ValueError("Incomplete listing: "+sid)
            count=source.get("relevant_leads")
            audited=source.get("audited")
            if not isinstance(count,int) or not isinstance(audited,list) or len(audited)!=count:
                raise ValueError("Not all matching jobs read: "+sid)
            if any(not isinstance(x.get("evaluation"),dict) for x in audited):
                raise ValueError("Missing job evaluation: "+sid)
            all_sources[sid]=source
    if set(all_sources)!=set(expected_sources):
        raise ValueError("Expected source mismatch: "+repr((set(all_sources),set(expected_sources))))
    return all_sources

def select_and_merge(records,history,run_id=None,configured_sources=None):
    state=check_history(json.loads(json.dumps(history)))
    now=iso_utc()
    new_items={lane:[] for lane in LANES}
    observations={}
    reasons=Counter()
    for source_id,role in records:
        item,error=triage(source_id,role)
        if item is None:
            reasons[error or "unspecified"]+=1
            continue
        fingerprint=item["role_key"]
        # Prefer the fully confirmed date if two representations occur in one scan.
        prev=observations.get(fingerprint)
        if prev is None or (item["lane"]=="confirmed_recent" and prev["lane"]!="confirmed_recent"):
            observations[fingerprint]=item
        else:
            reasons["duplicate_within_current_run"]+=1
    prior_count=len(state["records"])
    for rid,item in observations.items():
        prev=state["records"].get(rid)
        if prev is None:
            prev={"first_seen":now,"last_seen":now,"title":item["title"],
                  "last_url":item["url"],"delivered_lanes":[]}
            state["records"][rid]=prev
        lanes=prev["delivered_lanes"]
        lane=item["lane"]
        if lane=="promising_date_unconfirmed" and "confirmed_recent" in lanes:
            reasons["not_downgraded_after_confirmed"]+=1
        elif lane in lanes:
            reasons["already_reported_in_lane"]+=1
        else:
            new_items[lane].append(item)
            lanes.append(lane)
        prev["last_seen"]=now
        prev["title"]=item["title"]
        prev["last_url"]=item["url"]
        prev["current_lane"]=lane
    state["updated_at"]=now
    state["prior_run_id"]=str(run_id) if run_id else state.get("prior_run_id")
    check_history(state)
    def sort_score(x):
        v=set(x.get("confirmed_job_duties",[]))
        score=sum(4 if i in {"PEP","Sanctions screening","Adverse media","SoF","SoW"} else 2 for i in v)
        return (-score,x["employer_id"],x["title"] or "")
    for lane in LANES:new_items[lane].sort(key=sort_score)
    return state,{
        "checked_at_utc":now,
        "mode":RUN_MODE,
        "source_count":len(configured_sources) if configured_sources is not None else len(set(source_id for source_id,_ in records)),
        "sources_with_role_matches":len(set(source_id for source_id,_ in records)),
        "roles_evaluated":len(records),
        "qualifying_distinct_roles":len(observations),
        "history_before":prior_count,
        "history_after":len(state["records"]),
        "new_counts":{lane:len(new_items[lane]) for lane in LANES},
        "new_alert_previews":new_items,
        "suppressed_reasons":dict(reasons),
        "warnings":[
          "No real notifications sent, applications submitted or production files modified.",
          "The date-unconfirmed lane is NOT a list of newly posted jobs.",
          "ATS application access does not prove the employer will accept the candidate.",
          "Only audited matched roles were considered; no inference about the unscanned 339-source catalog."
        ],
    }

def write_markdown(report,filename):
    lines=["# Simulación de alertas AML — sin envíos reales","",
      "Comprobadas "+str(report["roles_evaluated"])+" fichas en "+str(report["source_count"])+" portales.",
      "Primera aparición en este historial: "+str(report["history_before"]==0)+".",
      ""]
    for lane,heading in [("confirmed_recent","Novedades confirmadas (fecha original en 72 h)"),
                         ("promising_date_unconfirmed","Para revisar: fecha de publicación no confirmada")]:
        items=report["new_alert_previews"][lane]
        lines.extend(["## "+heading,"",str(len(items))+" aviso(s) simulado(s).",""])
        for it in items:
            lines.extend(["- **"+str(it["title"])+"** — "+str(it["location"])+
                " ("+str(it["employer_id"])+")", "  - "+str(it["url"]),
                "  - Funciones de la ficha: "+", ".join(it["confirmed_job_duties"]),
                "  - "+it["note"]])
        lines.append("")
    lines.extend(["## Registros suprimidos","",
        json.dumps(report["suppressed_reasons"],ensure_ascii=False,indent=2),
        "","No se han enviado mensajes ni actualizado el historial de producción.",""])
    Path(filename).write_text("\n".join(lines),encoding="utf-8")

def tests():
    r=role_template()
    state=blank_history()
    a,new=select_and_merge([("company",r)],state,"test-first")
    assert new["new_counts"]=={"confirmed_recent":0,"promising_date_unconfirmed":1}
    assert len(a["records"])==1
    b,replay=select_and_merge([("company",r)],a,"test-second")
    assert replay["new_counts"]=={"confirmed_recent":0,"promising_date_unconfirmed":0}
    assert replay["suppressed_reasons"]["already_reported_in_lane"]==1
    fresh=role_template(evaluation={"class":"possible_match_confirmed_recent",
        "publication_status":"fresh","original_posting_date":iso_utc(),
        "date_field":"Vinted.GH.first_published","uncertainties":[]})
    c,promoted=select_and_merge([("company",fresh)],b,"test-promotion")
    assert promoted["new_counts"]=={"confirmed_recent":1,"promising_date_unconfirmed":0}
    _,repeat=select_and_merge([("company",fresh)],c,"test-fourth")
    assert repeat["new_counts"]=={"confirmed_recent":0,"promising_date_unconfirmed":0}
    _,downgrade=select_and_merge([("company",r)],c,"test-fifth")
    assert downgrade["new_counts"]=={"confirmed_recent":0,"promising_date_unconfirmed":0}
    assert downgrade["suppressed_reasons"]["not_downgraded_after_confirmed"]==1
    second=role_template(title="Compliance Screening Associate")
    _,two=select_and_merge([("company",r),("company",second)],blank_history())
    assert two["new_counts"]["promising_date_unconfirmed"]==2
    duplicated=select_and_merge([("company",r),("company",r)],blank_history())[1]
    assert duplicated["new_counts"]["promising_date_unconfirmed"]==1
    assert duplicated["suppressed_reasons"]["duplicate_within_current_run"]==1
    for corrupted in [None,{},{"schema":5,"records":{}},
                      {"schema":1,"records":{"not-a-key":{"delivered_lanes":[]}}}]:
        try:check_history(corrupted)
        except ValueError:pass
        else:raise AssertionError("Malformed historical state was accepted")
    no_match_source=select_and_merge([("company",r)],blank_history(),configured_sources=["company","empty"])[1]
    assert no_match_source["source_count"]==2 and no_match_source["sources_with_role_matches"]==1
    print("E2E_ALERT_HISTORY_TESTS_PASSED",flush=True)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--self-test",action="store_true")
    a.add_argument("--state-in")
    a.add_argument("--state-out",default="isolated_alert_history.json")
    a.add_argument("--json-out",default="isolated_alert_previews.json")
    a.add_argument("--md-out",default="isolated_alert_previews.md")
    a.add_argument("--expect-sources",default="verifo-lithuania,demivolt-lithuania,vinted")
    a.add_argument("--run-id")
    a.add_argument("evidence",nargs="*")
    args=a.parse_args()
    tests()
    if args.self_test:return
    sources=[x.strip() for x in args.expect_sources.split(",") if x.strip()]
    verify_input_coverage(args.evidence,sources,True)
    rows=read_evidence(args.evidence)
    before=load_history(args.state_in)
    state,report=select_and_merge(rows,before,args.run_id,configured_sources=sources)
    Path(args.state_out).parent.mkdir(parents=True,exist_ok=True)
    Path(args.json_out).parent.mkdir(parents=True,exist_ok=True)
    Path(args.state_out).write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Path(args.json_out).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    write_markdown(report,args.md_out)
    print("E2E_DRY_RUN_SUMMARY",json.dumps({
       "sources":report["source_count"],"roles":report["roles_evaluated"],
       "eligible":report["qualifying_distinct_roles"],
       "new":report["new_counts"],"history_before":report["history_before"],
       "history_after":report["history_after"],"suppressed":report["suppressed_reasons"]},
       ensure_ascii=False),flush=True)

if __name__=="__main__":main()
