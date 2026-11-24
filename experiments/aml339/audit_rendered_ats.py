#!/usr/bin/env python3
"""Official publicly rendered job boards: inspect standard JS rendering.
No login, no access-control bypass, no retry of denied requests, no publication.
Only Altery's complete static audit is a production candidate in this run.
"""
import argparse,json,re
from pathlib import Path
from urllib.parse import urlsplit
from live_external_generic import audit_config
SOURCES={
 "reg100-cy-altery-eu-limited-formerly-named-heado-limited":("Altery","https://altery.com/careers/open-positions/",r"^/careers/[0-9a-f-]{36}/?$"),
 "reg50-three-s-money":("3S Money","https://app.screenloop.com/careers/3smoney",r"^/careers/3smoney/job_posts/[0-9]+/?$"),
 "reg100-mt-weavr-europe-ltd":("Weavr","https://app.screenloop.com/careers/weavr",r"^/careers/weavr/job_posts/[0-9]+/?$"),
 "reg50-paysera-lt":("Paysera","https://www.paysera.lt/v2/en-LT/career",r"^/v2/(?:en|lt)-LT/careers$"),
 "reg50-finance-incorporated":("Finance Incorporated","https://financeincorporated.bamboohr.com/careers",r"^/careers/[0-9]+/?$"),
 "reg100-ie-currenxie-technologies-limited":("Currenxie","https://currenxie.bamboohr.com/careers",r"^/careers/[0-9]+/?$"),
 "reg100-mt-moneybase-limited":("Moneybase","https://moneybase.com/careers",r"^/job-position/?$"),
 "reg100-nl-mews-financial-services-b-v":("Mews","https://www.mews.com/en/careers",r"^/en/careers/[^/]+/?$"),
}

def browser_inspect(url,pattern):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page()
        response=page.goto(url,wait_until="domcontentloaded",timeout=25000)
        if not response or response.status!=200:raise ValueError("HTTP access not available; no retry")
        if urlsplit(page.url).hostname!=urlsplit(url).hostname:raise ValueError("Unexpected redirect")
        page.wait_for_timeout(3000)
        def snapshot():
            return page.evaluate("""() => ({
              anchors:Array.from(document.querySelectorAll('a[href]')).filter(a=>a.getClientRects().length>0).map(a=>({url:a.href,title:(a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,240),context:(a.closest('article,li,tr,[data-job-id]')?.innerText||a.parentElement?.innerText||'').trim().slice(0,400)})),
              controls:Array.from(document.querySelectorAll('button,[role=button]')).filter(a=>a.getClientRects().length>0).map(a=>({text:(a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,120),href:a.getAttribute('data-href'),action:a.getAttribute('data-action')})).filter(a=>a.text),
              frames:Array.from(document.querySelectorAll('iframe[src]')).map(a=>a.src),
              text:document.body.innerText.slice(0,35000)
            })""")
        first=snapshot();page.wait_for_timeout(1500);second=snapshot()
        browser.close()
    def ids(s):
        return {a["url"] for a in s["anchors"] if re.fullmatch(pattern,urlsplit(a["url"]).path) and urlsplit(a["url"]).hostname==urlsplit(url).hostname}
    found=ids(second)
    return {"rendered_job_links":[a for a in second["anchors"] if a["url"] in found],"stable_link_ids":ids(first)==found,
            "career_related_links":[a for a in second["anchors"] if re.search(r"career|job|vacanc|position|apply",a["url"]+" "+a["title"],re.I)][:60],
            "controls":[a for a in second["controls"] if re.search(r"job|apply|next|load more|show more|position",a["text"],re.I)][:60],
            "frames":second["frames"],
            "visible_count_markers":re.findall(r"(?:open roles|open positions|job openings|vacancies|jobs found|showing)\s*[:(]?\s*\d+|\b\d+\s*(?:open roles|open positions|jobs|vacancies)\b",second["text"],re.I)[:20],
            "text_excerpt":second["text"][:15000]}

def main():
    p=argparse.ArgumentParser();p.add_argument("--source",choices=SOURCES,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    name,url,pattern=SOURCES[a.source]; result={"id":a.source,"name":name,"url":url,"verified":False}
    try:
        if a.source.startswith("reg100-cy-altery"):
            cfg={"id":a.source,"name":name,"careers_url":url,"route":["site_jobs",urlsplit(url).hostname,pattern],"job_pattern":pattern}
            r,ok=audit_config(cfg)
            result.update(verified=ok,config=cfg,audit=r)
        else:result.update(browser_inspect(url,pattern))
    except Exception as e:result["error"]=type(e).__name__+": "+str(e)[:300]
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("RENDERED_ATS_RESULT",json.dumps({"id":a.source,"verified":result["verified"],"linked":len(result.get("rendered_job_links",[])),"listed":result.get("audit",{}).get("total_listed"),"markers":result.get("visible_count_markers",[]),"error":result.get("error"),"audit_errors":result.get("audit",{}).get("errors",[])}),flush=True)
if __name__=="__main__":main()
