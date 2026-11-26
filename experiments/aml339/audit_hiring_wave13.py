#!/usr/bin/env python3
"""Hiring-first bounded live audits. Read-only; no enrollment or application."""
import argparse, json, re
from pathlib import Path
from urllib.parse import urlsplit,urljoin
from live_e2e18_full import audit_one
import live_e2e18_full as audit
from live_external50_wave02 import candidate,Anchors,read_page

# Actual employer postings establish hiring relevance, not present vacancies,
# regulatory status, suitability for the user or technical completeness.
CATALOG = {"caceis-europe":"https://jobs.caceis.com/offre-de-emploi/emploi-kyc-analyst-h-f_115530.aspx"}
EXTERNAL = {
  "external-societe-generale": [
    "Société Générale",
    "https://careers.societegenerale.com/en/Technical/all-job-offers",
    [
      "site_jobs",
      "careers.societegenerale.com",
      "^/en/job-offers/[^/]+-[0-9A-Z]{8}-en/?$"
    ],
    "https://careers.societegenerale.com/en/job-offers/vie-new-business-onboarding-kyc-analyst-26000N0G-en",
    [
      "societe generale",
      "société générale",
      "societegenerale",
      "socit gnrale"
    ]
  ]
}
IDS = tuple(CATALOG)+tuple(EXTERNAL)
def normalized(s):
    return re.sub(r"[^a-z0-9]","",str(s).lower())
def same_group(row, others):
    aliases=[normalized(a) for a in row.get("aliases",[])]
    for old in others:
        vals=[normalized(old.get(k,"")) for k in ("id","name","careers_url")]
        vals.extend(normalized(a) for a in old.get("aliases",[]))
        if old.get("route")==row.get("route") or any(a and a in v for a in aliases for v in vals):
            return old.get("id")
    return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,choices=IDS)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--live",type=Path,required=True)
    p.add_argument("--registry",type=Path,required=True)
    a=p.parse_args(); sid=a.source
    result={"id":sid,"verified":False}
    try:
        original=json.loads(Path("fuentes.json").read_text())["sources"]
        assert len(original)==len({x["id"] for x in original})==339
        live=json.loads(a.live.read_text())["sources"]
        registry=json.loads(a.registry.read_text())["sources"]
        assert len(live)==len({x["id"] for x in live})
        active={x["id"] for x in live}|{x["id"] for x in registry}
        if sid in active:
            raise ValueError("Already monitored; no duplicate audit")
        if sid in CATALOG:
            row=dict(next(x for x in original if x["id"]==sid))
            reference=CATALOG[sid]
            if any(x.get("route")==row.get("route") and x["id"] in active for x in original+registry):
                raise ValueError("ATS route already monitored")
            result["origin"]="original_catalog"
        else:
            name,careers_url,route,reference,aliases=EXTERNAL[sid]
            row={"id":sid,"name":name,"careers_url":careers_url,"route":route,"aliases":aliases}
            if route[0]=="teamtailor":row["job_pattern"]=r"^/jobs/[0-9]+-[^/]+/?$"
            if route[0]=="site_jobs":row["job_pattern"]=route[2]
            match=same_group(row,original+registry+live)
            if match:
                if match in active:
                    raise ValueError("Already monitored group: "+str(match))
                found=[x for x in original if x["id"]==match]
                if len(found)!=1:
                    raise ValueError("Ambiguous catalog group: "+str(match))
                old=found[0]
                aliases_n={normalized(x) for x in aliases}
                exact=aliases_n.intersection({normalized(old.get("id","")),normalized(old.get("name",""))})
                if not exact and row["route"]!=old.get("route"):
                    raise ValueError("Potential original group alias; manual review required: "+str(match))
                row=dict(old)
                if any(x.get("route")==row.get("route") and x["id"] in active for x in original+registry):
                    raise ValueError("ATS route already monitored")
                result["origin"]="original_catalog"
                result["catalog_id"]=match
            else:
                result["origin"]="new_external_review"
                if route[0] in ("smart_review","lever"):
                    # Reuse only a known schema from the original catalog. Never invent
                    # a provider route when the public employer slug cannot be mapped.
                    kind=route[0]
                    slug=route[1]
                    examples=[x.get("route",[]) for x in original if len(x.get("route",[]))==3]
                    oldslug="wise" if kind=="smart_review" else "crypto"
                    templates=[r for r in examples if any(oldslug==str(v).lower() for v in r[1:]) and ((kind=="smart_review" and "smart" in str(r[0]).lower()) or (kind=="lever" and "lever" in str(r[0]).lower()))]
                    if len({tuple(r) for r in templates})!=1:
                        raise ValueError("No unique known original ATS route schema")
                    row["route"]=[slug if str(v).lower()==oldslug else v for v in templates[0]]
                    if any(x.get("route")==row["route"] for x in original+registry+live):
                        raise ValueError("ATS route already catalogued or monitored")

        if urlsplit(reference).scheme!="https" or "workable" in str(row.get("route",[])).lower():
            raise ValueError("Unsupported or restricted route")
        result.update(config=row,hiring_reference=reference)
        if row["route"][0]=="diagnostic":
            # Static/JS paginated portals require independent all-page coverage proof.
            # Record only observed anchors; never label a partial listing verified.
            page=Anchors();page.feed(read_page(row["careers_url"]))
            links={urljoin(row["careers_url"],h) for h,t in page.links.items() if t and urlsplit(urljoin(row["careers_url"],h)).hostname==row["route"][1] and urlsplit(urljoin(row["careers_url"],h)).path.startswith(row["route"][2])}
            result.update(status="DIAGNOSTIC_NEEDS_COMPLETE_LISTING",observed_job_links=len(links),observed_urls=sorted(links)[:15])
            a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
            print("HIRING_FIRST_AUDIT",json.dumps({k:v for k,v in result.items() if k!="config"},ensure_ascii=False),flush=True)
            return
        old=audit.candidate
        from amlradar.sources import Board
        original_listing=Board.listing
        def checked_listing(board):
            jobs=original_listing(board)
            if sid=="external-societe-generale":
                raw=read_page(row["careers_url"])
                from html.parser import HTMLParser
                class Visible(HTMLParser):
                    def __init__(self):super().__init__();self.parts=[]
                    def handle_data(self,d):self.parts.append(d)
                v=Visible();v.feed(raw)
                counts={int(m.replace(" ","").replace("\u00a0","")) for m in re.findall(r"\b([\d \u00a0]+)\s+offre\(s\)", " ".join(v.parts),re.I)}
                anchor=Anchors();anchor.feed(raw);pattern=re.compile(row["job_pattern"])
                keys={urlsplit(urljoin(row["careers_url"],h)).path.rstrip("/") for h,t in anchor.links.items() if t and urlsplit(urljoin(row["careers_url"],h)).hostname==row["route"][1] and pattern.fullmatch(urlsplit(urljoin(row["careers_url"],h)).path)}
                actual={urlsplit(str(j.get("url",""))).path.rstrip("/") for j in jobs}
                result["independent_counts"]=sorted(counts)
                print("SG_DECLARED_CONTROL",json.dumps({"declared":sorted(counts),"anchors":len(keys),"extracted":len(actual)},ensure_ascii=False),flush=True)
                if counts!={len(keys)} or not keys or keys!=actual or len(actual)!=len(jobs):raise ValueError("SG declared count, anchor IDs and extracted IDs disagree")
            return jobs
        audit.candidate=candidate
        Board.listing=checked_listing
        try:report=audit_one(row,minutes=4)
        finally:
            audit.candidate=old
            Board.listing=original_listing
        n=report.get("total_listed")
        ok=(report.get("state")=="listing_extracted" and report.get("list_complete") is True
            and type(n) is int and n>0
            and report.get("relevant_leads")==len(report.get("audited",[]))
            and report.get("unverified_in_scope")==0 and report.get("listing_untrackable_count")==0)
        if not ok:report.update(state="listing_failed",list_complete=False)
        result.update(verified=ok,audit=report,status="TECHNICAL_PASS_REVIEW_REQUIRED" if ok else "INCOMPLETE")
    except Exception as exc:
        result.update(status="HELD",error=type(exc).__name__+": "+str(exc)[:250])
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    report=result.get("audit",{})
    print("HIRING_FIRST_AUDIT",json.dumps({"id":sid,"verified":result["verified"],"status":result.get("status"),"listed":report.get("total_listed"),"relevant":report.get("relevant_leads"),"unverified":report.get("unverified_in_scope"),"error":result.get("error"),"errors":report.get("errors"),"plausible_geo":[{"title":j.get("title"),"location":j.get("location"),"url":j.get("url"),"error":j.get("verification_error")} for j in report.get("audited",[]) if j.get("evaluation",{}).get("geography") in ("target","swiss_future","remote_location_review","mixed_location_review","unknown")]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
