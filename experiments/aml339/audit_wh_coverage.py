#!/usr/bin/env python3
"""Read-only public WH Partners board coverage diagnostic. Never enrolls."""
import argparse, datetime as dt, json, re
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from hourly_http_guard import load, save, parse_time, until_from
HOST="whpartners.eu"
ROOT="https://"+HOST
PATTERN=re.compile(r"^/career/[^/]+/?$")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prior",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    prior=load(a.prior);new={};save(a.receipt,new)
    result={"id":"external-wh-partners","verified":False,"status":"DIAGNOSTIC_ONLY","pages":{},"errors":[]}
    def paused(host):
        return any(host in d and parse_time(d[host]["until"])>dt.datetime.now(dt.timezone.utc) for d in (prior,new))
    if paused(HOST):
        result["status"]="HELD"
        result["errors"].append("Provider cooldown active")
    else:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            ctx=browser.new_context(service_workers="block")
            stopped=[];requests=[0]
            def route(r):
                u=urlsplit(r.request.url)
                requests[0]+=1
                if stopped or paused(u.hostname) or requests[0]>300 or r.request.method not in ("GET","HEAD") or r.request.resource_type in ("image","media","font") or (r.request.is_navigation_request() and u.hostname!=HOST):
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
            def snapshot():
                if stopped:raise RuntimeError(stopped[0])
                pairs=page.locator("a[href]").evaluate_all("""els => els.filter(e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden').map(e=>({url:e.href,title:e.innerText.trim()}))""")
                rows={}
                for x in pairs:
                    u=urlsplit(x["url"])
                    if u.scheme=="https" and u.netloc==HOST and PATTERN.fullmatch(u.path) and x["title"]:
                        rows[u.path.rstrip("/")]=x["title"]
                return rows
            try:
                page.goto(ROOT+"/careers/",wait_until="domcontentloaded")
                page.wait_for_timeout(1200)
                result["pages"]["landing"]=snapshot()
                page.goto(ROOT+"/careers/job-openings/",wait_until="domcontentloaded")
                page.wait_for_timeout(1200)
                for label in ("Malta","Italy","Romania","All"):
                    button=page.get_by_role("button",name=re.compile("^"+label+r"\s*$",re.I))
                    if button.count()!=1 or not button.is_visible() or not button.is_enabled():
                        raise ValueError("Missing or ambiguous public tab: "+label)
                    button.click()
                    page.wait_for_timeout(1600)
                    result["pages"][label]=snapshot()
                pages=result["pages"]
                union=set().union(*(set(pages[x]) for x in ("Malta","Italy","Romania")))
                result["country_union"]=len(union)
                result["all_count"]=len(pages["All"])
                result["landing_count"]=len(pages["landing"])
                result["all_matches_country_union"]=bool(union and union==set(pages["All"]))
                result["landing_missing_from_all"]=sorted(set(pages["landing"])-set(pages["All"]))
                result["all_missing_from_landing"]=sorted(set(pages["All"])-set(pages["landing"]))
                result["old_aml_on_current_listing"]=any("junior-aml-analyst" in k for k in union)
                # Agreement is useful evidence, not proof of complete coverage.
                result["visible_pagination_controls"]=page.get_by_role("button").all_inner_texts()[:30]
                result["status"]="PUBLIC_TAB_EVIDENCE_REVIEW_REQUIRED"
            except Exception as exc:
                result["status"]="HELD" if stopped else "DIAGNOSTIC_INCOMPLETE"
                result["errors"].append(type(exc).__name__+": "+str(exc)[:220])
            finally:
                browser.close()
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("WH_PUBLIC_COVERAGE",json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
