#!/usr/bin/env python3
"""Reviewed regulated employers: direct public ATS audit, exact independent listing IDs.
No application submission, access-control bypass or publication."""
import argparse,datetime as dt,json,re
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from live_external50_wave02 import Anchors,read_page,candidate
from live_e2e18_full import audit_one
import live_e2e18_full as audit
from amlradar.sources import Board
from live_external_generic import audit_config

SOURCES={
 "reg100-fr-bcb-payments-europe":{"name":"BCB Payments Europe / BCB Group","careers_url":"https://job-boards.eu.greenhouse.io/bcbgroup","route":["greenhouse","boards-api.eu.greenhouse.io","bcbgroup"],"job_pattern":r"^/bcbgroup/jobs/([0-9]+)/?$","aliases":["bcbgroup","bcb group"],"regulatory_reference":"https://www.lb.lt/en/sfi-financial-market-participants/bcb-payments-europe-sasu"},
 "reg100-es-currencies-direct-spain-ede-s-l":{"name":"Currencies Direct Spain","careers_url":"https://job-boards.eu.greenhouse.io/currenciesdirectlimited","route":["greenhouse","boards-api.eu.greenhouse.io","currenciesdirectlimited"],"job_pattern":r"^/currenciesdirectlimited/jobs/([0-9]+)/?$","aliases":["currencies direct","currenciesdirect","redpin"],"regulatory_reference":"https://www.currenciesdirect.com/en-es/company"},
 "reg100-lt-sezzle-lithuania-uab":{"name":"Sezzle Lithuania","careers_url":"https://job-boards.greenhouse.io/sezzle","route":["greenhouse","boards-api.greenhouse.io","sezzle"],"job_pattern":r"^/sezzle/jobs/([0-9]+)/?$","aliases":["sezzle"],"regulatory_reference":"https://www.lb.lt/en/news/two-electronic-money-institution-licences-issued-1","licence_current_review":True},
 "reg100-lv-sia-xpate":{"name":"xpate","careers_url":"https://xpate.jobs.personio.com/?language=en","route":["personio","xpate.jobs.personio.com",""],"job_pattern":r"^/job/([0-9]+)/?$","aliases":["xpate"],"regulatory_reference":"https://www.lb.lt/en/sfi-financial-market-participants/sia-xpate"},
 "external-monese-group":{"name":"Monese / Pockit","careers_url":"https://careers.monese.com/jobs","route":["teamtailor","careers.monese.com","/jobs"],"job_pattern":r"^/jobs/[0-9]+-[^/]+/?$","aliases":["monese","pockit"],"licence_current_review":True},
 "external-terrapay-group":{"name":"TerraPay","careers_url":"https://jobs.terrapay.com/","route":["site_jobs","jobs.terrapay.com",r"^/_/j/[A-Z0-9]+/?$"],"job_pattern":r"^/_/j/[A-Z0-9]+/?$","aliases":["terrapay","terra payment services"],"licence_current_review":True},
}
def same_identity(row):
    """Do not label an original-catalog employer as a genuinely new external source."""
    original=json.loads(Path("fuentes.json").read_text())["sources"]
    matches=[]
    for old in original:
        label=" ".join(str(old.get(k,"")).lower() for k in ("id","name","careers_url"))
        if any(re.search(r"(?<![a-z0-9])"+re.escape(a)+r"(?![a-z0-9])",label) for a in row["aliases"]) or old.get("route")==row["route"]:
            matches.append(old["id"])
    return matches
def audit_provider(row):
    if row["route"][0] in ("site_jobs","teamtailor"):
        return audit_config(row)
    url=row["careers_url"]; host=urlsplit(url).hostname
    rx=re.compile(row["job_pattern"])
    page=Anchors(); page.feed(read_page(url))
    def key(href):
        u=urlsplit(urljoin(url,href))
        # Greenhouse's US and EU public board links can redirect to each other.
        allowed={host}
        if row["route"][0]=="greenhouse":
            allowed.update({"job-boards.greenhouse.io","job-boards.eu.greenhouse.io","boards.greenhouse.io","boards.eu.greenhouse.io"})
        m=rx.fullmatch(u.path)
        return m[1] if u.scheme=="https" and u.hostname in allowed and m else None
    expected={key(h):title for h,title in page.links.items() if key(h) and title}
    if not expected:raise ValueError("No independent positive job-link proof")
    original=Board.listing;old=audit.candidate
    def checked(board):
        jobs=original(board)
        by={key(str(j.get("url",""))):j for j in jobs}
        if None in by or len(by)!=len(jobs) or set(expected)!=set(by):raise ValueError("Public ATS and visible board job identities disagree")
        for k,title in expected.items():
            if candidate({"title":title}) and not candidate(by[k]):by[k]["title"]=title
        return jobs
    Board.listing=checked;audit.candidate=candidate
    try:r=audit_one(row,minutes=4)
    finally:Board.listing=original;audit.candidate=old
    ok=(r.get("state")=="listing_extracted" and r.get("list_complete") is True and r.get("total_listed")==len(expected) and r.get("relevant_leads")==len(r.get("audited",[])) and r.get("unverified_in_scope")==0 and r.get("listing_untrackable_count")==0)
    if not ok:r.update(state="listing_failed",list_complete=False)
    return r,ok
def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True,choices=SOURCES);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    row=dict(SOURCES[a.source],id=a.source)
    result={"id":a.source,"verified":False,"config":row}
    try:
        duplicates=same_identity(row);result["original_catalog_matches"]=duplicates
        if duplicates:result["status"]="ORIGINAL_CATALOG_ALIAS_REVIEW"
        else:
            r,ok=audit_provider(row);result.update(verified=ok,audit=r,status="VERIFIED_PENDING_REGULATORY_AND_GROUP_REVIEW" if ok else "FAILED")
    except Exception as e:result.update(status="FAILED",error=type(e).__name__+": "+str(e)[:300])
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("REVIEWED_EXTERNAL_ATS",json.dumps({k:v for k,v in result.items() if k not in ("config","audit")}|{"listed":result.get("audit",{}).get("total_listed"),"errors":result.get("audit",{}).get("errors",[])}),flush=True)
if __name__=="__main__":main()
