#!/usr/bin/env python3
"""Two audited official ATS sources from the 100-entity regulator research queue.

An isolated live audit MUST verify full source positive controls and every
geographically plausible AML job detail, with an official application URL.
Failed/partial sources cannot publish and never close previously seen roles.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qs
from urllib.request import Request, urlopen
from pathlib import Path
from amlradar.sources import Board
from quality_audit import candidate

from live_e2e18_full import audit_one
from live_reg100_pilot import SOURCES as RESEARCH_SOURCES

# No broader 7-source promotion: 3 failed and 2 only returned a single page
# even though their employer career sites expose more jobs. Only these two
# passed source-specific listing positive controls on a real Github runner.
LIVE_SOURCE_MINIMUM = {
    "reg100-be-paynovate": None,  # current public listing identities, not a fixed count
    "reg100-lu-pingpong-europe-s-a": 4,
}

PAYNOVATE_URL = "https://paynovate.breezy.hr/"
PAYNOVATE_PATH = re.compile(r"^/p/[a-z0-9-]+/?$")
class PaynovateLinks(HTMLParser):
    """Independent public HTML link extraction, not the Board parser."""
    def __init__(self):
        super().__init__()
        self.links={}
        self.controls=[]
        self.pagination=[]
        self.observed=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ("a","button","link"):
            u=urlsplit(urljoin(PAYNOVATE_URL,a.get("href") or ""))
            if "next" in (a.get("rel") or "").lower().split() or (
                u.hostname=="paynovate.breezy.hr" and any(k.lower() in ("page","offset","cursor") for k in parse_qs(u.query))):
                self.pagination.append({"tag":tag,"path":u.path,"reason":"pagination href or rel"})
            if tag=="a" and u.hostname=="paynovate.breezy.hr" and "/p/" in u.path:
                self.observed.append(u.path)
            if tag in ("a","button"):
                self.controls.append((tag,u,[]))
    def handle_data(self,data):
        for c in self.controls:c[2].append(data)
    def handle_endtag(self,tag):
        if tag not in ("a","button"):return
        for i in range(len(self.controls)-1,-1,-1):
            if self.controls[i][0]==tag:break
        else:return
        _,u,parts=self.controls.pop(i)
        label=" ".join(" ".join(parts).split())
        if re.fullmatch(r"(?:next(?: page)?|(?:load|show|view) more(?: jobs| positions)?)",label,re.I):
            self.pagination.append({"tag":tag,"path":u.path,"label":label})
        if tag=="a" and u.scheme=="https" and u.netloc=="paynovate.breezy.hr" and PAYNOVATE_PATH.fullmatch(u.path):
            self.links.setdefault(u.path.rstrip("/"),[]).append(label)

def paynovate_expected(html):
    p=PaynovateLinks();p.feed(html);p.close()
    if not p.links or p.pagination:
        print("PAYNOVATE_PUBLIC_SHAPE",json.dumps({"matched_paths":sorted(p.links),"observed_job_paths":p.observed[:25],"pagination_controls":p.pagination[:15]}),flush=True)
        raise ValueError("Paynovate public listing empty or pagination not accounted for")
    if any(not any(t and t.lower() not in ("apply","apply now","%button_apply%") for t in labels) for labels in p.links.values()):
        raise ValueError("Paynovate public listing missing independent job titles")
    return p.links

def paynovate_compare(expected,jobs):
    actual={}
    for job in jobs:
        u=urlsplit(str(job.get("url","")))
        if u.scheme!="https" or u.netloc!="paynovate.breezy.hr" or not PAYNOVATE_PATH.fullmatch(u.path):
            raise ValueError("Paynovate invalid listing identity")
        key=u.path.rstrip("/")
        if key in actual:raise ValueError("Paynovate duplicate listing identity")
        actual[key]=job
    if set(expected)!=set(actual):
        raise ValueError("Paynovate official and extracted job identities differ")
    for key,labels in expected.items():
        if any(candidate({"title":t}) for t in labels) and not candidate(actual[key]):
            raise ValueError("Paynovate original title selector missed an official candidate")
    return sorted(actual)

def paynovate_self_test():
    html='<a href="/p/abc-aml-analyst">AML Analyst</a><a href="/p/abc-aml-analyst">Apply</a><a href="/p/def-engineer">Engineer</a>'
    exp=paynovate_expected(html)
    jobs=[{"url":PAYNOVATE_URL+"p/abc-aml-analyst","title":"AML Analyst"},{"url":PAYNOVATE_URL+"p/def-engineer","title":"Engineer"}]
    assert len(paynovate_compare(exp,jobs))==2
    for bad in (jobs[:1],jobs+[jobs[0]], [dict(jobs[0],title="Engineer"),jobs[1]]):
        try:paynovate_compare(exp,bad)
        except ValueError:pass
        else:raise AssertionError("Incomplete or mismatched Paynovate evidence passed")
    for bad_html in ("<h1>Access denied</h1>",html+'<a href="?page=2">Next</a>'):
        try:paynovate_expected(bad_html)
        except ValueError:pass
        else:raise AssertionError("Empty/paginated evidence passed")

def audit_paynovate(config,minutes):
    paynovate_self_test()
    assert config["careers_url"]==PAYNOVATE_URL
    original=Board.listing
    identities=[]
    def checked(board):
        # The HTTP guard wraps this independent read as well as the original parser.
        with urlopen(Request(PAYNOVATE_URL,headers={"User-Agent":"AML339-source-audit/1.0"}),timeout=15) as response:
            if response.geturl().rstrip("/")!=PAYNOVATE_URL.rstrip("/"):raise ValueError("Paynovate unexpected listing redirect")
            body=response.read(1500001)
            if len(body)>1500000:raise ValueError("Paynovate listing evidence truncated")
        expected=paynovate_expected(body.decode("utf-8","replace"))
        jobs=original(board)
        identities.extend(paynovate_compare(expected,jobs))
        return jobs
    Board.listing=checked
    try:result=audit_one(config,minutes=minutes)
    finally:Board.listing=original
    n=result.get("total_listed")
    result["independent_listing_paths"]=identities
    if (type(n) is not int or n<=0 or len(identities)!=n
        or len(result.get("listing_role_keys",[]))!=n
        or result.get("listing_untrackable_count")!=0):
        result.update(state="listing_failed",list_complete=False)
        result.setdefault("errors",[]).append("Paynovate complete current unique identity evidence missing")
    print("PAYNOVATE_COVERAGE",json.dumps({"listed":n,"official_paths":identities,"complete":result.get("list_complete")}),flush=True)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True,choices=tuple(LIVE_SOURCE_MINIMUM))
    parser.add_argument("--out",required=True)
    parser.add_argument("--minutes",type=int,default=4)
    args=parser.parse_args()
    if not 1<=args.minutes<=5:raise SystemExit("Invalid bounded source budget")
    original=json.loads(Path("experiments/aml339/regulator100_discovery_queue.json").read_text(encoding="utf-8"))
    ids={row["id"] for row in original["candidates"]}
    if original["count"]!=100 or len(ids)!=100 or args.source not in ids:
        raise ValueError("Not a known legal entity of regulator100 discovery")
    config=RESEARCH_SOURCES[args.source]
    result=(audit_paynovate(config,args.minutes) if args.source=="reg100-be-paynovate"
            else audit_one(config,minutes=args.minutes))
    min_count=LIVE_SOURCE_MINIMUM[args.source]
    if min_count is not None and result.get("state")=="listing_extracted" and result.get("list_complete") is True:
        if not isinstance(result.get("total_listed"),int) or result["total_listed"]<min_count:
            result["state"]="listing_failed"
            result["list_complete"]=False
            result.setdefault("errors",[]).append(
                f"Official listing incomplete relative to confirmed baseline of {min_count} jobs")
    if result.get("unverified_in_scope",0):
        result["state"]="listing_failed"
        result["list_complete"]=False
        result.setdefault("errors",[]).append("Official in-scope job detail/application failed")
    result["employer_legal_entity_discovery_id"]=args.source
    report={
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "source_registry":"regulated_emi_reg100_live_v1",
        "original_catalog_sources":339,
        "total_configured_sources":339,
        "sources_requested":[args.source],
        "sources":[result],
    }
    Path(args.out).write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("REG100_PRODUCTION_ELIGIBLE",json.dumps({
       "id":args.source,"complete":result["list_complete"],
       "total_listed":result["total_listed"],
       "relevant":result["relevant_leads"],
       "audited":len(result["audited"]),
       "errors":result.get("errors",[]),
       "unverified_in_scope":result["unverified_in_scope"]
    },ensure_ascii=False),flush=True)
    if result["state"]!="listing_extracted" or result["list_complete"] is not True:
        raise SystemExit("Fail-closed source audit: "+args.source)

if __name__=="__main__":
    main()
