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
CATALOG = {}
EXTERNAL = {
  "external-deutsche-boerse": [
    "Deutsche Börse / Clearstream",
    "https://careers.deutsche-boerse.com/search/",
    [
      "site_jobs",
      "careers.deutsche-boerse.com",
      "^/jobs/[^/]+/[0-9a-f-]{36}/?$"
    ],
    "https://careers.deutsche-boerse.com/jobs/intern-compliance-fcc-projects-data-analyst-associate-f-m-d/5ef6a2ab-0728-4a24-8aad-81d8882a332c",
    [
      "deutsche boerse",
      "deutsche börse",
      "clearstream"
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
        from amlradar.sources import Board
        from html.parser import HTMLParser
        host="careers.deutsche-boerse.com"
        categories={"Business Operations":"business-operations","Information Technology":"information-technology","Corporate Functions":"corporate-functions","Control Functions":"control-functions","Business Analytics & Data":"business-analytics","Finance":"finance"}
        pattern=re.compile(row["job_pattern"],re.I)
        def extract(raw,url):
            a=Anchors();a.feed(raw)
            paths={}
            for h,t in a.links.items():
                u=urlsplit(urljoin(url,h))
                if u.scheme=="https" and u.netloc==host and pattern.fullmatch(u.path) and t:
                    ident=u.path.rstrip("/").rsplit("/",1)[1]
                    if ident in paths and paths[ident]!=u.path.rstrip("/"):raise ValueError("Ambiguous UUID")
                    paths[ident]=u.path.rstrip("/")
            return paths
        class Visible(HTMLParser):
            def __init__(self):super().__init__();self.parts=[]
            def handle_data(self,d):self.parts.append(d)
        sets={}
        for label,slug in categories.items():
            url="https://"+host+"/"+slug
            raw=read_page(url)
            v=Visible();v.feed(raw)
            visible=" ".join(v.parts)
            counts={int(m) for m in re.findall(re.escape(label)+r"\s+(\d+)\s+jobs\b",visible,re.I)}
            paths=extract(raw,url)
            sets[label]={"declared":sorted(counts),"links":len(paths),"ids":sorted(paths)}
        result["category_evidence"]=sets
        print("DBG_CATEGORY_COUNTS",json.dumps({k:{"declared":v["declared"],"links":v["links"]} for k,v in sets.items()}),flush=True)
        if any(v["declared"]!=[v["links"]] or not v["links"] for v in sets.values()):raise ValueError("Department declared counts disagree with visible job IDs")
        union=set().union(*(set(v["ids"]) for v in sets.values()))
        if sum(v["links"] for v in sets.values())!=len(union):raise ValueError("Department identity overlap")
        global_paths=extract(read_page(row["careers_url"]),row["careers_url"])
        result["global_coverage"]={"department_ids":len(union),"global_ids":len(global_paths),"missing":sorted(union-set(global_paths)),"extra":sorted(set(global_paths)-union)}
        print("DBG_GLOBAL_COVERAGE",json.dumps(result["global_coverage"]),flush=True)
        if set(global_paths)!=union:raise ValueError("Department/global listing identities disagree")
        old=audit.candidate
        original=Board.listing
        def checked(board):
            jobs=original(board)
            actual={urlsplit(str(j.get("url",""))).path.rstrip("/") for j in jobs}
            if actual!=set(global_paths.values()) or len(actual)!=len(jobs):raise ValueError("Production parser did not extract complete global identities")
            return jobs
        audit.candidate=candidate
        Board.listing=checked
        try:report=audit_one(row,minutes=4)
        finally:
            audit.candidate=old
            Board.listing=original
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
