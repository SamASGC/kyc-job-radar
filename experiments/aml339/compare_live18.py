#!/usr/bin/env python3
"""Compare employer job identities across archived and new live HTTP listings.

Identity is ATS job ID or distinct posting URL; title only discriminates when
multiple real roles share a single generic careers page. The report is NOT
proof of a new listing within 72 hours or active job application.
"""
from __future__ import annotations
import argparse,datetime as dt,json,re,unicodedata,urllib.parse
from collections import Counter
from pathlib import Path

def norm_title(text):
    x=unicodedata.normalize("NFKD",str(text or "")).casefold()
    x="".join(c for c in x if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+"," ",x).split())

def identity(url,title):
    u=urllib.parse.urlsplit(url or "")
    if u.scheme not in ("http","https") or not u.hostname:
        raise ValueError("Job has missing/invalid public URL")
    host=u.hostname.lower()
    path=urllib.parse.unquote(u.path).rstrip("/")
    if host=="jobs.smartrecruiters.com":
        m=re.fullmatch(r"/([^/]+)/(\d{9,})(?:-[^/]*)?",path,re.I)
        if m:
            return "smartrecruiters:"+m.group(1).casefold()+":"+m.group(2)
    if re.search(r"/(?:jobs|career|careers|positions|vacancies|open-roles)/[^/]{5,}$",path,re.I):
        # Specific employer posting URL; punctuation in the presentation title
        # does NOT make it a distinct vacancy.
        return "joburl:"+host+":"+path.casefold()
    params=urllib.parse.parse_qs(u.query)
    for k in ("gh_jid","jobId","job_id","jid"):
        if k in params and params[k]:
            return "jobid:"+host+":"+k+":"+params[k][0]
    if not norm_title(title):
        raise ValueError("Generic careers page without title")
    # Inline career cards can legitimately share one URL; separate by title.
    return "inline:"+host+":"+path.casefold()+":"+norm_title(title)

def assess(old,live):
    previous={s["source_id"]:s for s in old["sources"]}
    current={s["source_id"]:s for s in live["sources"]}
    if len(previous)!=18 or len(current)!=18 or set(previous)!=set(current):
        raise ValueError("Expected exactly 18 unique source IDs")
    rows=[]
    for sid in sorted(previous):
        a,b=previous[sid],current[sid]
        info={"source_id":sid,"live_state":b.get("state"),
              "old_count":a.get("relevant_leads"),"live_count":b.get("title_matches")}
        if b.get("state")!="listing_extracted" or b.get("complete") is not True:
            info.update(status="blocked_unverified",error=b.get("error","incomplete listing"))
            rows.append(info);continue
        old_roles=a["audited"];new_roles=b["records"]
        before={identity(x["url"],x["title"]):x for x in old_roles}
        now={identity(x["url"],x["title"]):x for x in new_roles}
        if len(before)!=len(old_roles) or len(now)!=len(new_roles):
            info.update(status="blocked_unverified",error="Duplicate ATS job IDs / generic inline roles")
            rows.append(info);continue
        additions=sorted(set(now)-set(before))
        removals=sorted(set(before)-set(now))
        changed_titles=[]
        changed_dates=[]
        for key in set(now)&set(before):
            p,q=before[key],now[key]
            if norm_title(p["title"])!=norm_title(q["title"]):
                changed_titles.append({"id":key,"old":p["title"],"live":q["title"]})
            old_date=(p.get("evaluation") or {}).get("original_posting_date")
            new_date=q.get("date")
            if old_date and new_date and old_date!=new_date:
                changed_dates.append({"id":key,"title":q["title"],"old":old_date,"live":new_date,
                                      "field":q.get("date_field")})
        info.update(status="needs_detail_recheck" if additions or removals or changed_titles or changed_dates else "unchanged",
            new_count=len(additions),missing_count=len(removals),
            changed_title_count=len(changed_titles),changed_date_count=len(changed_dates),
            new=[now[k] for k in additions[:30]],missing=[before[k]["title"] for k in removals[:30]],
            title_changes=changed_titles[:20],date_changes=changed_dates[:20])
        rows.append(info)
    return {"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope":"New live employer GET versus prior fully audited job identities, not a second verification of applications.",
        "summary":{"sources":18,**dict(Counter(x["status"] for x in rows)),
            "new_job_identities":sum(x.get("new_count",0) for x in rows),
            "disappeared_job_identities":sum(x.get("missing_count",0) for x in rows),
            "title_changes":sum(x.get("changed_title_count",0) for x in rows),
            "date_field_changes":sum(x.get("changed_date_count",0) for x in rows)},
        "sources":rows,"warning":"Never treat an unverified new job listing as a fresh confirmed application."}

def tests():
    left=identity("https://jobs.smartrecruiters.com/Wise/744000159666623-kyc-operations-analyst","KYC Operations Analyst")
    right=identity("https://jobs.smartrecruiters.com/Wise/744000159666623","KYC Operations Analyst")
    assert left==right
    a=identity("https://www.bnf.bank/careers/open-roles/investigations-sanctions-fraud-manager",
               "Investigations, Sanctions & Fraud Manager")
    b=identity("https://www.bnf.bank/careers/open-roles/investigations-sanctions-fraud-manager",
               "Investigations Sanctions Fraud Manager")
    assert a==b
    assert identity("https://www.demivolt.com/careers","AML Officer")!=identity(
        "https://www.demivolt.com/careers","KYC Analyst")
    assert norm_title("Administrative Officer – Screening Helpdesk")==norm_title(
        "Administrative Officer Screening Helpdesk")
    print("LIVE18_STABLE_JOB_ID_TESTS_PASSED",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--baseline",required=True)
    p.add_argument("--out",default="live18_reconciled_delta.json")
    p.add_argument("--self-test",action="store_true")
    p.add_argument("live_reports",nargs="*")
    args=p.parse_args()
    tests()
    if args.self_test:return
    if len(args.live_reports)!=3:raise SystemExit("Exactly three shard reports expected")
    a=json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    sources=[]
    for path in args.live_reports:
        d=json.loads(Path(path).read_text(encoding="utf-8"))
        if d["configured_sources"]!=339 or len(d["sources"])!=6:
            raise ValueError("Unexpected live HTTP evidence")
        sources+=d["sources"]
    report=assess(a,{"sources":sources})
    Path(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LIVE18_RECONCILED_FINAL",json.dumps({
        "summary":report["summary"],
        "changed":[x for x in report["sources"] if x["status"]!="unchanged"]},
        ensure_ascii=False),flush=True)

if __name__=="__main__":main()
