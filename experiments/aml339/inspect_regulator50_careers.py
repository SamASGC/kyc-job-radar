#!/usr/bin/env python3
"""Discover real, employer-linked job posting paths on ten official careers pages.

Read-only diagnostics. HTTP 200 or the word "career" are not job-feed evidence.
Never publish an employer until its listing and role details pass full auditing.
"""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
import json,re

class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.open=[];self.pairs=[];self.ldjson=[];self.json_mode=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="a":self.open.append({"href":a.get("href",""),"txt":[]})
        elif tag=="script" and a.get("type")=="application/ld+json":
            self.json_mode=True;self.ldjson.append("")
    def handle_endtag(self,tag):
        if tag=="a" and self.open:self.pairs.append(self.open.pop())
        if tag=="script":self.json_mode=False
    def handle_data(self,data):
        if self.open:self.open[-1]["txt"].append(data)
        if self.json_mode:self.ldjson[-1]+=data

def main():
    data=json.loads(Path("experiments/aml339/regulator50_external_candidates.json").read_text())
    for c in data["candidates"]:
        if not c["careers_url"]:continue
        url=c["careers_url"]
        try:
            req=Request(url,headers={"User-Agent":"AML339-regulated-careers-research/1.0"})
            with urlopen(req,timeout=15) as r:
                actual=r.url
                html=r.read(650000).decode("utf-8","replace")
            parser=Links();parser.feed(html)
            seen=set();best=[]
            for link in parser.pairs:
                href=urljoin(actual,link["href"])
                t=" ".join(" ".join(link["txt"]).split())[:100]
                host=urlsplit(href).netloc.lower()
                if href in seen or not href.startswith("https:"):continue
                seen.add(href)
                if re.search(r"/(job|career|position|vacanc|openings|opportunit)|\b(AML|KYC|screening|compliance|risk|fraud|fincrime)\b",href+" "+t,re.I):
                    best.append({"href":href,"text":t,"host":host})
            dataout={"id":c["id"],"status":200,"last_url":actual,
                "all_links":len(parser.pairs),"matching_links":len(best),
                "example_links":best[:35],"jsonld_count":len(parser.ldjson),
                "jobposting_jsonld":sum("JobPosting" in x for x in parser.ldjson)}
        except Exception as e:
            dataout={"id":c["id"],"error":type(e).__name__+": "+str(e)[:160]}
        print("REG50_OFFICIAL_CAREERS_LINKS",json.dumps(dataout,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
