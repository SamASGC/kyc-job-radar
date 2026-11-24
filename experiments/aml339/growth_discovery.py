#!/usr/bin/env python3
"""Bounded regulator-first discovery and persistent batch selection.
Discovery is evidence, not a claim that a legal entity is a new employer or licensed today."""
import argparse, datetime as dt, hashlib, ipaddress, json, re, socket, sys, unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from urllib.request import Request,build_opener,HTTPRedirectHandler
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.aml339_source_manifest import CORE,OPTIONAL
from external_live_registry import load_registry
DIR=ROOT/"experiments/aml339"
QUEUES=("lithuania_emi_wave01.json","regulator50_external_candidates.json","regulator100_discovery_queue.json","external_regulated50_wave02.json")
BLOCKED=("workable.com","sage.hr","linkedin.com","facebook.com","instagram.com","twitter.com","x.com","youtube.com","tiktok.com","bit.ly")
TARGET={"LT","EE","MT","LU","ES"}
REGULATORS=("www.lb.lt","lb.lt","www.fi.ee","fi.ee","www.bank.lv","bank.lv")
INDEXES=[
 ("LT",f"https://www.lb.lt/en/sfi-financial-market-participants?market=1&type=8&page={i}",r"/en/sfi-financial-market-participants/[^/]+") for i in range(1,6)
]+[
 ("EE","https://www.fi.ee/en/payment-services/payment-services/payment-institutions/estonian-payment-institutions",r"/en/payment-services/payment-services/payment-institutions/estonian-payment-institutions/[^/]+"),
 ("EE","https://www.fi.ee/en/payment-services/payment-services/e-money-institutions/estonian-e-money-institutions",r"/en/payment-services/payment-services/e-money-institutions/estonian-e-money-institutions/[^/]+")
]
def blocked(host):return any(host==d or host.endswith("."+d) for d in BLOCKED)
def safe_url(url):
    u=urlsplit(url);host=u.hostname or ""
    if u.scheme!="https" or u.username or u.password or u.port not in (None,443) or not host or blocked(host):raise ValueError("Unapproved URL")
    for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(x[4][0]).is_global:raise ValueError("Non-public IP")
    return url
class Redirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        safe_url(newurl)
        # Never silently change employer identity; www and non-www only.
        if urlsplit(req.full_url).hostname.removeprefix("www.")!=urlsplit(newurl).hostname.removeprefix("www."):raise ValueError("Cross-domain redirect requires review")
        return super().redirect_request(req,fp,code,msg,headers,newurl)
def get(url):
    safe_url(url)
    with build_opener(Redirect()).open(Request(url,headers={"User-Agent":"AML339 public career research/1.0"}),timeout=12) as r:
        body=r.read(2_000_001)
        if len(body)>2_000_000:raise ValueError("Truncated response")
        return body.decode("utf-8","replace")
class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.current=None;self.links=[]
    def handle_starttag(self,t,a):
        if t=="a":self.current=[dict(a).get("href",""),[]]
    def handle_data(self,d):
        if self.current is not None:self.current[1].append(d)
    def handle_endtag(self,t):
        if t=="a" and self.current is not None:
            self.links.append((self.current[0]," ".join(" ".join(self.current[1]).split())));self.current=None
def anchors(url,body):
    p=Links();p.feed(body)
    return [(urljoin(url,h),t) for h,t in p.links if h and t]
def norm(name):
    words=re.findall(r"[a-z0-9]+",unicodedata.normalize("NFKD",name.casefold()).encode("ascii","ignore").decode())
    ignore={"uab","sia","ou","as","ab","oy","ltd","limited","sa","sas","sl","slu","srl","bv","gmbh","ede","ep","europe","lithuania","malta","estonia","latvia","spain","ireland","luxembourg"}
    return "".join(w for w in words if w not in ignore)
def hostkey(url):
    return (urlsplit(url or "").hostname or "").removeprefix("www.")
def key(row):
    return norm(row["name"])
def collect_queues():
    rows=[]
    for fn in QUEUES:
        d=json.loads((DIR/fn).read_text())
        for x in d["candidates"]:
            country=x.get("country") or d.get("country") or ("LT" if fn.startswith("lithuania") else "")
            profile=x.get("regulator_profile") or x.get("regulatory_profile")
            rows.append({"id":x["id"],"name":x["legal_name"],"country":country,
              "profile":profile,"careers_url":x.get("careers_url"),"company_site":x.get("company_site"),
              "known_aliases":x.get("prior_source_ids",[]),"trading_name":x.get("trading_name"),"origin":fn})
    return rows
def discover():
    rows=[];errors=[]
    for country,url,pattern in INDEXES:
        try:
            links=anchors(url,get(url));base=hostkey(url);count=0
            for u,title in links:
                if hostkey(u)!=base or not re.fullmatch(pattern,urlsplit(u).path) or len(norm(title))<3 or len(title)>180:continue
                if title.casefold() in ("next","previous","careers","contacts","full list"):continue
                # Official direct profile link, not independently verified licence.
                sid="auto-"+country.lower()+"-"+hashlib.sha256(norm(title).encode()).hexdigest()[:20]
                rows.append({"id":sid,"name":title,"country":country,"profile":u.split("?")[0],"origin":url,"careers_url":None,"company_site":None,"known_aliases":[]})
                count+=1
            if count==0:raise ValueError("No profile links extracted")
        except Exception as e:errors.append({"index":url,"error":type(e).__name__+": "+str(e)[:180]})
    return rows,errors
def select(rows,active,original,registry,ledger,now,limit=50):
    names={norm(x["name"].split(" (")[0]) for x in original if x.get("name")}
    names.update(norm(x["id"].replace("-"," ")) for x in original)
    hosts={hostkey(x.get("careers_url")) for x in original if x.get("careers_url")}
    # Host-only identity is safe only for a proprietary company site;
    # shared multi-tenant ATS hosts cannot identify the employer.
    shared={"jobs.ashbyhq.com","jobs.lever.co","jobs.eu.lever.co","job-boards.greenhouse.io","boards.greenhouse.io","job-boards.eu.greenhouse.io","join.com","ats.rippling.com","jobs.smartrecruiters.com","app.screenloop.com"}
    hosts-=shared
    names.update(norm(x.get("name",x["id"])) for x in registry)
    names.update(norm(a) for x in registry for a in x.get("aliases",[]))
    hosts.update(hostkey(x.get("careers_url")) for x in registry if x.get("careers_url") and hostkey(x.get("careers_url")) not in shared)
    for r in rows:
        if r["id"] in active or r.get("known_aliases"):
            names.add(key(r))
            if r.get("trading_name"):names.add(norm(r["trading_name"]))
    grouped={}
    for r in rows:
        k=key(r)
        if len(k)<3 or r["id"] in active or r.get("known_aliases") or k in names or (r.get("trading_name") and norm(r["trading_name"]) in names):continue
        if hostkey(r.get("careers_url")) in hosts or hostkey(r.get("company_site")) in hosts:continue
        if k not in grouped:grouped[k]=dict(r)
        else:
            for f in ("careers_url","company_site","profile","trading_name"):
                if not grouped[k].get(f) and r.get(f):grouped[k][f]=r[f]
    eligible=[]
    for k,r in grouped.items():
        previous=ledger.get(k,{})
        last=previous.get("checked_at")
        if last:
            age=(now-dt.datetime.fromisoformat(last)).total_seconds()/86400
            if previous.get("status")=="TECHNICAL_PASS_REVIEW_REQUIRED" or age<30:continue
        r["key"]=k
        eligible.append(r)
    eligible.sort(key=lambda r:(r["key"] in ledger, r["country"] not in TARGET,not bool(r.get("careers_url")),not bool(r.get("profile")),r["key"]))
    return eligible[:limit],len(eligible)
def main():
    p=argparse.ArgumentParser();p.add_argument("--ledger",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--limit",type=int,default=50);p.add_argument("--offline",action="store_true");a=p.parse_args()
    if not 1<=a.limit<=50:raise ValueError("Batch limit 50")
    now=dt.datetime.now(dt.timezone.utc);ledger=json.loads(a.ledger.read_text())["records"] if a.ledger.exists() else {}
    with ZipFile(DIR/"full_original_339_sources.zip") as z:original=json.loads(z.read("fuentes.json"))["sources"]
    if hashlib.sha256((DIR/"full_original_339_sources.zip").read_bytes()).hexdigest()!="e8a08263115c4bbbaf02d4a4ae59431a7e4b16a0a7c79e339ff2f53ef9aadc02":raise ValueError("Catalog hash mismatch")
    fresh,errors=([],[]) if a.offline else discover()
    selected,pending=select(collect_queues()+fresh,set(CORE+OPTIONAL),original,load_registry(),ledger,now,a.limit)
    data={"schema":"aml339_growth_batch_v1","checked_at":now.isoformat(),"selected":selected,"eligible_pending":pending,"new_register_profiles_observed":len({r["profile"] for r in fresh}),"discovery_errors":errors}
    a.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    print("GROWTH_SELECTED",json.dumps({"selected":len(selected),"pending":pending,"profiles":data["new_register_profiles_observed"],"errors":errors},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
