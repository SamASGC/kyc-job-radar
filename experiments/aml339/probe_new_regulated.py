#!/usr/bin/env python3
"""READ-ONLY source adapter discovery for candidate regulated EMIs NOT in pinned 339.

Zero production writes, no applications, no source counts guessed. Queries
public official ATS endpoints only with a small bounded HTTP budget.
"""
import json
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


def get(url, timeout=12):
    req=urllib.request.Request(url,headers={"User-Agent":"AML339-independent-research/1.0","Accept":"application/json, text/html;q=0.8"})
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        data=resp.read(450000)
        return resp.getcode(),resp.headers.get("Content-Type",""),data.decode("utf-8",errors="replace")


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            d=dict(attrs)
            if "href" in d:self.links.append(d["href"])


def main():
    targets={
        "trumia-gh-eu":"https://boards-api.eu.greenhouse.io/v1/boards/trumia/jobs?content=true",
        "trumia-gh":"https://boards-api.greenhouse.io/v1/boards/trumia/jobs?content=true",
        "zen-traffit-published":"https://zen.traffit.com/public/job_posts/published",
        "zen-traffit-careers":"https://zen.traffit.com/career/",
        "monemon-careers":"https://monemon.com/careers",
        "stanhope-careers":"https://stanhopefinancial.com/careers",
    }
    output={}
    for name,url in targets.items():
        result={"url":url}
        try:
            status,ctype,raw=get(url)
            result.update(status=status,ctype=ctype,length=len(raw),preview=raw[:400])
            if "json" in ctype or raw.lstrip().startswith(("{","[")):
                obj=json.loads(raw)
                result["json_type"]=type(obj).__name__
                if isinstance(obj,dict):
                    result["json_keys"]=list(obj)[:25]
                    result["meta"]={k:obj[k] for k in list(obj)[:8] if isinstance(obj[k],(int,str,float,bool,type(None)))}
                    for k,v in obj.items():
                        if isinstance(v,list):
                            result["list_field"]=k
                            result["list_count"]=len(v)
                            result["sample"]=v[:2]
                            break
                if isinstance(obj,list):
                    result["list_count"]=len(obj)
                    result["sample"]=obj[:2]
            else:
                parser=Links()
                parser.feed(raw)
                result["links"]=parser.links[:20]
        except Exception as e:
            result["error"]=type(e).__name__+": "+str(e)[:400]
        output[name]=result
        print("NEW_REGULATED_SOURCE_PROBE",json.dumps({name:result},ensure_ascii=False)[:12500],flush=True)
        time.sleep(.3)
    Path("regulated_new_source_probe.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":main()
