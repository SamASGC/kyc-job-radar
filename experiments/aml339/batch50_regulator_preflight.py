#!/usr/bin/env python3
"""Read-only preflight of regulator records + 339 source catalog. No live changes."""
import json,urllib.request,zipfile,io,xml.etree.ElementTree as ET,re
from pathlib import Path

REG_URL="https://www.lb.lt/en/charts/electronic-money-institutions-in-lithuania-1?export=xlsx&version=10"
def load_xlsx(url):
  req=urllib.request.Request(url,headers={"User-Agent":"AML339-regulatory-research/1.0",
      "Accept":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
  with urllib.request.urlopen(req,timeout=22) as resp:
    raw=resp.read(2500000)
    print("REGULATORY_EXPORT_HTTP",resp.status,resp.headers.get("Content-Type"),len(raw))
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
    ns={"x":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strs=[]
    if "xl/sharedStrings.xml" in z.namelist():
      root=ET.fromstring(z.read("xl/sharedStrings.xml"))
      for si in root.findall("x:si",ns):
        strs.append("".join(t.text or "" for t in si.findall(".//x:t",ns)))
    sheets=[name for name in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml",name)]
    print("REGULATORY_EXPORT_SHEETS",sheets)
    for sn in sheets[:3]:
      root=ET.fromstring(z.read(sn))
      rows=[]
      for row in root.findall(".//x:sheetData/x:row",ns):
        vals=[]
        for c in row.findall("x:c",ns):
          v=c.find("x:v",ns)
          v=v.text if v is not None else ""
          if c.get("t")=="s" and v:v=strs[int(v)]
          if c.get("t")=="inlineStr":v="".join(x.text or "" for x in c.findall(".//x:t",ns))
          vals.append([c.get("r"),v])
        rows.append(vals)
      print("REGULATORY_EXPORT_ROWS",sn,len(rows),json.dumps(rows[:7],ensure_ascii=False)[:8000])
    return sheets

def catalog():
  with zipfile.ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
    rows=json.loads(z.read("fuentes.json"))["sources"]
  assert len(rows)==len({x["id"] for x in rows})==339
  from collections import Counter
  print("CATALOG_ROUTES",json.dumps(Counter(x["route"][0] for x in rows),ensure_ascii=False))
  for i,x in enumerate(rows):
    print("CATALOG_SOURCE",json.dumps({"id":x["id"],"name":x["name"],
      "url":x.get("careers_url"),"route":x.get("route",[])[:2]},ensure_ascii=False))
  return rows
if __name__=="__main__":
  catalog()
  try:load_xlsx(REG_URL)
  except Exception as e:print("REGULATORY_EXPORT_ERROR",type(e).__name__,str(e)[:500])
