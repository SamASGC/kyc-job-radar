#!/usr/bin/env python3
"""Bounded audit of previously failed official career sources. No production writes."""
import argparse,datetime as dt,json,re
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit,parse_qs
from urllib.request import Request,build_opener,HTTPRedirectHandler
from amlradar.sources import Board
from live_e2e18_full import audit_one
import live_e2e18_full as audit
from live_external50_wave02 import candidate,Anchors

class SameHost(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        u=urlsplit(urljoin(req.full_url,newurl))
        if u.scheme!="https" or u.hostname!=urlsplit(req.full_url).hostname:raise ValueError("External redirect requires review")
        return super().redirect_request(req,fp,code,msg,headers,newurl)
def get(url,limit=4_000_000):
    with build_opener(SameHost()).open(Request(url,headers={"User-Agent":"AML339-source-audit/1.0"}),timeout=15) as r:
        b=r.read(limit+1)
    if len(b)>limit:raise ValueError("Truncated official response")
    return b.decode("utf-8","replace")

class Visible(HTMLParser):
    def __init__(self):
        super().__init__();self.text=[];self.hidden=0;self.embeds=[];self.forms=[];self.anchors=Anchors()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ("script","style","template"):self.hidden+=1
        if tag in ("iframe","script") and a.get("src"):self.embeds.append(a["src"])
        if tag=="form":self.forms.append(a.get("action",""))
        if tag in ("h1","h2","h3","h4","p","div","li","section"):self.text.append("\n")
    def handle_endtag(self,tag):
        if tag in ("script","style","template") and self.hidden:self.hidden-=1
        if tag in ("h1","h2","h3","h4","p","div","li","section"):self.text.append("\n")
    def handle_data(self,data):
        if not self.hidden:self.text.append(data)
def parse(html):
    p=Visible();p.feed(html);p.anchors.feed(html)
    return p," ".join("".join(p.text).split()).replace("’","'").casefold()

SOURCES={
 "reg50-connectpay":("ConnectPay","https://connectpay.com/career/","currently, we don't have any available positions","always eager to connect"),
 "lt-emi-research-uab-blue-emi-lt":("Blue EMI","https://blueemi.com/careers/","we don't have any open roles at the moment","open positions"),
 "reg100-lt-uab-monavate":("Monavate","https://www.monavate.com/careers","there are currently no open roles","open roles"),
 "reg50-payhound":("Payhound","https://payhound.com/jobs","no items found.","current openings"),
 "reg100-ie-currenxie-technologies-limited":("Currenxie","https://currenxie.com/eu/company/careers",None,None),
 "reg100-nl-mews-financial-services-b-v":("Mews","https://www.mews.com/en/careers",None,None),
 "reg50-three-s-money":("3S Money","https://app.screenloop.com/careers/3smoney",None,None),
 "reg100-mt-weavr-europe-ltd":("Weavr","https://app.screenloop.com/careers/weavr",None,None),
 "reg100-mt-moneybase-limited":("Moneybase","https://moneybase.com/careers",None,None),
 "reg100-cy-altery-eu-limited-formerly-named-heado-limited":("Altery","https://altery.com/careers/open-positions/",None,None),
 "lt-emi-research-paymont-uab":("Paymont","https://www.paymont.eu/career/",None,None),
 "reg50-paysera-lt":("Paysera","https://www.paysera.lt/v2/en-LT/career",None,None),
 "reg50-finance-incorporated":("Finance Incorporated","https://www.financeincorp.com/careers/",None,None),
 "lt-emi-research-satchelpay-uab":("SatchelPay","https://satchel.eu/careers/",None,None),
 "reg100-ie-decta-limited":("DECTA","https://www.decta.com/company/careers",None,None),
}

def empty_proof(p,t,marker,heading,url):
    if not marker or marker not in t or heading not in t:return False
    # A marker in generic marketing content is insufficient. Require the
    # official careers section, with no separate job-detail or ATS links.
    if t.index(marker)<t.index(heading) or t.index(marker)-t.index(heading)>400:return False
    for href,title in p.anchors.links.items():
        u=urlsplit(urljoin(url,href)); path=u.path.casefold()
        if re.search(r"/(?:jobs|careers|career|vacancies|positions)/(?!$)[^/]+",path) and u.path.rstrip("/")!=urlsplit(url).path.rstrip("/"):return False
        if re.search(r"greenhouse|lever\.co|ashbyhq|bamboohr|screenloop|recruitee|personio|workable|teamtailor|rippling|join\.com",u.hostname or "",re.I):return False
    if any(re.search(r"greenhouse|lever\.co|ashbyhq|bamboohr|screenloop|recruitee|personio|workable|teamtailor|rippling",x,re.I) for x in p.embeds):return False
    return True

def inspect(sid):
    name,url,marker,heading=SOURCES[sid]
    html=get(url);p,t=parse(html);host=urlsplit(url).hostname
    evidence={"id":sid,"name":name,"careers_url":url,"verified":False,"embeds":[x for x in p.embeds if re.search(r"job|career|greenhouse|screenloop|bamboohr|personio|recruitee|ashby|workable",x,re.I)][:15],"links":[[urljoin(url,h),v] for h,v in p.anchors.links.items() if re.search(r"job|career|vacanc|position|apply|AML|compliance",h+" "+v,re.I)][:40]}
    # An explicitly empty board is checked anew every run. On disappearance
    # of its proof, fail closed; never report an empty list from silence.
    if empty_proof(p,t,marker,heading,url):
        original=Board.listing
        def listing(board):
            board.complete=True
            return []
        Board.listing=listing
        try:r=audit_one({"id":sid,"name":name,"careers_url":url,"route":["site_jobs",host,r"^/jobs/[^/]+/?$"]},minutes=3)
        finally:Board.listing=original
        ok=r["state"]=="listing_extracted" and r["list_complete"] is True and r["total_listed"]==0
        evidence.update(verified=ok,mode="explicit_empty",empty_marker=marker,section_heading=heading,audit=r)
        return evidence
    if sid=="reg100-ie-currenxie-technologies-limited":
        # Compare public BambooHR JSON against independent employer-linked IDs.
        bh="currenxie.bamboohr.com"
        expected={}
        for href,title in p.anchors.links.items():
            u=urlsplit(urljoin(url,href))
            if u.hostname!=bh:continue
            m=re.fullmatch(r"/careers/([0-9]+)/?",u.path)
            jobid=m[1] if m else (parse_qs(u.query).get("id",[None])[0] if u.path=="/jobs/view.php" else None)
            if jobid and title:expected[str(jobid)]=title
        evidence["independent_ids"]=sorted(expected)
        raw=json.loads(get("https://"+bh+"/careers/list"))
        rows=raw.get("result",raw) if isinstance(raw,dict) else raw
        if not isinstance(rows,list):raise ValueError("Unknown BambooHR public listing schema")
        jobs=[]
        for row in rows:
            jid=str(row.get("id",""))
            title=row.get("jobOpeningName") or row.get("title") or row.get("name")
            loc=row.get("location") or row.get("locationName") or ""
            if isinstance(loc,dict):loc=", ".join(str(v) for v in loc.values() if isinstance(v,str) and v)
            if not jid.isdigit() or not isinstance(title,str) or not title.strip():raise ValueError("Incomplete BambooHR job record")
            jobs.append({"id":jid,"title":title,"location":loc,"url":"https://"+bh+"/careers/"+jid,"description":""})
        if not expected or set(expected)!=set(j["id"] for j in jobs):raise ValueError("BambooHR API and official employer listing disagree")
        original=Board.listing
        def listing(board):
            board.complete=True
            return jobs
        Board.listing=listing;old=audit.candidate;audit.candidate=candidate
        try:r=audit_one({"id":sid,"name":name,"careers_url":url,"route":["site_jobs",bh,r"^/careers/[0-9]+/?$"]},minutes=4)
        finally:Board.listing=original;audit.candidate=old
        ok=r["state"]=="listing_extracted" and r["list_complete"] is True and r["unverified_in_scope"]==0 and r["listing_untrackable_count"]==0 and r["relevant_leads"]==len(r["audited"])
        evidence.update(verified=ok,mode="bamboohr_public_api",audit=r)
        return evidence
    # Diagnostics only for other formats. Evidence retained to choose next
    # adapter rather than trying unproven API endpoints.
    evidence["mode"]="requires_adapter"
    return evidence

def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True,choices=SOURCES);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    try:r=inspect(a.source)
    except Exception as e:r={"id":a.source,"verified":False,"error":type(e).__name__+": "+str(e)[:300]}
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print("RECOVERY_AUDIT",json.dumps({k:v for k,v in r.items() if k not in ("audit","links","embeds")},ensure_ascii=False),flush=True)
    if r.get("audit"):print("RECOVERY_COVERAGE",json.dumps({k:r["audit"].get(k) for k in ("state","total_listed","relevant_leads","unverified_in_scope","errors")}),flush=True)
    if not r["verified"]:raise SystemExit("Not approved for production")
if __name__=="__main__":main()
