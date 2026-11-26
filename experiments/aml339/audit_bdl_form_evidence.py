#!/usr/bin/env python3
"""Investigate Talentsoft ASP.NET application controls without submitting forms.
Research evidence only; never turns a failed production application check into a pass.
"""
import argparse,json,re,time
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from live_e2e18_full import audit_one
from live_external50_wave02 import read_page
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
def main():
    a=argparse.ArgumentParser();a.add_argument("--out",type=Path,required=True);args=a.parse_args();self_test()
    cat=json.loads(Path("fuentes.json").read_text())["sources"]
    assert len(cat)==len({r["id"] for r in cat})==339
    row=next(r for r in cat if r["id"]=="banque-de-luxembourg")
    result={"id":row["id"],"verified":False,"status":"INCOMPLETE","details":[]}
    try:
        # Keep the existing audit and record its actual failures without replacing them.
        r=audit_one(row,minutes=4);n=r.get("total_listed")
        landing=read_page("https://"+HOST+"/offre-de-emploi/liste-toutes-offres.aspx")
        p=Page();p.feed(landing)
        totals={int(x) for x in re.findall(r"Nombre de r[ée]sultats\s*:\s*(\d+)\s*offre"," ".join(p.text),re.I)}
        complete=(r.get("state")=="listing_extracted" and r.get("list_complete") is True
            and type(n) is int and n>0 and totals=={n}
            and len(r.get("listing_role_keys",[]))==n and r.get("listing_untrackable_count")==0
            and r.get("relevant_leads")==len(r.get("audited",[])))
        result.update(listed=n,declared_totals=sorted(totals),listing_complete=complete,relevant=r.get("relevant_leads"),original_unverified=r.get("unverified_in_scope"))
        if not complete:raise ValueError("Existing listing and declared total not complete")
        deadline=time.monotonic()+120
        for item in r["audited"]:
            if time.monotonic()>deadline:raise RuntimeError("Independent detail evidence deadline")
            if not job_id(item.get("url","")):raise ValueError("Unexpected job identity")
            if item.get("detail_skipped_outside_geo"):raise ValueError("Unexpected geographic skip")
            ev={"title":item["title"],"url":item["url"],"original_error":item["verification_error"],"description_length":item["description_length"]}
            ev.update(inspect_detail(read_page(item["url"]),item["url"],item["title"]))
            if ev["description_length"]<200:ev["form_evidence"]=False
            if ev["original_error"] and ev["original_error"]!="SourceError: No se encontró acceso directo a candidatura":ev["form_evidence"]=False
            result["details"].append(ev)
        if result["details"] and all(e["form_evidence"] for e in result["details"]):
            result["status"]="FORM_ENTRYPOINT_EVIDENCE_REVIEW_REQUIRED"
        else:result["status"]="FORM_EVIDENCE_INCOMPLETE"
    except Exception as exc:result["error"]=type(exc).__name__+": "+str(exc)[:240]
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("BDL_FORM_EVIDENCE",json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
