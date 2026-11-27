#!/usr/bin/env python3
"""Read-only public Flatchr coverage and application-control diagnostic."""
import argparse, datetime as dt, json, re, time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from hourly_http_guard import load, save, parse_time, until_from
HOST="careers.aoshearman.com"
ROOT="https://"+HOST+"/en/search-jobs"
PATTERN=re.compile(r"^/en/job/[^/]+/[^/]+/\d+/(\d+)/?$")
TITLE=re.compile(r"\b(?:AML|KYC|compliance|conformit[eé]|risk|risques?|r[eé]glementaire|regulatory|financial crime|due diligence|screening)\b",re.I)
MORE=re.compile(r"^(?:see|show|load|view) more offers$|^next(?: page)?$",re.I)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prior",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    prior=load(a.prior);new={};save(a.receipt,new)
    result={"id":"external-ao-shearman","verified":False,"status":"DIAGNOSTIC_ONLY","listed":0,"audited":[],"errors":[]}
    def paused(host):
        return any(host in d and parse_time(d[host]["until"])>dt.datetime.now(dt.timezone.utc) for d in (prior,new))
    if paused(HOST):
        result["status"]="HELD"
        result["errors"].append("Provider cooldown active")
    else:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            ctx=browser.new_context(service_workers="block")
            stopped=[];requests=[0];deadline=time.monotonic()+240
            def route(r):
                u=urlsplit(r.request.url)
                requests[0]+=1
                if stopped or paused(u.hostname) or requests[0]>1800 or time.monotonic()>deadline or r.request.method not in ("GET","HEAD") or r.request.resource_type in ("image","media","font") or (r.request.is_navigation_request() and u.hostname!=HOST):
                    r.abort()
                else:r.continue_()
            def response(r):
                h=urlsplit(r.url).hostname
                if r.status==429 or (r.status==503 and r.headers.get("retry-after")):
                    new[h]={"until":until_from({"Retry-After":r.headers.get("retry-after")},dt.datetime.now(dt.timezone.utc)).isoformat(),"status":r.status}
                    save(a.receipt,new);stopped.append("Provider cooldown")
                elif r.status in (401,403) and h==HOST and r.request.resource_type in ("document","xhr","fetch"):
                    stopped.append("Access restriction")
            ctx.route("**/*",route);ctx.on("response",response)
            page=ctx.new_page();page.set_default_timeout(10000)
            def check():
                if stopped:raise RuntimeError(stopped[0])
                if requests[0]>1800 or time.monotonic()>deadline:raise RuntimeError("Read budget exceeded")
            def snapshot():
                check()
                rows={}
                pairs=page.locator("a[href]").evaluate_all("""els => els.filter(e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden').map(e=>({url:e.href,title:e.innerText.trim()}))""")
                for x in pairs:
                    u=urlsplit(x["url"]);m=PATTERN.fullmatch(u.path)
                    if u.scheme=="https" and u.netloc==HOST and m and x["title"]:
                        k=m[1]
                        if k in rows and rows[k]["url"]!=x["url"]:raise ValueError("Ambiguous job identity")
                        rows[k]=x
                return rows
            try:
                response=page.goto(ROOT,wait_until="domcontentloaded")
                if not response or response.status!=200:raise ValueError("Board response not successful")
                page.wait_for_timeout(1200)
                def declared():
                    h=page.get_by_role("heading",name=re.compile(r"^[\d,]+ jobs found$",re.I))
                    values={int(re.search(r"[\d,]+",x).group().replace(",","")) for x in h.all_inner_texts()}
                    if len(values)!=1:raise ValueError("Ambiguous official total")
                    return values.pop()
                total=declared()
                if not 0<total<=500:raise ValueError("Outside bounded inventory")
                all_rows=snapshot();result["declared"]=total;result["steps"]=[len(all_rows)]
                for _ in range(35):
                    check()
                    if len(all_rows)==total:break
                    more=page.get_by_role("button",name=re.compile(r"^View More Jobs$",re.I))
                    controls=[x for x in more.all() if x.is_visible() and x.is_enabled()]
                    if len(controls)!=1:raise ValueError("No unique enabled public jobs pagination control")
                    before=len(all_rows);controls[0].click();page.wait_for_timeout(1000)
                    check()
                    if declared()!=total:raise ValueError("Official count changed mid-scan")
                    current=snapshot()
                    all_rows.update(current)
                    result["steps"].append(len(all_rows))
                    if len(all_rows)<=before or len(all_rows)>total:raise ValueError("Pagination did not establish new distinct identities")
                if len(all_rows)!=total:raise ValueError("Incomplete listing")
                result["listed"]=len(all_rows);result["listing_ids"]=sorted(all_rows)
                result["aml_titles"]=[r for r in all_rows.values() if TITLE.search(r["title"])]
                result["status"]="LISTING_COVERAGE_REVIEW_REQUIRED"
            except Exception as exc:
                result["status"]="HELD" if stopped else "DIAGNOSTIC_INCOMPLETE"
                result["errors"].append(type(exc).__name__+": "+str(exc)[:240])
            finally:
                browser.close()
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("AO_COVERAGE_EVIDENCE",json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
