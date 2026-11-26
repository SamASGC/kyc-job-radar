#!/usr/bin/env python3
"""Read-only public Flatchr coverage and application-control diagnostic."""
import argparse, datetime as dt, json, re, time
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from hourly_http_guard import load, save, parse_time, until_from
from quality_audit import candidate,evaluate
from live_external50_wave02 import candidate as extended_candidate
from two_lane_alert_preview import listing_identity
from amlradar.model import plain
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
                landing=page.goto(ROOT,wait_until="domcontentloaded")
                if not landing or landing.status!=200:raise ValueError("Board response not successful")
                # Independently parse all public anchors present in initial HTML.
                from html.parser import HTMLParser
                from urllib.parse import urljoin
                class Anchors(HTMLParser):
                    def __init__(self):
                        super().__init__();self.keys=set()
                    def handle_starttag(self,tag,attrs):
                        if tag!="a":return
                        u=urlsplit(urljoin(ROOT,dict(attrs).get("href","")))
                        if u.scheme=="https" and u.netloc==HOST and PATTERN.fullmatch(u.path):
                            self.keys.add(u.path.rstrip("/"))
                independent=Anchors();independent.feed(landing.text())
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
                result["independent_anchor_count"]=len(independent.keys)
                if not all_rows or set(all_rows)!=independent.keys:raise ValueError("Initial official HTML and fully rendered listing disagree")
                result["listing_role_keys"]=sorted({listing_identity(result["id"],r) for r in all_rows.values()})
                if len(result["listing_role_keys"])!=len(all_rows) or "" in result["listing_role_keys"]:raise ValueError("Untrackable listing ID")
                # The public listing prints country within each job card. Bind it
                # only to the same exact unique job URL; never infer country from
                # corporate description or another job's location.
                card_rows=page.locator("a[href]").evaluate_all("""els => els.filter(e=>e.getClientRects().length && /\\/vacancy\\//.test(e.pathname)).map(e=>{
                  const key=x=>{try {const u=new URL(x.href);return u.origin===location.origin && /\\/vacancy\\//.test(u.pathname)?u.pathname.replace(/\\/$/,''):null;} catch {return null;}};
                  let p=e;
                  for(let i=0;p && i<8;i++,p=p.parentElement){
                    const keys=new Set(Array.from(p.querySelectorAll('a[href]')).map(key).filter(Boolean));if(key(e))keys.add(key(e));
                    if(keys.size>1)break;
                    const txt=(p.innerText||'').trim();
                    if(keys.size===1 && /\\b(?:Luxembourg|France|Belgique|Belgium)\\b/i.test(txt) && /\\b\\d{4,5}\\b/.test(txt))return {key:key(e),text:txt};
                  }
                  return {key:key(e),text:''};
                })""")
                card_text={}
                for c in card_rows:
                    if c.get("key") in all_rows and c.get("text"):card_text.setdefault(c["key"],set()).add(c["text"])
                selected={k:r for k,r in all_rows.items() if TITLE.search(r["title"]) or candidate(r) or extended_candidate(r)}
                result["relevant"]=len(selected)
                for key,row in selected.items():
                    check()
                    response=page.goto(row["url"],wait_until="domcontentloaded")
                    page.wait_for_timeout(500)
                    check()
                    heads=page.get_by_role("heading").all_inner_texts()
                    apply=page.get_by_role("button",name=re.compile(r"^Apply$",re.I))
                    buttons=[b for b in apply.all() if b.is_visible() and b.is_enabled()]
                    body=page.locator("body").inner_text()
                    ev={"title":row["title"],"url":row["url"],"verified":False}
                    try:
                        if not response or response.status!=200 or urlsplit(page.url).netloc!=HOST or urlsplit(page.url).path.rstrip("/")!=key:raise ValueError("Detail response or identity mismatch")
                        if not any(" ".join(h.split())==" ".join(row["title"].split()) for h in heads):raise ValueError("Title mismatch")
                        if not buttons:raise ValueError("No visible enabled Apply control")
                        if re.search(r"no longer accepting applications|job (?:is )?closed|offre (?:pourvue|expirée|clôturée)",body,re.I):raise ValueError("Closed vacancy")
                        lines=[x.strip() for x in body.splitlines() if x.strip()]
                        # Exact pre-description metadata: title, city/postcode, contract, displayed date.
                        title_at=[i for i,x in enumerate(lines) if " ".join(x.split())==" ".join(row["title"].split())]
                        if len(title_at)!=1:raise ValueError("Ambiguous detail title")
                        j=title_at[0]
                        k=next((i for i in range(j+1,len(lines)) if lines[i]=="Description"),None)
                        if k is None or k-j!=4:raise ValueError("Unrecognized detail metadata")
                        city=lines[j+1]; displayed_date=lines[j+3]
                        if not re.fullmatch(r".+,\s*\d{4,5}",city):raise ValueError("Location not explicit")
                        city_name,postal=city.rsplit(",",1);postal=postal.strip()
                        countries=set()
                        for txt in card_text.get(key,set()):
                            m=re.search(re.escape(city_name.strip())+r"\s+"+re.escape(postal)+r"\s+(Luxembourg|France|Belgique|Belgium)\b",txt,re.I)
                            if m:countries.add(m.group(1).lower())
                        if len(countries)!=1:raise ValueError("Listing/detail location not independently matched")
                        country={"luxembourg":"Luxembourg","france":"France","belgique":"Belgium","belgium":"Belgium"}[countries.pop()]
                        loc=city+", "+country
                        missions=[i for i in range(k+1,len(lines)) if lines[i]=="Missions"]
                        profiles=[i for i in range(k+1,len(lines)) if lines[i]=="Profile"]
                        if len(missions)!=1 or len(profiles)!=1 or not k<missions[0]<profiles[0]:raise ValueError("Duty/requirement sections unclear")
                        stop_profile=next((i for i in range(profiles[0]+1,len(lines)) if lines[i] in ("Nous rejoindre","Votre package et vos avantages","Notre processus de recrutement","Apply","Back to offers")),len(lines))
                        duties=lines[missions[0]+1:profiles[0]]
                        requirements=lines[profiles[0]+1:stop_profile]
                        if not duties or not requirements:raise ValueError("Empty duty or requirement section")
                        desc="\n".join(["Responsibilities",*duties,"Requirements",*requirements])
                        if len(plain(desc))<200:raise ValueError("Insufficient description")
                        evaluation=evaluate({"title":row["title"],"url":row["url"],"apply_url":row["url"],"location":loc,"description":desc},True)
                        # French requirements are not automatically equivalent to
                        # English evidence. Keep the existing evaluator intact;
                        # apply a conservative source-only barrier until covered.
                        req_text="\n".join(requirements)
                        years=[int(m.group(1)) for m in re.finditer(r"\b(\d+)\s*(?:à\s*\d+\s*)?(?:ans|années)\b",req_text,re.I)]
                        if any(n>3 for n in years):
                            evaluation["barriers"].append("Requisito de experiencia en francés superior a tres años")
                        evaluation["barriers"].append("Requisitos en francés: revisión manual obligatoria antes de alertar")
                        evaluation["class"]="not_recommended"
                        ev.update(verified=True,location=loc,displayed_date=displayed_date,description_length=len(plain(desc)),enabled_apply_controls=len(buttons),evaluation=evaluation,apply_url=row["url"])
                    except Exception as exc:
                        ev["error"]=type(exc).__name__+": "+str(exc)[:240]
                    result["audited"].append(ev)
                    # No click on Apply, no form filling or submission.
                result["unverified"]=sum(not r["verified"] for r in result["audited"])
                if result["unverified"] or len(result["audited"])!=result["relevant"]:raise ValueError("Relevant detail coverage incomplete")
                check()
                result["status"]="QUALITY_EVIDENCE_PASS_REVIEW_REQUIRED"
            except Exception as exc:
                result["status"]="HELD" if stopped else "DIAGNOSTIC_INCOMPLETE"
                result["errors"].append(type(exc).__name__+": "+str(exc)[:240])
            finally:
                browser.close()
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("SQUARE_QUALITY_EVIDENCE",json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
