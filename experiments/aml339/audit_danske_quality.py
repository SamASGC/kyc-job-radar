#!/usr/bin/env python3
"""Experimental read-only Oracle public UI reader. No enrollment or API replay."""
import argparse, datetime as dt, json, re, time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from hourly_http_guard import load, save, until_from, parse_time
from quality_audit import candidate,evaluate
from two_lane_alert_preview import listing_identity
from amlradar.model import plain

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
            # Oracle can render an empty overlay anchor alongside the actual
            # job title. Only associate a title within the nearest visible
            # ancestor that contains exactly one distinct job identity.
            entries=page.locator("a[href]").evaluate_all("""els => {
                const visible=e=>e.getClientRects().length>0 && getComputedStyle(e).visibility!=='hidden';
                const key=e=>{try {const u=new URL(e.href);return u.origin===location.origin && /\\/job\\/\\d+\\/?$/.test(u.pathname)?u.pathname.replace(/\\/$/,''):null;} catch {return null;}};
                return els.filter(e=>visible(e)&&key(e)).map(e=>{
                    let title=(e.innerText||e.getAttribute('aria-label')||'').trim(), samples=[], locationText='', postingDate='';
                    for(let n=e.parentElement, depth=0;!title&&n&&depth<6;n=n.parentElement,depth++){
                        const ids=new Set([...n.querySelectorAll('a[href]')].filter(visible).map(key).filter(Boolean));
                        if(ids.size!==1||!ids.has(key(e))) break;
                        const candidates=[...n.querySelectorAll('h2,h3,h4,[role=heading],[class*="job-title"],[class*="jobTitle"]')].filter(visible).map(x=>x.innerText.trim()).filter(Boolean);
                        const names=[...new Set(candidates)];
                        samples.push({tag:n.tagName,classes:String(n.className).slice(0,200),headings:names.slice(0,5),text:n.innerText.trim().slice(0,350)});
                        if(names.length===1)title=names[0];
                        // Observed on Danske's public Oracle listing: the first
                        // line of a job-tile is its title, followed by location
                        // and the explicit posting date. Do not apply to a
                        // generic ancestor or a tile with ambiguous IDs.
                        if(!title && n.classList.contains('job-tile') && n.classList.contains('job-grid-item')){
                            const lines=n.innerText.split(/\\n/).map(x=>x.trim()).filter(Boolean);
                            if(lines.length>=2 && /Posting Date\\s*\\d{1,2}\\/\\d{1,2}\\/\\d{4}/i.test(lines[1]) && lines[0].length<=240 && !/Posting Date/i.test(lines[0]))title=lines[0];
                        }
                    }
                    const tile=e.closest('.job-tile.job-grid-item');
                    if(tile && new Set([...tile.querySelectorAll('a[href]')].filter(visible).map(key).filter(Boolean)).size===1){
                        const lines=tile.innerText.split(/\\n/).map(x=>x.trim()).filter(Boolean);
                        const row=lines[1]||'';
                        const m=row.match(/^(.+?)\\s*Posting Date\\s*(\\d{1,2}\\/\\d{1,2}\\/\\d{4})$/i);
                        if(m && lines[0]===title){locationText=m[1].trim();postingDate=m[2];}
                    }
                    return {url:e.href,title,samples,locationText,postingDate};
                });
            }""")
            result["visible_card_samples"]=[{"url":e["url"],"title":e["title"],"ancestors":e["samples"]} for e in entries[:5]]
            result["visible_job_id_count"]=len({job_identity(e["url"],host,site) for e in entries if job_identity(e["url"],host,site)})
            rows={}
            for e in entries:
                key=job_identity(e["url"],host,site)
                if key:
                    title=" ".join(e["title"].split())
                    if title:
                        if key in rows and rows[key]["title"]!=title:
                            raise ValueError("Conflicting visible job labels: "+key)
                        rows[key]={"id":key,"title":title,"url":root+"/job/"+key,"location":e["locationText"],"posting_label":e["postingDate"]}
            return rows
        try:
            page.goto(root+"/jobs",wait_until="domcontentloaded")
            # Dismiss optional cookies via the explicitly offered decline control.
            decline=page.get_by_role("button",name=re.compile(r"^(?:I DECLINE|DECLINE)$",re.I))
            if decline.count()==1 and decline.is_visible() and decline.is_enabled():decline.click(timeout=5000)
            # Oracle initially renders zero while results are being loaded.
            # Wait for a positive total and separately retain only public DOM evidence.
            try:
                page.wait_for_function(r"() => /Job search results\s+[1-9][\d,]*|[1-9][\d,]*\s+Open Jobs/i.test(document.body.innerText)",timeout=25000)
            except Exception:
                pass
            check()
            result["visible_link_samples"]=page.locator("a[href]").evaluate_all("""els => els.filter(e=>e.getClientRects().length).slice(0,100).map(e=>({path:new URL(e.href).pathname,label:(e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,120)}))""")
            result["visible_button_labels"]=page.get_by_role("button").all_inner_texts()[:40]
            result["visible_headings"]=page.get_by_role("heading").all_inner_texts()[:40]
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
                if result.get("visible_job_id_count",0)>0 and not links():
                    raise ValueError("Visible job IDs found but no unambiguous card title")
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
            result["listing_role_keys"]=sorted({listing_identity("external-danske-bank",r) for r in all_rows.values()})
            if len(result["listing_role_keys"])!=expected or "" in result["listing_role_keys"]:raise ValueError("Untrackable listing identities")
            relevant=[r for r in all_rows.values() if TITLE.search(r["title"]) or candidate(r)]
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
                    # Use only the job-description region, not global corporate
                    # page chrome or cookie text, for skills/requirements.
                    regions=page.locator('[class*="job-details__description"],[class*="job-description"],[itemprop="description"]')
                    vals={" ".join(x.inner_text().split()) for x in regions.all() if x.is_visible() and len(x.inner_text().strip())>=200}
                    # Preserve paragraphs for the original duty/requirement parser.
                    descriptions=[x.inner_text().strip() for x in regions.all() if x.is_visible() and len(x.inner_text().strip())>=200]
                    if len(vals)==1:
                        desc=descriptions[0]
                    else:
                        m=re.search(r"(?:^|\n)Job Description\s*\n(.+?)(?:\nJob Info\s*\n|\nApply Now\s*(?:\n|$))",s,re.I|re.S)
                        if not m:raise ValueError("Unambiguous job description region unavailable")
                        desc=m.group(1).strip()
                    if len(plain(desc))<200:raise ValueError("Insufficient description evidence")
                    loc=row.get("location","")
                    if not loc:raise ValueError("Missing explicit listing location")
                    if loc.casefold() not in s.casefold():
                        # Require exact location text or the location without a
                        # clearly delimited work-mode suffix in job detail.
                        simple=re.sub(r"\s*\((?:Hybrid|On-site|Remote)\)$","",loc,flags=re.I)
                        if not simple or simple.casefold() not in s.casefold():raise ValueError("Listing/detail location mismatch")
                    # Posting Date does not prove first publication; leave date
                    # unknown rather than promoting it to confirmed recent.
                    job={"title":row["title"],"url":row["url"],"apply_url":row["url"],"location":loc,"description":desc}
                    ev.update(verified=True,application_control_count=len(controls),description_present=True,description_length=len(plain(desc)),evaluation=evaluate(job,True),apply_url=row["url"])
                except Exception as exc:
                    ev["error"]=type(exc).__name__+": "+str(exc)[:180]
                result["audited"].append(ev)
            result["unverified"]=sum(not r["verified"] for r in result["audited"])
            if result["unverified"] or len(result["audited"])!=len(relevant):raise ValueError("Relevant details incomplete")
            check()
            # This is explicitly experimental evidence, not the production verifier.
            result["status"]="QUALITY_EVIDENCE_PASS_REVIEW_REQUIRED"
        except Exception as exc:
            result["errors"].append(type(exc).__name__+": "+str(exc)[:240])
        finally:
            result["request_count"]=requests
            if stop:result["errors"].extend(stop[:1]);result["status"]="HELD"
            browser.close()
    return result

def main():
    a=argparse.ArgumentParser();a.add_argument("--source",choices=["danske-bank"],required=True);a.add_argument("--prior",type=Path,required=True);a.add_argument("--receipt",type=Path,required=True);a.add_argument("--out",type=Path,required=True);args=a.parse_args()
    self_test()
    result=run(args.source,args.prior,args.receipt)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("ORACLE_UI_EVIDENCE",json.dumps({k:v for k,v in result.items() if k not in ("listing_ids","audited")},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
