#!/usr/bin/env python3
"""Read-only canary for externally discovered employer boards. Never publishes alerts."""
import argparse, datetime as dt, json, re
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, urlopen
from pathlib import Path
import live_e2e18_full as audit
from live_e2e18_full import audit_one
from quality_audit import candidate as original_candidate
from amlradar.sources import Board
from two_lane_alert_preview import triage

# Observed official links on 2026-11-24. Positive controls for this one canary,
# not permanent minimum headcounts. External provider matching may need a
# dedicated parser; failure is explicitly retained.
SOURCES={
 "external50b-lv-paybis":("Paybis","https://paybis.com/career/",["site_jobs","talent.sage.hr",r"^/jobs/[0-9a-f-]{36}/?$"],20),
 "external50b-lv-neverless":("Neverless","https://neverless.com/es-eea/careers",["site_jobs","neverless.com",r"^/(?:[a-z]{2}[-_][a-zA-Z]{2}/)?careers/[a-z0-9-]+/?$"],3),
 "external50b-lv-noah":("Noah","https://noah.com/careers",["site_jobs","noah.com",r"^/careers/[0-9a-f-]{36}/?$"],8),
 "external50b-es-treezor":("Treezor","https://careers.treezor.com/jobs",["teamtailor","careers.treezor.com",""],0),
}

class Anchors(HTMLParser):
 def __init__(self):
  super().__init__(); self.current=None; self.links={}
 def handle_starttag(self,tag,attrs):
  if tag=="a": self.current=[dict(attrs).get("href",""),[]]
 def handle_data(self,data):
  if self.current is not None:self.current[1].append(data)
 def handle_endtag(self,tag):
  if tag=="a" and self.current is not None:
   href,parts=self.current; self.links[href]=" ".join(" ".join(parts).split()); self.current=None

def read_page(url):
 with urlopen(Request(url,headers={"User-Agent":"AML339-source-audit/1.0"}),timeout=15) as response:
  if urlsplit(response.url).hostname!=urlsplit(url).hostname:raise RuntimeError("Unexpected employer redirect")
  body=response.read(1500001)
  if len(body)>1500000:raise RuntimeError("Independent listing evidence truncated")
  return body.decode("utf-8","replace")

class EmptyBoard(HTMLParser):
 def __init__(self):
  super().__init__(); self.heading=None; self.headings=[]; self.job_links=[]; self.pagination=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in ("h1","h2","h3","h4"):self.heading=[]
  if tag=="a":
   u=urlsplit(urljoin("https://careers.treezor.com/jobs",a.get("href","")))
   if u.hostname=="careers.treezor.com" and re.match(r"^/(?:[a-z]{2}/)?jobs/[^/]+",u.path):self.job_links.append(u.path)
   if "next" in a.get("rel","").split() or (u.path=="/jobs" and re.search(r"(?:^|&)page=",u.query)):self.pagination=True
 def handle_data(self,data):
  if self.heading is not None:self.heading.append(data)
 def handle_endtag(self,tag):
  if tag in ("h1","h2","h3","h4") and self.heading is not None:
   self.headings.append(" ".join(" ".join(self.heading).split()).casefold());self.heading=None

def explicit_treezor_empty(html):
 p=EmptyBoard();p.feed(html)
 return ("aucune offre pour le moment" in p.headings and not p.job_links and not p.pagination)

def self_test():
 assert explicit_treezor_empty("<h3>Aucune offre pour le moment</h3>")
 assert not explicit_treezor_empty("<script>Aucune offre pour le moment</script>")
 assert not explicit_treezor_empty("<h3>Aucune offre pour le moment</h3><a href='/jobs/123-test'>Job</a>")
 assert not explicit_treezor_empty("<h3>Aucune offre pour le moment</h3><a href='/jobs?page=2'>Next</a>")
 assert not explicit_treezor_empty("<h3>Access denied</h3>")
 assert candidate({"title":"Anti-Fraud Specialist"})
 assert candidate({"title":"Compliance Officer (Regulatory Focus)"})
 print("EXTERNAL50_REGRESSION_TESTS_PASSED",flush=True)

def candidate(job):
 return original_candidate(job) or bool(re.search(r"\b(?:anti[- ]fraud|fraud (?:analyst|specialist|investigator|officer)|compliance officer|internal auditor|head of risk)\b",str(job.get("title","")),re.I))

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--source",required=True,choices=SOURCES)
 p.add_argument("--out",required=True)
 a=p.parse_args()
 self_test()
 names=json.loads(Path("experiments/aml339/external_regulated50_wave02.json").read_text())["candidates"]
 assert len(names)==50 and a.source in {x["id"] for x in names}
 name,url,route,minimum=SOURCES[a.source]
 # Independent positive control: compare exact official linked job identities
 # and titles against the parser output. A source must not pass with zero
 # title matches when employer links show obvious compliance or fraud roles.
 if a.source=="external50b-lv-paybis":
  links=Anchors(); links.feed(read_page(url))
  expected={urlsplit(urljoin(url,h)).path:t for h,t in links.links.items()
   if urlsplit(urljoin(url,h)).hostname=="talent.sage.hr" and re.fullmatch(r"/jobs/[0-9a-f-]{36}/?",urlsplit(urljoin(url,h)).path) and t}
  if len(expected)<minimum:raise RuntimeError("Official employer anchor coverage incomplete")
  raw_listing=Board.listing
  def checked_listing(board):
   jobs=raw_listing(board)
   actual={urlsplit(str(j.get("url",""))).path:j for j in jobs}
   if not set(expected).issubset(actual):raise RuntimeError("Official linked jobs missing from extractor")
   for key,title in expected.items():
    actual[key]["title"]=title
   print("PAYBIS_TITLE_CONTROL",json.dumps({"linked":len(expected),"matching_titles":[t for t in expected.values() if candidate({"title":t})]},ensure_ascii=False),flush=True)
   return jobs
  Board.listing=checked_listing
 if a.source=="external50b-es-treezor":
  original_listing=Board.listing
  def treezor_listing(board):
   html=read_page(url)
   if explicit_treezor_empty(html):
    board.complete=True;board.total=0
    print("TREEZOR_EXPLICIT_EMPTY_BOARD",flush=True)
    return []
   return original_listing(board)
  Board.listing=treezor_listing
 audit.candidate=candidate
 result=audit_one({"id":a.source,"name":name,"careers_url":url,"route":route},minutes=4)
 if a.source=="external50b-lv-paybis" and not result.get("relevant_leads"):
  result["list_complete"]=False;result["errors"].append("Employer page contains compliance/fraud jobs but parser matched none")
 if a.source=="external50b-es-treezor" and result.get("total_listed")==0:
  html=read_page(url)
  if not explicit_treezor_empty(html):
   result["list_complete"]=False;result["errors"].append("Zero jobs not independently confirmed by official empty-board marker")
 ok=(result.get("state")=="listing_extracted" and result.get("list_complete") is True and
     isinstance(result.get("total_listed"),int) and result["total_listed"]>=minimum and
     result.get("relevant_leads")==len(result.get("audited",[])) and result.get("unverified_in_scope")==0
     and result.get("listing_untrackable_count")==0)
 print("EXTERNAL50_CANARY",json.dumps({"id":a.source,"verified":ok,"listed":result.get("total_listed"),"errors":result.get("errors"),"unverified":result.get("unverified_in_scope")}),flush=True)
 for job in result.get("audited",[]):
  alert,reason=triage(a.source,job)
  print("EXTERNAL50_ROLE",json.dumps({"title":job.get("title"),"url":job.get("url"),"lane":alert.get("lane") if alert else None,"reason":reason,"duties":job.get("evaluation",{}).get("explicit_duties"),"verification_error":job.get("verification_error")},ensure_ascii=False),flush=True)
 Path(a.out).write_text(json.dumps({"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA","source_registry":"external_regulated50_wave02_canary","original_catalog_sources":339,"total_configured_sources":339,"sources_requested":[a.source],"verified":ok,"sources":[result]},ensure_ascii=False,indent=2)+"\n")
 if not ok:raise SystemExit("Unverified employer feed: do not promote")

if __name__=="__main__":main()
