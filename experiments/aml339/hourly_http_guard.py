#!/usr/bin/env python3
"""Guard urllib HTTP calls in AML339 source workers and persist provider Retry-After.
A paused host is never retried by this worker, and a pause is not a job closure.
The separate original radar has its own scheduling and request controls.
"""
import argparse,datetime as dt,json,runpy,sys
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import HTTPError
import urllib.request as ur

UTC=dt.timezone.utc
def now():return dt.datetime.now(UTC)
def parse_time(value):
    stamp=dt.datetime.fromisoformat(value)
    if stamp.tzinfo is None:raise ValueError("Timezone required")
    return stamp
def until_from(headers,stamp):
    val=(headers.get("Retry-After") if headers else None)
    if val:
        try:
            if val.strip().isdigit():deadline=stamp+dt.timedelta(seconds=int(val))
            else:
                deadline=parsedate_to_datetime(val)
                if deadline.tzinfo is None:deadline=deadline.replace(tzinfo=UTC)
            return max(deadline,stamp+dt.timedelta(minutes=5))+dt.timedelta(seconds=10)
        except (ValueError,TypeError,OverflowError):pass
    # Unknown Retry-After: conservative 24-hour pause.
    return stamp+dt.timedelta(hours=24)
def load(path):
    if not path.exists():return {}
    doc=json.loads(path.read_text())
    if doc.get("schema")!="aml339_http_pause_v1" or not isinstance(doc.get("hosts"),dict):raise ValueError("Invalid cooldown ledger")
    for host,record in doc["hosts"].items():
        if not host or "/" in host or not isinstance(record,dict):raise ValueError("Invalid cooldown entry")
        parse_time(record["until"])
    return doc["hosts"]
def merge(prior,receipts,stamp):
    result={h:r for h,r in prior.items() if parse_time(r["until"])>stamp}
    for entries in receipts:
        for h,r in entries.items():
            if parse_time(r["until"])>stamp and (h not in result or parse_time(r["until"])>parse_time(result[h]["until"])):
                result[h]=r
    return result
def save(path,hosts):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"schema":"aml339_http_pause_v1","hosts":hosts},sort_keys=True,indent=2)+"\n")
    tmp.replace(path)
class PausedHost(RuntimeError):pass
class Guard:
    def __init__(self,prior,out):
        self.prior=prior;self.out=out;self.new={}
    def request(self,original,url,*args,**kw):
        raw=url.full_url if hasattr(url,"full_url") else str(url)
        host=(urlsplit(raw).hostname or "").lower()
        stamp=now()
        for h in (host,):
            entries=[x[h] for x in (self.prior,self.new) if h in x]
            if any(parse_time(r["until"])>stamp for r in entries):
                raise PausedHost("Provider cooldown active: "+h)
        try:return original(url,*args,**kw)
        except HTTPError as e:
            if e.code==429 or (e.code==503 and e.headers and e.headers.get("Retry-After")):
                final=(urlsplit(e.url).hostname or host).lower()
                end=until_from(e.headers,stamp)
                for h in {host,final}-{""}:
                    record={"until":end.isoformat(),"status":e.code}
                    if h not in self.new or parse_time(self.new[h]["until"])<end:self.new[h]=record
                save(self.out,self.new)
                # Do not let a generic HTTP client immediately retry 429.
                raise PausedHost("HTTP "+str(e.code)+"; provider paused until "+end.isoformat()) from e
            raise
def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    run=sub.add_parser("run");run.add_argument("--prior",type=Path,required=True);run.add_argument("--receipt",type=Path,required=True);run.add_argument("script");run.add_argument("args",nargs=argparse.REMAINDER)
    combine=sub.add_parser("merge");combine.add_argument("--prior",type=Path,required=True);combine.add_argument("--receipts",type=Path,required=True);combine.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.mode=="merge":
        save(a.out,merge(load(a.prior),[load(x) for x in a.receipts.rglob("http_pause_*.json")],now()));return
    if not a.prior.is_file():raise ValueError("Missing cooldown snapshot")
    guard=Guard(load(a.prior),a.receipt)
    save(a.receipt,{})
    original=ur.urlopen
    ur.urlopen=lambda url,*args,**kw:guard.request(original,url,*args,**kw)
    # Also cover explicit build_opener/open calls and redirect targets.
    original_open=ur.OpenerDirector.open
    def guarded_open(self,url,*args,**kw):
        return guard.request(lambda u,*aa,**kk:original_open(self,u,*aa,**kk),url,*args,**kw)
    ur.OpenerDirector.open=guarded_open
    # urllib's redirect handler invokes parent.open; redirected hosts are checked too.
    script=Path(a.script).resolve()
    sys.path.insert(0,str(script.parent));sys.argv=[str(script),*a.args]
    runpy.run_path(str(script),run_name="__main__")
if __name__=="__main__":main()
