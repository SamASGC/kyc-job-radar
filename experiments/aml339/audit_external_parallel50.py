#!/usr/bin/env python3
"""Sharded 50-candidate audit. Every row gets a disposition, never a fake zero."""
import argparse,json,re
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from live_external50_wave02 import Anchors,read_page
from live_external_generic import audit_config

# Each path pattern is deliberately narrow. ATS tenants must be linked by
# the employer; no guessing provider slugs, no scraping blocked providers.
BLOCKED=("workable.com","sage.hr","linkedin.com")
def blocked(host):
    return any(host==x or host.endswith("."+x) for x in BLOCKED)
def links(url):
    p=Anchors();p.feed(read_page(url))
    return [(urljoin(url,h),t) for h,t in p.links.items() if h and urlsplit(urljoin(url,h)).scheme=="https"]
def route_pattern(url):
    u=urlsplit(url);h=u.hostname or "";p=u.path.rstrip("/")
    if h.endswith(".bamboohr.com"):
        return r"^/careers/[0-9]+/?$"
    if h.endswith(".recruitee.com"):
        return r"^/o/[a-zA-Z0-9-]+/?$"
    if h.endswith(".jobs.personio.com") or h.endswith(".jobs.personio.de"):
        return r"^/job/[0-9]+/?$"
    if h=="join.com" and re.fullmatch(r"/companies/[a-zA-Z0-9-]+",p):
        return "^"+re.escape(p)+r"/[0-9]+-[^/]+/?$"
    if h=="app.screenloop.com" and re.fullmatch(r"/careers/[a-zA-Z0-9-]+",p):
        return "^"+re.escape(p)+r"/job_posts/[0-9]+/?$"
    if h in ("job-boards.greenhouse.io","boards.greenhouse.io") and re.fullmatch(r"/[a-zA-Z0-9-]+",p):
        return "^"+re.escape(p)+r"/jobs/[0-9]+/?$"
    if h.startswith("careers.") or h.endswith(".teamtailor.com"):
        return r"^/jobs/[0-9]+-[^/]+/?$"
    if h=="ats.rippling.com" and re.fullmatch(r"/[a-zA-Z0-9-]+/jobs",p):
        return "^"+re.escape(p)+r"/[0-9a-f-]{36}/?$"
    # Own employer page: concrete job paths, not generic /careers links.
    return r"^/(?:[a-z]{2}/)?(?:careers|jobs|vacancies)/(?:jobs/)?(?:[0-9]+(?:-[^/]+)?|[0-9a-f-]{36})/?$"

def provider_board(url):
    u=urlsplit(url);h=u.hostname or "";p=u.path.rstrip("/")
    if blocked(h):return None
    if h.endswith(".bamboohr.com") and re.match(r"^/careers(?:/|$)",p):return f"https://{h}/careers"
    if h.endswith(".recruitee.com"):return f"https://{h}/"
    if h.endswith(".jobs.personio.com") or h.endswith(".jobs.personio.de"):return f"https://{h}/"
    m=re.match(r"^/companies/([a-zA-Z0-9-]+)(?:/|$)",p)
    if h=="join.com" and m:return f"https://{h}/companies/{m[1]}"
    m=re.match(r"^/careers/([a-zA-Z0-9-]+)(?:/|$)",p)
    if h=="app.screenloop.com" and m:return f"https://{h}/careers/{m[1]}"
    m=re.match(r"^/([a-zA-Z0-9-]+)(?:/jobs(?:/|$)|$)",p)
    if h in ("job-boards.greenhouse.io","boards.greenhouse.io") and m:return f"https://{h}/{m[1]}"
    if h.endswith(".teamtailor.com"):return f"https://{h}/jobs"
    m=re.match(r"^/([a-zA-Z0-9-]+)/jobs(?:/|$)",p)
    if h=="ats.rippling.com" and m:return f"https://{h}/{m[1]}/jobs"
    return None

def inspect(row):
    sid=row["id"];url=row.get("careers_url")
    out={"id":sid,"name":row["name"],"careers_url":url,"status":"NO_OFFICIAL_PORTAL_LOCATED","verified":False}
    if not url:return out
    if blocked(urlsplit(url).hostname or ""):return dict(out,status="BLOCKED_PROVIDER_NOT_QUERIED")
    try:
        anchors=links(url)
        h=urlsplit(url).hostname
        out["career_links"]=[{"url":u,"title":t[:160]} for u,t in anchors if re.search(r"/(?:career|job|vacanc|openings)|\b(?:AML|compliance|screening|fraud)\b",u+" "+t,re.I)][:40]
        possible=sorted({v for u,t in anchors if (v:=provider_board(u))})
        # Employer-owned /jobs page or explicit ATS board proven by actual anchors.
        if provider_board(url):possible.insert(0,provider_board(url))
        if len(set(possible))>1:return dict(out,status="MULTIPLE_ATS_TENANTS_NEED_REVIEW",ats_candidates=possible)
        board=possible[0] if possible else url
        pattern=route_pattern(board)
        bh=urlsplit(board).hostname
        current=anchors if board==url else links(board)
        matched=[(u,t) for u,t in current if urlsplit(u).hostname==bh and re.fullmatch(pattern,urlsplit(u).path) and t]
        if not matched:
            return dict(out,status="PORTAL_REACHED_NEEDS_ADAPTER_OR_EMPTY_PROOF",ats_candidates=possible,linked_job_count=0)
        route=["teamtailor",bh,""] if bh.endswith(".teamtailor.com") else ["site_jobs",bh,pattern]
        cfg={"id":sid,"name":row["name"],"careers_url":board,"route":route,"job_pattern":pattern}
        result,ok=audit_config(cfg)
        out.update(status="SOURCE_AUDIT_PASSED_PENDING_IDENTITY_AND_LICENCE_REVIEW" if ok else "SOURCE_AUDIT_FAILED",verified=ok,linked_job_count=len(matched),config=cfg,audit=result)
    except Exception as e:
        out.update(status="PORTAL_OR_DETAIL_ERROR",error=type(e).__name__+": "+str(e)[:250])
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument("--shard",type=int,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--batch",type=Path,default=Path("experiments/aml339/external_parallel_batch01.json"))
    a=p.parse_args()
    data=json.loads(a.batch.read_text());rows=data["candidates"]
    if data["count"]!=50 or len(rows)!=50 or len({x["id"] for x in rows})!=50 or not 0<=a.shard<10:raise ValueError("Invalid exact 50-row batch")
    results=[]
    for row in rows[a.shard*5:a.shard*5+5]:
        result=inspect(row);results.append(result)
        print("BATCH50_DISPOSITION",json.dumps({k:v for k,v in result.items() if k not in ("audit","career_links","config")},ensure_ascii=False),flush=True)
        a.out.write_text(json.dumps({"shard":a.shard,"results":results},ensure_ascii=False,indent=2)+"\n")
if __name__=="__main__":main()
