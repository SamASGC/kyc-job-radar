"""Temporary read-only official Traffit JSON shape diagnostics; only safe metadata."""
import json,urllib.request
url="https://zen.traffit.com/public/an/list/?limit=100&offset=0"
req=urllib.request.Request(url,headers={"User-Agent":"AML339-research/1.0","Accept":"application/json"})
with urllib.request.urlopen(req,timeout=15) as res:
    rows=json.loads(res.read(400000))
assert isinstance(rows,dict) and isinstance(rows.get('items'),list)
print('ZEN_LIST_META',json.dumps({'count':rows.get('count'),'length':len(rows['items']),'keys':list(rows)},ensure_ascii=False),flush=True)
rows=rows['items']
for row in rows:
    advert=row.get("advert") or {}
    vals=advert.get("values") or []
    short={str(v.get("field_id")):str(v.get("value",""))[:240] for v in vals if isinstance(v,dict)}
    print("ZEN_FIELDS",json.dumps({
      "job_id":row.get("id"),"url":row.get("url"),
      "top_keys":list(row.keys()),"advert_keys":list(advert.keys()),
      "value_ids":list(short.keys()),"values_preview":{k:v for k,v in short.items()
            if any(t in k.lower() for t in ["location","city","title","name","department",
                "workplace","employment","date","position","office","remote"])}
      ,"other_meta":{k:repr(v)[:180] for k,v in row.items()
                     if k not in ("advert","url") and isinstance(v,(str,int,bool,type(None)))}
    },ensure_ascii=False),flush=True)
