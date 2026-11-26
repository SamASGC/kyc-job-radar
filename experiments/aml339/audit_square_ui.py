#!/usr/bin/env python3
"""Read-only public Flatchr coverage and application-control diagnostic."""
import argparse, datetime as dt, json, re, time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from hourly_http_guard import load, save, parse_time, until_from
HOST="squaremanagement.flatchr.io"
ROOT="https://"+HOST+"/en/company/squaremanagement/"
PATTERN=re.compile(r"^/en/company/squaremanagement/vacancy/[a-z0-9]+-[^/]+/?$")
TITLE=re.compile(r"\b(?:AML|KYC|compliance|conformit[eé]|risk|risques?|r[eé]glementaire|regulatory|financial crime|due diligence|screening)\b",re.I)
MORE=re.compile(r"^(?:see|show|load|view) more offers$|^next(?: page)?$",re.I)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prior",type=Path,required=True)
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    prior=load(a.prior);new={};save(a.receipt,new)
    result={"id":"external-square-management","verified":False,"status":"DIAGNOSTIC_ONLY","listed":0,"audited":[],"errors":[]}
    def paused(host):
        return any(host in d and parse_time(d[host]["until"])>dt.datetime.now(dt.timezone.utc) for d in (prior,new))
    if paused(HOST):
        result["status"]="HELD"
        result["errors"].append("Provider cooldown active")
    else:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            ctx=browser.new_context(service_workers="block")
            stopped=[];requests=[0];deadline=time.monotonic()+180
            def route(r):
                u=urlsplit(r.request.url)
                requests[0]+=1
                if stopped or paused(u.hostname) or requests[0]>1200 or time.monotonic()>deadline or r.request.method not in ("GET","HEAD") or r.request.resource_type in ("image","media","font") or (r.request.is_navigation_request() and u.hostname!=HOST):
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
                if requests[0]>1200 or time.monotonic()>deadline:raise RuntimeError("Read budget exceeded")
            def snapshot():
                check()
                pairs=page.locator("a[href]").evaluate_all("""els => els.filter(e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden').map(e=>({url:e.href,title:e.innerText.trim()}))""")
                rows={}
                for x in pairs:
                    u=urlsplit(x["url"])
                    if u.scheme=="https" and u.netloc==HOST and PATTERN.fullmatch(u.path) and x["title"]:
                        rows[u.path.rstrip("/")]=x
                return rows
            try:
                page.goto(ROOT,wait_until="domcontentloaded")
                page.wait_for_timeout(1200)
                all_rows=snapshot();result["initial_count"]=len(all_rows)
                result["pagination_steps"]=[]
                for _ in range(10):
                    check()
                    controls=page.get_by_role("button",name=MORE).or_(page.get_by_role("link",name=MORE)).or_(page.get_by_text(MORE,exact=True))
                    visible=[c for c in controls.all() if c.is_visible()]
                    states=[{"text":c.inner_text().strip(),"enabled":c.is_enabled()} for c in visible]
                    result["pagination_steps"].append({"count":len(all_rows),"controls":states})
                    enabled=[c for c in visible if c.is_enabled()]
                    if not enabled:break
                    if len(enabled)!=1:raise ValueError("Ambiguous pagination")
                    before=len(all_rows);enabled[0].click();page.wait_for_timeout(1600)
                    all_rows.update(snapshot())
                    if len(all_rows)==before:raise ValueError("Pagination did not establish new listing IDs")
                else:raise ValueError("Pagination budget exhausted")
                result["listed"]=len(all_rows)
                result["listing_ids"]=sorted(all_rows)
                for key,row in all_rows.items():
                    if not TITLE.search(row["title"]):continue
                    check()
                    response=page.goto(row["url"],wait_until="domcontentloaded")
                    page.wait_for_timeout(500)
                    check()
                    heads=page.get_by_role("heading").all_inner_texts()
                    apply=page.get_by_role("button",name=re.compile(r"^Apply$",re.I))
                    buttons=[b for b in apply.all() if b.is_visible() and b.is_enabled()]
                    body=page.locator("body").inner_text()
                    ev={"title":row["title"],"url":row["url"],"status":response.status if response else None,"headings":heads[:12],"enabled_apply_controls":len(buttons),"detail_preview":body[:900],"control_attributes":[]}
                    for b in buttons:
                        ev["control_attributes"].append(b.evaluate("""e=>({tag:e.tagName,type:e.getAttribute('type'),id:e.id,aria:e.getAttribute('aria-controls'),dataTarget:e.getAttribute('data-target'),outer:e.outerHTML.slice(0,600)})"""))
                    result["audited"].append(ev)
                    # No click on Apply, no form filling or submission.
                result["status"]="PUBLIC_UI_EVIDENCE_REVIEW_REQUIRED"
            except Exception as exc:
                result["status"]="HELD" if stopped else "DIAGNOSTIC_INCOMPLETE"
                result["errors"].append(type(exc).__name__+": "+str(exc)[:240])
            finally:
                browser.close()
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("SQUARE_UI_EVIDENCE",json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
