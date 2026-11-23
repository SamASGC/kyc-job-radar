#!/usr/bin/env python3
"""DRY RUN: two conservative AML vacancy alert lanes.

NO emails, push, scheduling, applications or production history updates.
Input: quality_audit JSON evidence, never plain title-only listings.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, re, urllib.parse
from collections import Counter
from pathlib import Path

PRIMARY={"SoF","SoW","PEP","Sanctions screening","Adverse media"}
SECONDARY={"TM","SAR/STR","Financial crime investigations"}
PURPOSE=PRIMARY|SECONDARY
KNOWN_FIRST_POSTING={"Vinted.GH.first_published","Greenhouse.first_published",
    "JSON-LD.datePosted","RSS.pubDate","Official employer detail: publication date"}
REQUIRED_FIELDS={"original_posting_date","publication_status","application_verified",
    "geography","functions","explicit_duties","barriers","uncertainties"}

def canonical_url(url):
    p=urllib.parse.urlsplit(url or "")
    if p.scheme not in ("https","http") or not p.hostname:return ""
    path=p.path.rstrip("/")
    # Preserve job path; do not use utm/gh_src tokens as a different vacancy.
    retained=urllib.parse.parse_qsl(p.query,keep_blank_values=True)
    retained=[(k,v) for k,v in retained if k in ("gh_jid","jobId","job_id","jid") and not re.search(r"/\d{6,}",path)]
    return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower(),path,
        urllib.parse.urlencode(retained),""))

def key(employer_id,role):
    u=canonical_url(role.get("url") or role.get("apply_url"))
    if not u:return ""
    return hashlib.sha256((employer_id+"|"+u+"|"+(role.get("title") or "").strip().casefold()).encode("utf-8")).hexdigest()[:24]

def triage(employer_id,role):
    evidence=role.get("evaluation") or {}
    if not REQUIRED_FIELDS.issubset(evidence):return None,"incomplete_evidence"
    if not key(employer_id,role):return None,"invalid_job_url"
    if evidence.get("barriers"):return None,"explicit_barrier"
    geo = evidence.get("geography")
    # Swiss employers are an explicit career target, but legal work eligibility
    # is unconfirmed. Admit only the same validated duties, form and dates;
    # preserve Swiss limitations on every published card and RSS entry.
    if geo not in ("target","swiss_future"):return None,"unconfirmed_or_outside_geography"
    if not evidence.get("application_verified"):return None,"application_unverified"
    if not set(evidence.get("functions") or []) & PURPOSE:return None,"no_incremental_aml_content"
    duties=set(evidence.get("explicit_duties") or []) & PURPOSE
    if not duties:return None,"target_functions_not_in_job_duties"
    publication=evidence["publication_status"]
    date_field=evidence.get("date_field") or ""
    cls=evidence.get("class")
    if (cls=="possible_match_confirmed_recent" or (geo=="swiss_future" and cls=="manual_review")) and publication=="fresh" \
            and date_field in KNOWN_FIRST_POSTING and evidence.get("original_posting_date"):
        lane="confirmed_recent"
    elif (cls=="manual_review" and publication in ("undated","boundary")
          or cls=="manual_review" and publication=="fresh" and date_field not in KNOWN_FIRST_POSTING):
        lane="promising_date_unconfirmed"
    else:
        return None,"not_eligible_for_either_lane"
    # Neither lane asserts training is offered or that employer will accept the applicant.
    return {
        "lane":lane,"employer_id":employer_id,"role_key":key(employer_id,role),
        "title":role.get("title"),"url":canonical_url(role.get("url")),
        "location":role.get("location"),"geography":geo,"publication_status":publication,
        "date_field":date_field,"original_date":evidence.get("original_posting_date"),
        "confirmed_job_duties":sorted(duties),"skills_mentioned":evidence.get("functions"),
        "application_route_checked":True,
        "limitations":evidence.get("uncertainties") or [],
        "note":("Suiza: no se ha verificado elegibilidad laboral, permiso ni aceptación de la candidatura. "
                if geo=="swiss_future" else "") +
               "El anuncio se ha analizado automáticamente; no confirma formación ni elegibilidad profesional."
    },None

def preview(records,limit_recent=12,limit_unknown=12):
    lanes={"confirmed_recent":[],"promising_date_unconfirmed":[]}
    suppressed=Counter();fingerprints=set()
    for employer_id,role in records:
        item,reason=triage(employer_id,role)
        if not item:
            suppressed[reason]+=1;continue
        if item["role_key"] in fingerprints:
            suppressed["duplicate_role_key"]+=1;continue
        fingerprints.add(item["role_key"])
        lanes[item["lane"]].append(item)
    weight=lambda it:(len(set(it.get("confirmed_job_duties") or []) & PRIMARY)*4 +
                      len(set(it.get("confirmed_job_duties") or []) & SECONDARY)*2)
    for lane in lanes:
        lanes[lane].sort(key=lambda it:(-weight(it),it["employer_id"],it["title"] or ""))
    included={"confirmed_recent":lanes["confirmed_recent"][:limit_recent],
              "promising_date_unconfirmed":lanes["promising_date_unconfirmed"][:limit_unknown]}
    return {
       "mode":"DRY_RUN_ONLY_NO_NOTIFICATIONS",
       "policy":{
          "confirmed_recent":"72-hour original publication, verified application route, target geography (including Swiss with eligibility warning), duties and no explicit barriers",
          "promising_date_unconfirmed":"Employer application route exists; original posting date missing, boundary or not trustworthy; NOT labelled new",
          "digest_recommendation":"Separate low-frequency manual-review digest; no duplicate alerts or sending enabled",
          "limitations":"Review requirements and legal employing entity manually; alerts are not proof of training or eligibility"},
       "total_reviewed":len(records),
       "eligible_before_display_limits":{lane:len(items) for lane,items in lanes.items()},
       "suppressed_reasons":dict(suppressed),
       "preview":included,
       "hidden_beyond_preview_limit":{lane:len(lanes[lane])-len(included[lane]) for lane in lanes}
    }

def role_template(**kw):
    e={"class":"manual_review","geography":"target","functions":["PEP","Sanctions screening"],
       "explicit_duties":["PEP"],"barriers":[],"uncertainties":["Publicación no declarada"],
       "original_posting_date":None,"publication_status":"undated","date_field":"",
       "application_verified":True}
    e.update(kw.pop("evaluation",{}))
    return {"title":kw.pop("title","Junior AML Analyst"),
            "url":kw.pop("url","https://careers.example.org/jobs/1234567"),
            "location":kw.pop("location","Vilnius, Lithuania"),
            "evaluation":e,**kw}

def tests():
    role=role_template()
    out=preview([("company",role)])
    assert len(out["preview"]["promising_date_unconfirmed"])==1
    assert not out["preview"]["confirmed_recent"]
    assert triage("company",role_template(evaluation={"explicit_duties":[]}))[1]=="target_functions_not_in_job_duties"
    assert triage("company",role_template(evaluation={"barriers":["Maltese required"]}))[1]=="explicit_barrier"
    assert triage("company",role_template(evaluation={"geography":"outside_scope"}))[1]=="unconfirmed_or_outside_geography"
    assert triage("company",role_template(evaluation={"publication_status":"old"}))[1]=="not_eligible_for_either_lane"
    recent=role_template(evaluation={"class":"possible_match_confirmed_recent","publication_status":"fresh",
        "original_posting_date":dt.datetime.now(dt.timezone.utc).isoformat(),
        "date_field":"Vinted.GH.first_published","uncertainties":[]})
    assert triage("company",recent)[0]["lane"]=="confirmed_recent"
    untrusted=role_template(evaluation={"class":"manual_review","publication_status":"fresh",
        "date_field":"Ashby.publishedAt"})
    assert triage("company",untrusted)[0]["lane"]=="promising_date_unconfirmed"
    duplicate=role_template(url="https://careers.example.org/jobs/1234567?utm_campaign=email")
    d=preview([("company",role),("company",duplicate)])
    assert len(d["preview"]["promising_date_unconfirmed"])==1 and d["suppressed_reasons"]["duplicate_role_key"]==1
    # Several first-party sites publish multiple inline job cards under one careers URL.
    distinct_titles=preview([("company",role),("company",role_template(title="AML Screening Officer"))])
    assert len(distinct_titles["preview"]["promising_date_unconfirmed"])==2
    print("TWO_LANE_POLICY_TESTS_PASSED",flush=True)

def read_evidence(paths):
    rows=[]
    for path in paths:
        d=json.loads(Path(path).read_text(encoding="utf-8"))
        if d.get("total_configured_sources")!=339:raise ValueError("Unexpected source configuration")
        for source in d.get("sources",[]):
            if "audited" not in source or not isinstance(source["audited"],list):
                raise ValueError("Missing individual role evidence")
            rows.extend((source["source_id"],r) for r in source["audited"])
    return rows

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--out",default="alert_preview.json")
    p.add_argument("--max-each",type=int,default=12)
    p.add_argument("evidence",nargs="*")
    a=p.parse_args()
    tests()
    if a.self_test:return
    if not a.evidence:raise SystemExit("Missing quality evidence JSON files")
    if not 1<=a.max_each<=30:raise SystemExit("Invalid display limit")
    evidence=read_evidence(a.evidence)
    report=preview(evidence,a.max_each,a.max_each)
    report["evidence_files"]=[str(x) for x in a.evidence]
    Path(a.out).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("TWO_LANE_PREVIEW",json.dumps({
        "reviewed":report["total_reviewed"],
        "eligible":report["eligible_before_display_limits"],
        "suppressed":report["suppressed_reasons"]},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
