#!/usr/bin/env python3
"""One-time audit of a public EMI export for discovering regulated firms.

The export is a SECONDARY directory. Every row stays UNVERIFIED until matched
to an official EBA/national authority licence. No regulated-status or live
job claim is made solely from this CSV.
"""
import csv,io,json,urllib.request
url="https://licensedemis.com/data/emis.csv"
req=urllib.request.Request(url,headers={"User-Agent":"AML339-source-discovery/1.0","Accept":"text/csv"})
with urllib.request.urlopen(req,timeout=25) as response:
    data=response.read(3000000)
    print("EMI_EXPORT_HTTP",json.dumps({"status":response.status,
       "url":response.url,"type":response.headers.get("Content-Type"),"bytes":len(data)}),flush=True)
text=data.decode("utf-8-sig")
print("EMI_EXPORT_HEAD",json.dumps(text.splitlines()[:8],ensure_ascii=False),flush=True)
rows=list(csv.DictReader(line for line in text.splitlines() if not line.startswith("#")))
print("EMI_EXPORT_SCHEMA",json.dumps({"fields":list(rows[0]) if rows else [],
  "count":len(rows)}),flush=True)
from collections import Counter
print("EMI_EXPORT_DISTRIBUTION",json.dumps({
    "countries":Counter(r.get("country","") for r in rows),
    "statuses":Counter(r.get("operational_status","") for r in rows),
    "licence_types":Counter(r.get("license_type","") for r in rows)
},ensure_ascii=False,default=dict),flush=True)
selected=[r for r in rows if r.get("country","") in ("LT","MT","LU","EE","ES","IE","NL","BE","LV","PL","PT","FR","DE")]
print("EMI_EXPORT_SAMPLE",json.dumps(selected[:36],ensure_ascii=False),flush=True)
