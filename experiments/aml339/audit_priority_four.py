#!/usr/bin/env python3
"""Read-only public evidence probes for four priority employer portals.
No enrollment, browser login, internal API calls, form submissions or closure claims.
"""
import argparse,json,re
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from urllib.parse import urlsplit,urljoin
from pathlib import Path
import xml.etree.ElementTree as ET

SOURCES={
 "banque-de-luxembourg": {
  "listing":"https://jobs.banquedeluxembourg.com/offre-de-emploi/liste-toutes-offres.aspx",
  "rss_index":"https://jobs.banquedeluxembourg.com/offre-de-emploi/tous-les-flux-rss.aspx",
  "sample":"https://jobs.banquedeluxembourg.com/offre-de-emploi/emploi-aml-compliance-analyst-h-f-_1226.aspx",
  "pattern":r"^/offre-de-emploi/emploi-[^/]+_[0-9]+\.aspx$"},
 "advanzia": {
  "listing":"https://www.advanzia.com/en/careers",
  "sample":"https://www.advanzia.com/en/job/risk-management-officer",
  "pattern":r"^/en/job/[^/]+/?$"},
 "csc":{
  "listing":"https://www.cscglobal.com/service/careers/global-career-opportunities/",
  "board":"https://hczw.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?location=Luxembourg&locationId=300000000361571&locationLevel=country&mode=location",
  "pattern":r"^/hcmUI/CandidateExperience/en/sites/CX_1001/job/[0-9]+/?$"},
 "danske-bank":{
  "listing":"https://danskebank.com/careers/apply",
  "board":"https://ejqi.fa.ocs.oraclecloud.eu/hcmUI/CandidateExperience/en/sites/CX_1001/jobs",
  "pattern":r"^/hcmUI/CandidateExperience/en/sites/CX_1001/job/[0-9]+/?$"}
}
class Page(HTMLParser):
 def __init__(self):
  super().__init__();self.links=[];self.controls=[];self.scripts=[];self.text=[];self.invisible=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in ("script","style"):self.invisible+=1
  if tag=="a" and a.get("href"):self.links.append(a["href"])
  if tag=="script" and a.get("src"):self.scripts.append(a["src"])
  if tag in ("input","button"):
   # Never export hidden field values, cookies, tokens or user inputs.
   if a.get("type","").lower() not in ("hidden","password"):
    vals={k:str(a[k])[:180] for k in ("type","name","id","title","aria-label") if a.get(k)}
    if a.get("type","").lower() in ("submit","button","image") and a.get("value"):vals["label"]=str(a["value"])[:100]
    if re.search(r"postul|candid|apply|application|submit",str(vals),re.I):self.controls.append(vals)
 def handle_endtag(self,tag):
  if tag in ("script","style"):self.invisible=max(0,self.invisible-1)
 def handle_data(self,data):
  if not self.invisible:self.text.append(data)
def fetch(url):
 with urlopen(Request(url,headers={"User-Agent":"AML339-source-audit/1.0"}),timeout=15) as res:
  if urlsplit(res.url).hostname!=urlsplit(url).hostname:raise ValueError("Unexpected cross-host redirect")
  raw=res.read(2000001)
  if len(raw)>2000000:raise ValueError("Response exceeds bounded probe")
  return raw,res.url
def page(url):
 raw,final=fetch(url);p=Page();p.feed(raw.decode("utf-8","replace"));return p,final
def links(p,base,host,pattern):
 return sorted({urljoin(base,h).split("#")[0] for h in p.links if urlsplit(urljoin(base,h)).scheme=="https" and urlsplit(urljoin(base,h)).hostname==host and re.fullmatch(pattern,urlsplit(urljoin(base,h)).path)})
def probe(sid):
 cfg=SOURCES[sid];result={"id":sid,"verified":False,"status":"DIAGNOSTIC_ONLY","evidence":{}}
 e=result["evidence"];p,base=page(cfg["listing"]);host=urlsplit(cfg.get("board",base)).hostname
 e["official_listing_links"]=links(p,base,host,cfg["pattern"])
 e["listing_script_count"]=len(p.scripts)
 if sid=="banque-de-luxembourg":
  totals={int(x) for x in re.findall(r"Nombre de r[ée]sultats\s*:\s*(\d+)\s*offre", " ".join(p.text),re.I)}
  e["declared_totals"]=sorted(totals)
  rp,rb=page(cfg["rss_index"])
  feeds=sorted({urljoin(rb,h) for h in rp.links if urlsplit(urljoin(rb,h)).hostname==host and urlsplit(urljoin(rb,h)).path.lower()=="/handlers/offerrss.ashx" and urlsplit(urljoin(rb,h)).query.lower()=="lcid=1036"})
  if len(feeds)==1:
   raw,_=fetch(feeds[0])
   if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():raise ValueError("Unsafe XML")
   root=ET.fromstring(raw);items=root.findall("./channel/item")
   ids={urlsplit(urljoin(base,(i.findtext("link") or "").strip())).path for i in items if urlsplit(urljoin(base,(i.findtext("link") or "").strip())).hostname==host and re.fullmatch(cfg["pattern"],urlsplit(urljoin(base,(i.findtext("link") or "").strip())).path)}
   e.update(rss_url=feeds[0],rss_item_count=len(items),rss_unique_job_count=len(ids),rss_matches_declared_count=(len(totals)==1 and len(ids)==len(items)==next(iter(totals)) and len(items)>0))
  else:e["rss_status"]="No unique official unfiltered feed link"
 if "sample" in cfg:
  detail,_=page(cfg["sample"]);e["sample_url"]=cfg["sample"];e["application_controls"]=detail.controls[:25]
 if "board" in cfg:
  board,bbase=page(cfg["board"]);e["board_url"]=bbase;e["board_visible_job_links"]=links(board,bbase,host,cfg["pattern"]);e["board_script_count"]=len(board.scripts)
  e["next_step"]="Need public rendered listing with explicit total/pagination and live application validation; do not call Oracle internal-use API."
 return result
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--source",choices=SOURCES,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args()
 try:r=probe(a.source)
 except Exception as exc:r={"id":a.source,"verified":False,"status":"HELD","error":type(exc).__name__+": "+str(exc)[:240]}
 a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
 print("PRIORITY_PUBLIC_EVIDENCE",json.dumps(r,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
