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
s=s.replace(needle,needle+"import json\n",1)
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
            if payload is None:raise SourceError("Vinted: Next.js jobs data not available")
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
                if time.monotonic()+max(2,self.client.timeout)>=self.deadline:
                    if not jobs:raise SourceError("Workday: time exhausted without any results")
                    self.complete=False;self.warnings.append("Workday: remaining searches not checked")
                    break
                offset=0; seen_in_query=set(); advertised=None'''
assert old in s;s=s.replace(old,new)
old='''                while True:
                    d=self.js(base+"/jobs",{"limit":20,"offset":offset,"searchText":query})'''
new='''                while True:
                    if time.monotonic()+max(2,self.client.timeout)>=self.deadline:
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
p.write_text(s,encoding="utf-8")
p=root/"fuentes.json"
d=json.loads(p.read_text(encoding="utf-8"))
by={x["id"]:x for x in d["sources"]}
assert len(by)==len(d["sources"])==339
c=by["caceis-europe"]
c["careers_url"]="https://jobs.caceis.com/offre-de-emploi/liste-toutes-offres.aspx?LCID=1036&showSearchUrl=1"
c["catalog_count_url"]=c["careers_url"]
c["repair_status"]="Experimental: official French listing; pagination not yet fully validated"
by["santander"]["workday_search_terms"]=["AML","KYC","sanctions","financial crime"]
by["pwc-experienced"]["workday_search_terms"]=["AML","KYC","financial crime","sanctions"]
by["state-street"]["workday_search_terms"]=["AML","KYC","financial crime","sanctions"]
for ident in ("santander","pwc-experienced","state-street"):
    by[ident]["repair_status"]="Scoped Workday queries only, never claim complete employer catalogue"
for ident in ("truelayer","capimoney","lt-nayax-global-legal-compliance"):
    by[ident]["repair_status"]="Unconfirmed official endpoint; blocked or 404, never claim zero jobs"
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("REPAIR339_APPLIED",len(by),flush=True)
