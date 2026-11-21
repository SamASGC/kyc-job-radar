"""Reproduce the isolated AML339 repair against the SHAs pinned in the test workflow.
Never modify the repository root, production data or alert state.
"""
from pathlib import Path
import json
root=Path(__file__).resolve().parent
p=root/"amlradar/sources.py"
s=p.read_text(encoding="utf-8")
needle="from email.utils import parsedate_to_datetime\n"
assert needle in s
s=s.replace(needle,needle+"import json\nimport datetime as dt\n",1)
start=s.index('        elif k=="vinted_html":')
end=s.index('        elif k=="teamtailor":',start)
s=s[:start]+'''        elif k=="vinted_html":
            # The employer's Next.js initial data includes the full catalogue,
            # including first_published. Never use updated_at for freshness.
            r=self.page(self.source["careers_url"]); p=Page(r["body"],r["final_url"])
            scripts=[v["text"] for v in p.scripts if v["type"]=="application/json"
                     and v["text"].lstrip().startswith("{")]
            payload=None
            for body in scripts:
                try: candidate=json.loads(body)
                except (ValueError,TypeError):continue
                if isinstance(candidate,dict) and isinstance(candidate.get("props"),dict) and isinstance(candidate["props"].get("jobs"),dict):
                    payload=candidate;break
            if payload is None:
                fallback=[]
                for link in p.links:
                    u=up.urlparse(link["url"])
                    m=re.fullmatch(r"/jobs/j/(\d+)",u.path)
                    if u.hostname=="careers.vinted.com" and m:
                        fallback.append({"id":m[1],"absolute_url":link["url"],"title":link["text"]})
                m=re.search(r"Showing\s+\d+\s+out\s+of\s+(\d+)",p.visible(),re.I)
                payload={"props":{"jobs":{"dataMap":{"fallback":{"jobs":fallback}}},
                    "jobsCount":int(m[1]) if m else None}}
                self.complete=False
            props=payload["props"]; data_map=props["jobs"].get("dataMap")
            if not isinstance(data_map,dict):raise SourceError("Vinted: jobs dataMap missing")
            seen=set()
            for lang,section in data_map.items():
                if not isinstance(section,dict) or not isinstance(section.get("jobs"),list):
                    raise SourceError("Vinted: jobs dataMap section changed")
                for row in section["jobs"]:
                    if not isinstance(row,dict):continue
                    uid=str(row.get("id") or "")
                    url=row.get("absolute_url") or ""
                    parsed=up.urlparse(url)
                    if not uid.isdigit() or parsed.hostname!="careers.vinted.com":continue
                    if not re.fullmatch(r"/(?:[a-z]{2}/)?jobs/(?:j/)?"+re.escape(uid)+r"/?",parsed.path):continue
                    if uid in seen:continue
                    seen.add(uid)
                    loc=location(row.get("location")) or location(row.get("city"))
                    country=location(row.get("country"))
                    if country and country.lower() not in loc.lower():
                        loc=", ".join(filter(None,[loc,country]))
                    jobs.append(self.job(row.get("title"),url,id=uid,
                        date=row.get("first_published"),
                        date_field="Vinted.GH.first_published" if row.get("first_published") else "",
                        date_semantics="Initial publication in employer catalogue, not updated_at",
                        description=plain(row.get("content")),location=loc,apply_url=url))
            declared=props.get("jobsCount")
            if isinstance(declared,int) and declared>=0:
                self.total=declared
                if len(jobs)!=declared:
                    self.complete=False
                    self.warnings.append(f"Vinted: extracted {len(jobs)} unique posts out of {declared}")
            else:
                self.complete=False;self.warnings.append("Vinted: no authoritative count")
            if not jobs:raise SourceError("Vinted: empty or unsupported job catalogue")
'''+s[end:]
old='''            for query in terms:
                offset=0; seen_in_query=set(); advertised=None'''
new='''            for query in terms:
                if time.monotonic()+max(2,getattr(self.client,'timeout',0))>=self.deadline:
                    if not jobs:raise SourceError("Workday: time exhausted without any results")
                    self.complete=False;self.warnings.append("Workday: remaining searches not checked")
                    break
                offset=0; seen_in_query=set(); advertised=None'''
assert old in s;s=s.replace(old,new)
old='''                while True:
                    d=self.js(base+"/jobs",{"limit":20,"offset":offset,"searchText":query})'''
new='''                while True:
                    if time.monotonic()+max(2,getattr(self.client,'timeout',0))>=self.deadline:
                        if not jobs:raise SourceError("Workday: time limit before first result")
                        self.complete=False;self.warnings.append("Workday: incomplete by time limit")
                        break
                    d=self.js(base+"/jobs",{"limit":20,"offset":offset,"searchText":query})'''
assert old in s;s=s.replace(old,new)
old='''                    if len(seen_in_query)==before: raise SourceError("Workday repite páginas; listado incompleto")'''
new='''                    if len(seen_in_query)==before:
                        if not jobs:raise SourceError("Workday: repeating pages, no results")
                        self.complete=False;self.warnings.append(f"Workday '{query}': repeated page, partial listing")
                        break'''
assert old in s;s=s.replace(old,new)
# CACEIS same-host fallback if the English page has no job links.
old='''            if queue:
                self.complete=False
                self.warnings.append(f"Listado incompleto: límite de {max_pages} páginas alcanzado")'''
new='''            fallback_url=self.source.get("repair_fallback_url")
            if not jobs and fallback_url:
                if up.urlparse(fallback_url).hostname!=h or not safe_url(fallback_url):
                    raise SourceError("Fallback fuera del dominio oficial")
                replacement=dict(self.source,careers_url=fallback_url,catalog_count_url=fallback_url,repair_fallback_url=None)
                backup=Board(replacement,self.client,max_minutes=max(1,(self.deadline-time.monotonic())/60))
                rows=backup.listing()
                self.complete=backup.complete;self.total=backup.total
                self.warnings.extend(backup.warnings)
                return rows
            if queue:
                self.complete=False
                self.warnings.append(f"Listado incompleto: límite de {max_pages} páginas alcanzado")'''
assert old in s;s=s.replace(old,new,1)
old='''            if self.source.get("rfc2822_date"):
                match=re.search('''
new='''            if self.source.get("detail_date_regex") and not j.get("date"):
                m=re.search(self.source["detail_date_regex"],p.visible(),re.I)
                if m:
                    try:
                        j["date"]=dt.datetime.strptime(m.group(1),"%d/%m/%Y").date().isoformat()
                        j["date_field"]="Official employer detail: publication date"
                        j["date_semantics"]="Date de parution declared by employer"
                    except (ValueError,IndexError):pass
            if self.source.get("rfc2822_date"):
                match=re.search('''
assert old in s;s=s.replace(old,new,1)
p.write_text(s,encoding="utf-8")
p=root/"fuentes.json"
d=json.loads(p.read_text(encoding="utf-8"))
by={x["id"]:x for x in d["sources"]}
assert len(by)==len(d["sources"])==339
c=by["caceis-europe"]
c["careers_url"]="https://jobs.caceis.com/offre-de-emploi/liste-toutes-offres.aspx?LCID=2057&page=1"
c["repair_fallback_url"]="https://jobs.caceis.com/offre-de-emploi/liste-toutes-offres.aspx?LCID=1036&showSearchUrl=1"
c["catalog_count_url"]=c["careers_url"]
c["detail_date_regex"]=r"(?:Date de parution|Publication date)\s*(\d{2}/\d{2}/\d{4})"
c["repair_status"]="Experimental: official French listing; pagination not yet fully validated"
by["santander"]["workday_search_terms"]=["AML","KYC","sanctions","financial crime"]
by["pwc-experienced"]["workday_search_terms"]=["AML","KYC","financial crime","sanctions"]
by["state-street"]["workday_search_terms"]=["AML","KYC","financial crime","sanctions"]
for ident in ("santander","pwc-experienced","state-street"):
    by[ident]["repair_status"]="Scoped Workday queries only, never claim complete employer catalogue"
for ident in ("capimoney","lt-nayax-global-legal-compliance"):
    by[ident]["repair_status"]="Unconfirmed official endpoint; blocked or 404, never claim zero jobs"
# TrueLayer employer site migrated from Greenhouse EU to the first-party Ashby board.
# Verified via HTTP 200, not a speculative ATS slug.
by["truelayer"]["route"]=["ashby","api.ashbyhq.com","truelayer"]
by["truelayer"]["careers_url"]="https://jobs.ashbyhq.com/truelayer"
by["truelayer"]["repair_status"]="Official TrueLayer careers links to Ashby; first-party public API HTTP 200 with four jobs"
by["truelayer"]["regulation"]["regulatory_source"]="https://www.lb.lt/en/sfi-financial-market-participants/truelayer-ireland-limited"
by["truelayer"]["regulation"]["status"]="TrueLayer (Ireland) Limited is authorised in Ireland. The Lithuanian register confirms EEA cross-border services; verify hiring entity per vacancy."
# Regulatory register data is source metadata, NOT a property of every vacancy.
by["vinted"]["regulation"]={
    "licensed_entity":"Vinted Pay, UAB",
    "country":"Lithuania",
    "licence_type":"Electronic money institution",
    "regulator":"Bank of Lithuania",
    "regulatory_source":"https://www.lb.lt/en/sfi-financial-market-participants//vinted-pay-uab",
    "status":"Vinted Pay licence verified; the portal also contains Vinted Marketplace/Go roles. Do not assign licence to every vacancy."
}
by["caceis-europe"]["regulation"]={
    "licensed_entity":"CACEIS Bank, Luxembourg branch",
    "country":"Luxembourg",
    "licence_type":"Credit institution branch",
    "regulator":"Entity-dependent",
    "regulatory_source":"https://www.bde.es/webbe/en/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-instituciones-financieras-monetarias-pais/lista-mfi-lu.html",
    "status":"CACEIS Bank Luxembourg branch confirmed; verify the hiring legal entity for each posting."
}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("REPAIR339_APPLIED",len(by),flush=True)
