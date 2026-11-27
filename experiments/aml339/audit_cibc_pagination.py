#!/usr/bin/env python3
"""Instrument the existing approved Workday worker; do not make extra requests."""
import argparse,json,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from amlradar.sources import Board
from live_external_generic import audit_config
from external_live_registry import load_registry
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    row=next(x for x in load_registry() if x["id"]=="external-cibc")
    assert row["route"]==["workday","cibc.wd3.myworkdayjobs.com","search"]
    original=Board.js
    pages=[];seen=set()
    def traced(board,url,*args,**kwargs):
        data=original(board,url,*args,**kwargs)
        if urlsplit(url).hostname==row["route"][1] and urlsplit(url).path.endswith("/jobs") and isinstance(data,dict):
            params=args[0] if args and isinstance(args[0],dict) else {}
            postings=data.get("jobPostings",[])
            ids=[j.get("externalPath") for j in postings if isinstance(j,dict) and j.get("externalPath")]
            fresh=set(ids)-seen;seen.update(ids)
            pages.append({"offset":params.get("offset"),"limit":params.get("limit"),"total":data.get("total"),"page_count":len(postings),"identified":len(ids),"new_ids":len(fresh),"cumulative":len(seen),"page_fingerprint":hashlib.sha256(json.dumps(ids).encode()).hexdigest()[:20]})
        return data
    Board.js=traced
    try:
        r,ok=audit_config(row)
        result={"id":row["id"],"verified":ok,"listed":r.get("total_listed"),"warnings":r.get("warnings"),"errors":r.get("errors"),"pages":pages,"status":"TECHNICAL_PASS_REVIEW_REQUIRED" if ok else "INCOMPLETE"}
    except Exception as exc:
        result={"id":row["id"],"verified":False,"status":"HELD","pages":pages,"errors":[type(exc).__name__+": "+str(exc)[:240]]}
    finally:Board.js=original
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("CIBC_PAGINATION_EVIDENCE",json.dumps(result),flush=True)
if __name__=="__main__":main()
