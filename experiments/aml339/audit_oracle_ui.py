#!/usr/bin/env python3
"""Experimental read-only Oracle public UI reader. No enrollment or API replay."""
import argparse, datetime as dt, json, re, time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from hourly_http_guard import load, save, until_from, parse_time

SITES={
 "danske-bank":("ejqi.fa.ocs.oraclecloud.eu","CX_1001"),
 "csc":("hczw.fa.us2.oraclecloud.com","CX_1001"),
 "citco":("fa-euxc-saasfaprod1.fa.ocs.oraclecloud.com","CX_1"),
}
TITLE=re.compile(r"\b(?:aml|kyc|kyb|cdd|edd|compliance|sanctions?|financial crime|fraud|risk|due diligence|money laundering|screening|mlro|onboarding|investigations?|financial security|client acceptance|client lifecycle)\b",re.I)
TOTAL=re.compile(r"(?:Job search results\s+([\d,]+)|([\d,]+)\s+Open Jobs)",re.I)
MORE=re.compile(r"^(?:show|load|view|see) more (?:jobs|results)$|^next(?: page)?$|^show more$|^load more$",re.I)
APPLY=re.compile(r"^(?:apply now|apply for (?:this|the) job|apply|apply for this position)$",re.I)
CLOSED=re.compile(r"this job is (?:no longer available|closed|not available)|job (?:has been|is) (?:removed|closed|filled)|no longer accepting applications",re.I)
BLOCKED=re.compile(r"access denied|verify you are human|captcha|too many requests",re.I)

def declared_total(body):
    vals={int((a or b).replace(",","")) for a,b in TOTAL.findall(body)}
    if len(vals)!=1:raise ValueError("Missing or conflicting public listing count")
    return vals.pop()

def job_identity(href,host,site):
    u=urlsplit(href)
    m=re.fullmatch(r"/hcmUI/CandidateExperience/en/sites/"+re.escape(site)+r"/job/([0-9]+)/?",u.path)
    if u.scheme=="https" and u.netloc==host and m:return m[1]
    return None

def self_test():
    assert declared_total("235 Open Jobs\nJob search results 235")==235
    for bad in ("Open Jobs","0 Open Jobs\nJob search results 2"):
        try:declared_total(bad)
        except ValueError:pass
        else:raise AssertionError("Invalid total accepted")
    assert job_identity("https://example.com/hcmUI/CandidateExperience/en/sites/CX_1/job/123?utm=x","example.com","CX_1")=="123"
    assert job_identity("https://evil.com/hcmUI/CandidateExperience/en/sites/CX_1/job/123","example.com","CX_1") is None
    assert job_identity("https://example.com/hcmUI/CandidateExperience/en/sites/CX_1/job/123/apply","example.com","CX_1") is None
    assert TITLE.search("AML Officer") and not APPLY.search("Apply filters")

def run(source,prior_path,receipt):
    host,site=SITES[source]
    root=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}"
    prior=load(prior_path);new={};save(receipt,new)
    result={"id":source,"verified":False,"status":"INCOMPLETE","declared_total":None,"listed":0,"audited":[],"listing_complete":False,"errors":[]}
    deadline=time.monotonic()+240
    def paused(h):
        return any(h in d and parse_time(d[h]["until"])>dt.datetime.now(dt.timezone.utc) for d in (prior,new))
    if paused(host):
        result["errors"].append("Provider cooldown active")
        return result
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        ctx=browser.new_context(locale="en-US",service_workers="block")
        requests=0;stop=[]
        def intercept(route):
            nonlocal requests
            u=urlsplit(route.request.url);requests+=1
            if stop or paused(u.hostname) or requests>4000 or time.monotonic()>deadline:
                route.abort()
                return
            # Public page rendering only. Block nonessential assets and all methods
            # other than GET/HEAD; never submit an application, form or tracking POST.
            if route.request.method not in ("GET","HEAD") or route.request.resource_type in ("image","media","font"):
                route.abort()
                return
            if route.request.is_navigation_request() and u.hostname!=host:
                route.abort()
                return
            route.continue_()
        def response(res):
            h=urlsplit(res.url).hostname
            if res.status==429 or (res.status==503 and res.headers.get("retry-after")):
                end=until_from({"Retry-After":res.headers.get("retry-after")},dt.datetime.now(dt.timezone.utc))
                if h:
                    new[h]={"until":end.isoformat(),"status":res.status};save(receipt,new)
                stop.append("Provider cooldown: "+str(h))
            elif res.status in (401,403) and h==host and res.request.resource_type in ("document","xhr","fetch"):
                stop.append("Access restriction: "+str(res.status))
        ctx.route("**/*",intercept);ctx.on("response",response)
        page=ctx.new_page();page.set_default_timeout(12000)
        def check():
            if stop:raise RuntimeError(stop[0])
            if time.monotonic()>deadline or requests>4000:raise RuntimeError("Read budget exceeded")
        def body():
            check()
            s=page.locator("body").inner_text(timeout=12000)
            if BLOCKED.search(s):raise RuntimeError("Public page blocked")
            return s
        def links():
            entries=page.locator("a[href]").evaluate_all("""els => els.filter(e=>e.getClientRects().length).map(e=>({url:e.href,title:(e.innerText||e.getAttribute('aria-label')||'').trim()}))""")
            rows={}
            for e in entries:
                key=job_identity(e["url"],host,site)
                if key:
                    title=" ".join(e["title"].split())
                    if title:
                        if key in rows and rows[key]["title"]!=title:
                            raise ValueError("Conflicting visible job labels: "+key)
                        rows[key]={"id":key,"title":title,"url":root+"/job/"+key}
            return rows
        try:
            page.goto(root+"/jobs",wait_until="domcontentloaded")
            page.wait_for_function(r"() => /Job search results\s+\d|[\d,]+\s+Open Jobs/i.test(document.body.innerText)",timeout=25000)
            expected=declared_total(body());result["declared_total"]=expected
            if not 0<expected<=1500:raise ValueError("Public count outside positive bounded inventory")
            all_rows={}
            for step in range(80):
                check()
                if declared_total(body())!=expected:raise ValueError("Listing total changed during scan")
                old=len(all_rows)
                for k,r in links().items():
                    if k in all_rows and all_rows[k]["title"]!=r["title"]:raise ValueError("Title changed during scan")
                    all_rows[k]=r
                result["listed"]=len(all_rows)
                if len(all_rows)==expected:break
                if len(all_rows)>expected:raise ValueError("More job IDs than declared count")
                controls=page.get_by_role("button",name=MORE).or_(page.get_by_role("link",name=MORE))
                visible=[x for x in controls.all() if x.is_visible() and x.is_enabled()]
                if len(visible)>1:raise ValueError("Ambiguous pagination controls")
                if len(visible)==1:
                    visible[0].click(timeout=5000)
                else:
                    page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
                page.wait_for_timeout(1200)
                # Repeated no-progress is incomplete; never infer empty or end.
                if step>1 and len(all_rows)==old and not visible:
                    if not set(links())-set(all_rows):raise ValueError("No complete pagination evidence")
            if len(all_rows)!=expected:raise ValueError("Declared count not covered")
            result["listing_complete"]=True
            result["listing_ids"]=sorted(all_rows)
            relevant=[r for r in all_rows.values() if TITLE.search(r["title"])]
            result["relevant"]=len(relevant)
            for row in relevant:
                check();ev={**row,"verified":False}
                try:
                    page.goto(row["url"],wait_until="domcontentloaded")
                    page.wait_for_function(r"() => /Job Description|Job Info|Apply Now|no longer available/i.test(document.body.innerText)",timeout=15000)
                    s=body()
                    if job_identity(page.url,host,site)!=row["id"]:raise ValueError("Unexpected job identity")
                    if CLOSED.search(s):raise ValueError("Closed or unavailable job")
                    heads=page.get_by_role("heading").all_inner_texts()
                    if not any(row["title"].casefold() in " ".join(h.split()).casefold() for h in heads):raise ValueError("Job title not confirmed")
                    if not re.search(r"\bJob Description\b",s,re.I) or len(s)<400:raise ValueError("Missing job description")
                    apply=page.get_by_role("button",name=APPLY).or_(page.get_by_role("link",name=APPLY))
                    controls=[x for x in apply.all() if x.is_visible() and x.is_enabled()]
                    if not controls:raise ValueError("No enabled application control")
                    ev.update(verified=True,application_control_count=len(controls),description_present=True)
                except Exception as exc:
                    ev["error"]=type(exc).__name__+": "+str(exc)[:180]
                result["audited"].append(ev)
            result["unverified"]=sum(not r["verified"] for r in result["audited"])
            if result["unverified"] or len(result["audited"])!=len(relevant):raise ValueError("Relevant details incomplete")
            check()
            # This is explicitly experimental evidence, not the production verifier.
            result["status"]="UI_EVIDENCE_PASS_REVIEW_REQUIRED"
        except Exception as exc:
            result["errors"].append(type(exc).__name__+": "+str(exc)[:240])
        finally:
            result["request_count"]=requests
            if stop:result["errors"].extend(stop[:1]);result["status"]="HELD"
            browser.close()
    return result

def main():
    a=argparse.ArgumentParser();a.add_argument("--source",choices=SITES,required=True);a.add_argument("--prior",type=Path,required=True);a.add_argument("--receipt",type=Path,required=True);a.add_argument("--out",type=Path,required=True);args=a.parse_args()
    self_test()
    result=run(args.source,args.prior,args.receipt)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("ORACLE_UI_EVIDENCE",json.dumps({k:v for k,v in result.items() if k not in ("listing_ids","audited")},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
