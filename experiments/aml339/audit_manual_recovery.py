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

from live_external_generic import audit_config
from external_live_registry import load_registry

# URLs observed on the official employer portals, never inferred ATS slugs.
# These are research candidates only; licence, hiring-entity and skills review
# remains mandatory even when the technical audit passes.
ROWS = {
 "reg50-connectpay": {"name":"ConnectPay","aliases":["connectpay"],"careers_url":"https://connectpay.com/career/","marker":"currently, we don't have any available positions","heading":"always eager to connect","regulator":"https://www.lb.lt/en/sfi-financial-market-participants//uab-connectpay"},
 "lt-emi-research-uab-blue-emi-lt": {"name":"Blue EMI","aliases":["blue emi","blueemi"],"careers_url":"https://blueemi.com/careers/","marker":"we don't have any open roles at the moment","heading":"open positions","regulator":"https://www.lb.lt/en/sfi-financial-market-participants/uab-blue-emi-lt"},
 "reg100-lt-uab-monavate": {"name":"Monavate","aliases":["monavate"],"careers_url":"https://www.monavate.com/careers","marker":"there are currently no open roles","heading":"open roles","regulator":"https://www.lb.lt/en/sfi-financial-market-participants/uab-monavate"},
 "reg50-payhound": {"name":"Payhound","aliases":["payhound"],"careers_url":"https://payhound.com/jobs","marker":"no items found.","heading":"current openings"},
 "manual-lt-bankera-pervesk": {"name":"Bankera / Pervesk","aliases":["bankera","pervesk","spectrocoin","bankinglab","autokyc"],"careers_url":"https://careers.bankera.com/","route":["site_jobs","careers.bankera.com",r"^/en/(?:legal-compliance|business-development|cybersecurity|it|customer-support|marketing|finance-banking|office-administration|design|content-copywriting|human-resources)/[^/]+/?$"],"job_pattern":r"^/en/(?:legal-compliance|business-development|cybersecurity|it|customer-support|marketing|finance-banking|office-administration|design|content-copywriting|human-resources)/[^/]+/?$","regulator":"https://www.lb.lt/en/sfi-financial-market-participants//uab-pervesk","skill_evidence":"https://careers.bankera.com/en/legal-compliance/KYC-Specialist-(Clients-Onboarding-Team)/"},
 "manual-lu-ibanfirst": {"name":"iBanFirst","aliases":["ibanfirst","iban first"],"careers_url":"https://careers.ibanfirst.com/","route":["site_jobs","careers.ibanfirst.com",r"^/o/[a-z0-9-]+/?$"],"job_pattern":r"^/o/[a-z0-9-]+/?$","skill_evidence":"https://careers.ibanfirst.com/o/senior-amlkyc-onboarding-analyst-funds-complex-structures"},
 "manual-ee-esto": {"name":"ESTO","aliases":["esto","esto as"],"careers_url":"https://jobs.esto.eu/jobs","route":["teamtailor","jobs.esto.eu","/jobs"],"job_pattern":r"^/jobs/[0-9]+-[^/]+/?$","regulator":"https://www.fi.ee/en/banking-and-credit/banking-and-credit/creditors/licensed-creditors-estonia/esto","skill_evidence":"https://jobs.esto.eu/jobs/8695179-group-head-of-compliance"},
 "manual-ee-bigbank": {"name":"Bigbank","aliases":["bigbank","big bank"],"careers_url":"https://jobs.bigbank.eu/open-positions/","detail_host":"bigbank.teamdash.com","job_pattern":r"^/p/job/[A-Za-z0-9]+/[^/]+/?$","regulator":"https://www.fi.ee/en/banking-and-credit/banking-and-credit/credit-institutions/credit-institutions","skill_evidence":"https://bigbank.teamdash.com/p/job/c4AG5xxH/aml-specialist"},
}
def empty_proof(p,t,marker,heading,url):
    if not marker or marker not in t or heading not in t:return False
    # A marker in generic marketing content is insufficient. Require the
    # official careers section, with no separate job-detail or ATS links.
    if t.index(marker)<t.index(heading) or t.index(marker)-t.index(heading)>400:return False
    for href,title in p.anchors.links.items():
        u=urlsplit(urljoin(url,href)); path=u.path.casefold()
        if re.search(r"(?:^|[&;])(?:page|offset|start|cursor)=",u.query,re.I) or re.fullmatch(r"\s*(?:next|load more|show more)\s*",title,re.I):return False
        if re.search(r"/(?:jobs|careers|career|vacancies|positions)/(?!$)[^/]+",path) and u.path.rstrip("/")!=urlsplit(url).path.rstrip("/"):return False
        if re.search(r"greenhouse|lever\.co|ashbyhq|bamboohr|screenloop|recruitee|personio|workable|teamtailor|rippling|join\.com",u.hostname or "",re.I):return False
    if any(re.search(r"greenhouse|lever\.co|ashbyhq|bamboohr|screenloop|recruitee|personio|workable|teamtailor|rippling",x,re.I) for x in p.embeds):return False
    return True


def identity_matches(row, original, active):
    def compact(s):return re.sub(r"[^a-z0-9]","",str(s).casefold())
    aliases={compact(x) for x in row["aliases"]}
    hosts={urlsplit(row["careers_url"]).hostname,row.get("detail_host")}-{None}
    matches=[]
    for old in original+active:
        label=" ".join(str(old.get(k,"")) for k in ("name","id","careers_url"))
        tokens={compact(old.get("name","")),compact(old.get("id",""))}
        host=urlsplit(old.get("careers_url") or "").hostname
        # Short aliases such as ESTO must match whole tokens, not substrings.
        found=any(re.search(r"(?<![a-z0-9])"+re.escape(a)+r"(?![a-z0-9])",label,re.I) for a in row["aliases"])
        if found or aliases&tokens or host in hosts or (row.get("route") and old.get("route")==row["route"]):
            matches.append(old["id"])
    return sorted(set(matches))

def audit_empty(row):
    url=row["careers_url"]
    p,t=parse(get(url))
    if not empty_proof(p,t,row["marker"],row["heading"],url):
        raise ValueError("Explicit empty-board evidence absent or conflicts with live links")
    original=Board.listing
    def listing(board):
        board.complete=True
        board.total=0
        return []
    Board.listing=listing
    try:r=audit_one({"id":row["id"],"name":row["name"],"careers_url":url,"route":["site_jobs",urlsplit(url).hostname,r"^/jobs/[^/]+/?$"]},minutes=3)
    finally:Board.listing=original
    return r,r["state"]=="listing_extracted" and r["list_complete"] is True and r["total_listed"]==0

def crosshost_diagnostic(row):
    # The Teamdash detail identities are independently employer-linked.
    # Do not assert completeness from a cross-host anchor snapshot alone.
    url=row["careers_url"];p,t=parse(get(url));rx=re.compile(row["job_pattern"])
    jobs={}
    for href,title in p.anchors.links.items():
        u=urlsplit(urljoin(url,href))
        if u.scheme=="https" and u.hostname==row["detail_host"] and rx.fullmatch(u.path) and title:
            jobs[u.path.rstrip("/")]=title
    if not jobs:raise ValueError("No official linked Teamdash jobs")
    return {"linked_jobs":jobs,"status":"CROSSHOST_COMPLETENESS_REVIEW_REQUIRED"}

def selftest():
    p,t=parse("<h2>Open positions</h2><p>We don't have any open roles at the moment</p>")
    assert empty_proof(p,t,"we don't have any open roles at the moment","open positions","https://example.com/careers/")
    p,t=parse("<h2>Open positions</h2><p>We don't have any open roles at the moment</p><a href='/jobs/123'>AML</a>")
    assert not empty_proof(p,t,"we don't have any open roles at the moment","open positions","https://example.com/careers/")
    p,t=parse("<h2>Open positions</h2><script>We don't have any open roles at the moment</script>")
    assert not empty_proof(p,t,"we don't have any open roles at the moment","open positions","https://example.com/careers/")
    assert identity_matches(ROWS["manual-ee-esto"],[{"id":"esto","name":"ESTO AS"}],[])==["esto"]
    assert not identity_matches(ROWS["manual-ee-esto"],[{"id":"test","name":"Testosterone"}],[])
    assert identity_matches(ROWS["manual-lt-bankera-pervesk"],[{"id":"spectrocoin","name":"SpectroCoin"}],[])==["spectrocoin"]

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",choices=ROWS,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
    selftest()
    row=dict(ROWS[a.source],id=a.source)
    out={"id":a.source,"config":row,"verified":False,"status":"FAILED"}
    try:
        original=json.loads(Path("fuentes.json").read_text())["sources"]
        assert len(original)==339
        matches=identity_matches(row,original,load_registry())
        out["identity_matches"]=matches
        if matches:out["status"]="DUPLICATE_OR_ALIAS_REVIEW"
        elif row.get("detail_host"):out.update(crosshost_diagnostic(row))
        else:
            result,ok=(audit_empty(row) if row.get("marker") else audit_config(row))
            out.update(audit=result,verified=ok,status="TECHNICAL_PASS_REVIEW_REQUIRED" if ok else "FAILED")
    except Exception as e:out.update(error=type(e).__name__+": "+str(e)[:300])
    a.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("MANUAL_BATCH_RESULT",json.dumps({k:v for k,v in out.items() if k not in ("config","audit","linked_jobs")}|{"listed":out.get("audit",{}).get("total_listed"),"linked":len(out.get("linked_jobs",{})),"errors":out.get("audit",{}).get("errors",[])}),flush=True)
if __name__=="__main__":main()
