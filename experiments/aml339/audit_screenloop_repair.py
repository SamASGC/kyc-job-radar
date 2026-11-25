#!/usr/bin/env python3
"""Public rendered ATS listing audit with strict pagination and standard detail checks."""
import argparse,datetime as dt,json,re,os
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from hourly_http_guard import Guard,load,save,parse_time,until_from,now
from amlradar.sources import Board
from live_e2e18_full import audit_one
import live_e2e18_full as audit
from live_external50_wave02 import candidate as base_candidate

SOURCES={
 "reg50-three-s-money":("3S Money","https://app.screenloop.com/careers/3smoney","screenloop"),
}

def candidate(j):
    return base_candidate(j) or bool(re.search(r"\b(?:onboarding|periodic review|financial crime|financial crimes|due diligence|kyc|aml)\b",str(j.get("title","")),re.I))

def listed(page,url,provider,check_pause=lambda:None):
    host=urlsplit(url).hostname
    base=urlsplit(url).path.rstrip("/")
    pattern=re.compile(re.escape(base)+(r"/job_posts/([0-9]+)/?" if provider=="screenloop" else r"/([0-9]+)/?"))
    all_jobs={}
    seen_pages=set()
    for n in range(20):
        check_pause()
        page.wait_for_timeout(1000)
        check_pause()
        snapshot=page.evaluate("""() => ({
          text:document.body.innerText,
          rows:Array.from(document.querySelectorAll('a[href]')).filter(a=>a.getClientRects().length>0).map(a=>({url:a.href,title:a.innerText.trim()})),
          next:Array.from(document.querySelectorAll('button,a,[role=button]')).map((a,index)=>({a,index})).filter(({a})=>a.getClientRects().length>0 && ((a.innerText||'').trim()==='Next'||(a.getAttribute('aria-label')||'').trim()==='Next')).map(({a,index})=>({index,disabled:!!a.disabled||a.getAttribute('aria-disabled')==='true'||a.closest('[aria-disabled=true],.disabled')!==null,tag:a.tagName}))
        })""")
        text=snapshot["text"]
        rows={}
        for a in snapshot["rows"]:
            u=urlsplit(a["url"]);m=pattern.fullmatch(u.path)
            if u.hostname!=host or not m or not a["title"]:continue
            parts=[p.strip() for p in a["title"].splitlines() if p.strip()]
            title=parts[0]
            loc=parts[2] if provider=="screenloop" and len(parts)>=4 and parts[-1]=="Apply" else ""
            jid=m[1]
            if jid in rows and rows[jid]["title"]!=title:raise ValueError("Conflicting title for job ID")
            rows[jid]={"id":jid,"title":title,"location":loc,"url":a["url"],"description":""}
        if not rows:
            if n==0 and provider=="screenloop" and all(x in text for x in ("Job Openings","All Departments","All Locations","No jobs found","Powered by Screenloop")) and not snapshot["next"]:
                return [],1
            raise ValueError("No independently confirmed complete listing")
        fingerprint=tuple(sorted(rows))
        if fingerprint in seen_pages:raise ValueError("Pagination repeated page")
        seen_pages.add(fingerprint)
        if set(rows)&set(all_jobs):raise ValueError("Pagination overlapping IDs")
        all_jobs.update(rows)
        if provider=="bamboo":
            if "Current Openings" not in text or snapshot["next"] or re.search(r"\b(?:load more|show more|next page)\b",text,re.I):raise ValueError("Unresolved BambooHR pagination")
            return list(all_jobs.values()),1
        if not all(x in text for x in ("Job Openings","All Departments","All Locations","Powered by Screenloop")):raise ValueError("Unverified default filters")
        nxt=snapshot["next"]
        if not nxt:
            if re.search(r"(?m)^Next$",text):raise ValueError("Unresolved Next control")
            return list(all_jobs.values()),n+1
        if len(nxt)!=1:raise ValueError("Ambiguous pagination")
        if nxt[0]["disabled"]:return list(all_jobs.values()),n+1
        # Use exactly the same DOM element whose accessible label and visibility
        # were inspected above; inner text alone matched the ellipsis on this ATS.
        next_control=page.locator("button,a,[role=button]").nth(nxt[0]["index"])
        if not next_control.evaluate("a => a.getClientRects().length>0 && ((a.innerText||'').trim()==='Next'||(a.getAttribute('aria-label')||'').trim()==='Next') && !a.disabled && a.getAttribute('aria-disabled')!=='true' && !a.closest('[aria-disabled=true],.disabled')"):
            raise ValueError("Next control changed since snapshot")
        check_pause()
        next_control.click(timeout=10000)
        check_pause()
        page.wait_for_function("""prev => !prev.every(id=>Array.from(document.querySelectorAll('a[href]')).some(a=>a.href.includes('/job_posts/'+id+'?')||a.href.endsWith('/job_posts/'+id)))""",arg=list(rows),timeout=12000)
    raise ValueError("Pagination bound exceeded")

def run(sid):
    name,url,provider=SOURCES[sid]
    prior=Path(os.environ['AML339_PRIOR']); receipt=Path(os.environ['AML339_RECEIPT'])
    host=urlsplit(url).hostname
    previous=load(prior)
    if host in previous and parse_time(previous[host]['until'])>now():raise ValueError('Provider cooldown active: '+host)
    denied=[]
    def check_pause():
        if denied:raise ValueError('Public browser HTTP denied/rate limited: '+str(denied[0]))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page()
        def on_response(response):
            if urlsplit(response.url).hostname!=host:return
            if response.status in (403,429) or (response.status==503 and response.headers.get('retry-after')):
                denied.append(response.status)
                if response.status in (429,503):
                    end=until_from({'Retry-After':response.headers.get('retry-after')},now())
                    records=load(receipt)
                    if host not in records or parse_time(records[host]['until'])<end:
                        records[host]={'until':end.isoformat(),'status':response.status}
                    save(receipt,records)
        page.on('response',on_response)
        def route_request(route):
            if denied:route.abort()
            else:route.continue_()
        page.route('**/*',route_request)
        response=page.goto(url,wait_until="domcontentloaded",timeout=25000)
        if response is None or response.status!=200:raise ValueError("HTTP access not available; no retry")
        if urlsplit(page.url).hostname!=urlsplit(url).hostname:raise ValueError("Unexpected redirect")
        page.wait_for_timeout(3000)
        check_pause()
        jobs,pages=listed(page,url,provider,check_pause)
        check_pause()
        browser.close()
    original=Board.listing
    old=audit.candidate
    def listing(board):
        board.complete=True
        return jobs
    Board.listing=listing;audit.candidate=candidate
    try:
        result=audit_one({"id":sid,"name":name,"careers_url":url,"route":["site_jobs",urlsplit(url).hostname,r"^/careers/.+$"]},minutes=4)
    finally:
        Board.listing=original;audit.candidate=old
    ok=(result.get("state")=="listing_extracted" and result.get("list_complete") is True and result.get("total_listed")==len(jobs)
        and result.get("relevant_leads")==len(result.get("audited",[])) and result.get("unverified_in_scope")==0 and result.get("listing_untrackable_count")==0)
    return {"id":sid,"verified":ok,"pages":pages,"listing_count":len(jobs),"source":result}

def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True,choices=SOURCES);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    try:r=run(a.source)
    except Exception as e:r={"id":a.source,"verified":False,"error":type(e).__name__+": "+str(e)[:300]}
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print("BROWSER_FULL_AUDIT",json.dumps({k:v for k,v in r.items() if k!="source"}),flush=True)
    print("BROWSER_DETAIL_DISPOSITIONS",json.dumps([{"title":j.get("title"),"url":j.get("url"),"location":j.get("location"),"error":j.get("verification_error")} for j in r.get("source",{}).get("audited",[])],ensure_ascii=False),flush=True)
    if not r["verified"]:raise SystemExit("Incomplete browser source audit")
if __name__=="__main__":main()
