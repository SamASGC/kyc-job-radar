#!/usr/bin/env python3
"""Daily live audit of previously proven, enrolled original catalog sources."""
import argparse,datetime as dt,json
from pathlib import Path
from external_live_registry import ids
from live_e2e18_full import audit_one
from amlradar.sources import Board
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from live_external50_wave02 import read_page
import re

HOST="jobs.banquedeluxembourg.com"
PATH=re.compile(r"^/offre-de-emploi/emploi-[^/]+_([0-9]+)\.aspx$")
CLOSED=re.compile(r"cette offre n.est plus disponible|cette offre est pourvue|offre expir[ée]e|no longer accepting applications|job is no longer available",re.I)
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.form=None;self.controls=[];self.headings=[];self.heading=None;self.text=[];self.invisible=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ("script","style"):self.invisible+=1
        if tag=="form":self.form={"method":a.get("method","get").lower(),"action":a.get("action","")}
        if tag in ("h1","h2"):self.heading=[]
        if tag=="input" and self.form is not None:
            name=a.get("name","");ident=a.get("id","")
            if (a.get("type","").lower()=="submit" and a.get("value","").strip().casefold()=="postuler"
                and re.fullmatch(r"ctl00\$ctl00\$corpsRoot\$corps\$bt_Postuler(?:_Haut)?",name)
                and re.fullmatch(r"ctl00_ctl00_corpsRoot_corps_bt_Postuler(?:_Haut)?",ident)):
                self.controls.append({**self.form,"id":ident,"disabled":("disabled" in a or "hidden" in a or a.get("aria-disabled")=="true" or a.get("aria-hidden")=="true" or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden",a.get("style",""),re.I)))})
    def handle_endtag(self,tag):
        if tag in ("script","style"):self.invisible=max(0,self.invisible-1)
        if tag=="form":self.form=None
        if tag in ("h1","h2") and self.heading is not None:
            self.headings.append(" ".join(" ".join(self.heading).split()));self.heading=None
    def handle_data(self,data):
        if not self.invisible:
            self.text.append(data)
            if self.heading is not None:self.heading.append(data)
def job_id(url):
    u=urlsplit(url);m=PATH.fullmatch(u.path)
    return m[1] if u.scheme=="https" and u.netloc==HOST and m else None
def inspect_detail(html,url,title):
    p=Page();p.feed(html);expected=job_id(url)
    controls=[]
    for c in p.controls:
        action=urljoin(url,c["action"] or url)
        dest=urlsplit(action)
        controls.append({"id":c["id"],"method":c["method"],"disabled":c["disabled"],"same_host":dest.scheme=="https" and dest.netloc==HOST,"action_path":dest.path if dest.netloc==HOST else None,"same_job":bool(expected and job_id(action)==expected)})
    title_ok=bool(title and any(" ".join(title.split()).casefold() in h.casefold() for h in p.headings))
    closed=bool(CLOSED.search(" ".join(p.text)))
    enabled=any(c["same_job"] and c["same_host"] and c["method"]=="post" and not c["disabled"] for c in controls)
    return {"job_id":expected,"title_confirmed":title_ok,"closed_marker":closed,"controls":controls,"form_evidence":bool(expected and title_ok and enabled and not closed)}
def self_test():
    url="https://"+HOST+"/offre-de-emploi/emploi-test_123.aspx"
    control='<input type="submit" name="ctl00$ctl00$corpsRoot$corps$bt_Postuler" id="ctl00_ctl00_corpsRoot_corps_bt_Postuler" value="Postuler">'
    html='<h1>AML Analyst</h1><form method="post">'+control+'</form>'
    assert inspect_detail(html,url,"AML Analyst")["form_evidence"]
    for bad in [html.replace('type="submit"','type="submit" disabled'),html.replace('method="post"','method="post" action="https://example.org/"'),html+"Cette offre n'est plus disponible",html.replace("AML Analyst","Different job")]:
        assert not inspect_detail(bad,url,"AML Analyst")["form_evidence"]

def audit_banque(row):
    """Recognize the employer's actual same-page application entrypoint.
    No form is submitted. The offer page is the candidate-facing apply URL.
    Only the exact missing-link failure can be recovered; all other errors stay fatal.
    """
    assert row["id"]=="banque-de-luxembourg"
    self_test()
    original_verify=Board.verify
    def verify(board,job):
        try:return original_verify(board,job)
        except Exception as exc:
            if type(exc).__name__!="SourceError" or str(exc)!="No se encontró acceso directo a candidatura":
                raise
            url=job.get("url","")
            if not job_id(url):raise
            evidence=inspect_detail(read_page(url),url,job.get("title",""))
            if not evidence["form_evidence"]:raise
            if len(str(job.get("description","")))<200:raise
            job["apply_url"]=url
            return None
    Board.verify=verify
    try:r=audit_one(row,minutes=4)
    finally:Board.verify=original_verify
    p=Page();p.feed(read_page("https://"+HOST+"/offre-de-emploi/liste-toutes-offres.aspx"))
    totals={int(x) for x in re.findall(r"Nombre de r[ée]sultats\s*:\s*(\d+)\s*offre"," ".join(p.text),re.I)}
    n=r.get("total_listed")
    if type(n) is not int or n<=0 or totals!={n} or len(r.get("listing_role_keys",[]))!=n:
        r.update(state="listing_failed",list_complete=False)
        r.setdefault("errors",[]).append("Banque de Luxembourg declared count/unique role keys mismatch")
    return r


def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True,choices=ids(catalog=True));p.add_argument("--out",required=True);a=p.parse_args()
    catalog=Path("fuentes.json")
    original=catalog.read_bytes()
    rows=json.loads(original)["sources"]; by={x["id"]:x for x in rows}
    if len(rows)!=339 or len(by)!=339 or not set(ids(catalog=True)).issubset(by):raise ValueError("Original catalog identity mismatch")
    row=by[a.source]
    if "workable" in str(row.get("route",[])).lower():raise ValueError("Blocked provider not enrolled")
    r=audit_banque(row) if a.source=="banque-de-luxembourg" else audit_one(row,minutes=4)
    if catalog.read_bytes()!=original:raise ValueError("Catalog mutated during audit")
    ok=(r.get("state")=="listing_extracted" and r.get("list_complete") is True
        and type(r.get("total_listed")) is int and r["total_listed"]>0
        and r.get("relevant_leads")==len(r.get("audited",[])) and r.get("unverified_in_scope")==0
        and r.get("listing_untrackable_count")==0)
    if not ok:r.update(state="listing_failed",list_complete=False)
    envelope={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA","source_registry":"original_339","total_configured_sources":339,"sources_requested":[a.source],"verified":ok,"sources":[r]}
    Path(a.out).write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+"\n")
    print("CATALOG_REGISTRY_AUDIT",json.dumps({"id":a.source,"verified":ok,"listed":r.get("total_listed"),"errors":r.get("errors")}),flush=True)
    if not ok:raise SystemExit("Incomplete or unproven empty source")
if __name__=="__main__":main()
