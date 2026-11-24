#!/usr/bin/env python3
"""Find official recruitment links and audit supported ATS tenants without guessing.
All candidates require regulatory and employer-identity review before live enrollment."""
import argparse,json,re
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from growth_discovery import anchors,get,hostkey,blocked,REGULATORS,safe_url
from live_external_generic import audit_config
from live_e2e18_full import audit_one
from live_external50_wave02 import candidate
from amlradar.sources import Board
import live_e2e18_full as audit

def provider(url):
    u=urlsplit(url);h=u.hostname or "";path=u.path.rstrip("/")
    if u.scheme!="https" or blocked(h):return None
    m=re.match(r"^/([a-zA-Z0-9_-]+)(?:/jobs(?:/|$)|$)",path)
    if h in ("job-boards.greenhouse.io","boards.greenhouse.io","job-boards.eu.greenhouse.io","boards.eu.greenhouse.io") and m:
        tenant=m[1];return (f"https://{h}/{tenant}",["greenhouse","boards-api.greenhouse.io",tenant],r"^/"+re.escape(tenant)+r"/jobs/([0-9]+)/?$")
    if h.endswith(".jobs.personio.com") or h.endswith(".jobs.personio.de"):
        return (f"https://{h}/",["personio",h,""],r"^/job/([0-9]+)/?$")
    if h.endswith(".teamtailor.com") or (h.startswith("careers.") and re.match(r"^/jobs(?:/|$)",path)):
        return (f"https://{h}/jobs",["teamtailor",h,"/jobs"],r"^/jobs/[0-9]+-[^/]+/?$")
    m=re.match(r"^/companies/([a-zA-Z0-9-]+)(?:/|$)",path)
    if h=="join.com" and m:
        base="/companies/"+m[1];return (f"https://{h}{base}",["site_jobs",h,"^"+re.escape(base)+r"/[0-9]+-[^/]+/?$"],"^"+re.escape(base)+r"/[0-9]+-[^/]+/?$")
    # Other ATS are retained as evidence, not guessed or accepted.
    return None
def website_from_profile(url):
    if urlsplit(url).hostname not in REGULATORS:raise ValueError("Non-authority profile")
    candidates=set()
    for u,t in anchors(url,get(url)):
        if urlsplit(u).scheme!="https" or hostkey(u) in {h.removeprefix("www.") for h in REGULATORS} or blocked(hostkey(u)):continue
        # Only links whose displayed label is a website or the URL itself.
        label=t.strip().casefold().rstrip("/")
        hostname=hostkey(u)
        if label in ("website","web site","internet website","webpage","www","internet address") or label.removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]==hostname:
            if len(hostname.split("."))>=2:candidates.add(u)
    if len(candidates)==1:return next(iter(candidates))
    return None
def find_careers(site):
    options=[]
    for u,t in anchors(site,get(site)):
        if urlsplit(u).scheme!="https" or blocked(hostkey(u)):continue
        if provider(u) or (hostkey(u)==hostkey(site) and re.search(r"\b(careers?|jobs?|vacancies|join us|work with us|trabaja con nosotros|karjera|karriere)\b",t,re.I)):
            options.append(u)
    choices=sorted(set(options))
    if len(choices)==1:return choices[0]
    direct={provider(x)[0] for x in choices if provider(x)}
    if len(direct)==1:return next(iter(direct))
    # Multiple boards/regions may be different legal employers; don't pick blindly.
    return None
def check_provider(row):
    route=row["route"];url=row["careers_url"];rx=re.compile(row["job_pattern"]);host=urlsplit(url).hostname
    if route[0] in ("site_jobs","teamtailor"):return audit_config(row)
    def key(href):
        u=urlsplit(urljoin(url,href));m=rx.fullmatch(u.path)
        allowed={host}
        if route[0]=="greenhouse":allowed.update({"job-boards.greenhouse.io","boards.greenhouse.io","job-boards.eu.greenhouse.io","boards.eu.greenhouse.io"})
        return m[1] if u.scheme=="https" and u.hostname in allowed and m else None
    expected={key(h):t for h,t in anchors(url,get(url)) if key(h) and t}
    if not expected:raise ValueError("No independent positive job IDs")
    old=Board.listing;old_candidate=audit.candidate
    def listing(board):
        jobs=old(board)
        actual={key(str(j.get("url",""))):j for j in jobs}
        if None in actual or len(actual)!=len(jobs) or set(actual)!=set(expected):raise ValueError("ATS listing differs from visible official job IDs")
        for k,t in expected.items():
            if candidate({"title":t}) and not candidate(actual[k]):actual[k]["title"]=t
        return jobs
    Board.listing=listing;audit.candidate=candidate
    try:r=audit_one(row,minutes=3)
    finally:Board.listing=old;audit.candidate=old_candidate
    ok=(r.get("state")=="listing_extracted" and r.get("list_complete") is True and r.get("total_listed")==len(expected) and r.get("relevant_leads")==len(r.get("audited",[])) and r.get("unverified_in_scope")==0 and r.get("listing_untrackable_count")==0)
    return r,ok
def inspect(row):
    out={"id":row["id"],"key":row["key"],"name":row["name"],"country":row["country"],"profile":row.get("profile"),"status":"NO_CONFIRMED_CAREERS","verified":False}
    try:
        site=row.get("company_site");career=row.get("careers_url")
        if not career and not site and row.get("profile"):site=website_from_profile(row["profile"])
        if not career and site:career=find_careers(site)
        out.update(company_site=site,careers_url=career)
        if not career:return out
        safe_url(career)
        cfg=provider(career)
        if not cfg:
            links=anchors(career,get(career))
            providers={provider(u)[0]:provider(u) for u,t in links if provider(u)}
            out["linked_ats"]=sorted(providers)
            if len(providers)==1:cfg=next(iter(providers.values()))
            elif len(providers)>1:out["status"]="MULTIPLE_ATS_REVIEW_REQUIRED";return out
            else:
                out["status"]="PORTAL_NEEDS_ADAPTER"
                out["job_link_examples"]=[u for u,t in links if re.search(r"job|career|vacanc|position",u,re.I)][:12]
                return out
        url,route,pattern=cfg
        safe_url(url)
        config={"id":row["id"],"name":row["name"],"careers_url":url,"route":route,"job_pattern":pattern}
        out["config"]=config
        r,ok=check_provider(config)
        out.update(verified=ok,status="TECHNICAL_PASS_REVIEW_REQUIRED" if ok else "INCOMPLETE_AUDIT",listed=r.get("total_listed"),matched=r.get("relevant_leads"),unverified=r.get("unverified_in_scope"),errors=r.get("errors",[])[:3])
    except Exception as e:out.update(status="ERROR_OR_UNSUPPORTED",error=type(e).__name__+": "+str(e)[:220])
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument("--selection",type=Path,required=True);p.add_argument("--key",required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    row=next(x for x in json.loads(a.selection.read_text())["selected"] if x["key"]==a.key)
    result=inspect(row)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("GROWTH_RESULT",json.dumps({k:v for k,v in result.items() if k!="config"},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
