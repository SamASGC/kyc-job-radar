#!/usr/bin/env python3
"""Validate 50 regulator-discovered entities against immutable original catalog.

No job alerts, job applications or history writes. This is a *discovery*
preflight: separate 50 legal-entity leads from genuinely operable ATS feeds.
"""
import io,json,re,unicodedata,urllib.error,urllib.request,zipfile
from pathlib import Path

def norm(value):
    value=unicodedata.normalize("NFKD",value.casefold())
    value="".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+"," ",value).strip()

def main():
    d=json.loads(Path("experiments/aml339/regulator50_external_candidates.json").read_text())
    assert d["purpose"]=="DISCOVERY_ONLY_NOT_A_LIVE_JOB_MONITOR"
    assert d["round_size"]==len(d["candidates"])==50
    assert len({x["id"] for x in d["candidates"]})==50
    with zipfile.ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
        existing=json.loads(z.read("fuentes.json"))["sources"]
    assert len({x["id"] for x in existing})==len(existing)==339
    names={x["id"]:norm(x["name"]) for x in existing}
    records=[]
    for c in d["candidates"]:
        expected=norm(c["legal_name"])
        identity=norm(c["id"].removeprefix("reg50-"))
        collisions=[x["id"] for x in existing
                    if norm(x["id"]) in (expected,identity)
                    or names[x["id"]]==expected]
        # A similar token may reveal a brand parent or a previously configured
        # company board under another legal entity: flag, NEVER auto merge.
        hints=[]
        for x in existing:
            words=set(norm(x["name"]).split())|set(norm(x["id"]).split())
            distinctive=[t for t in identity.split() if len(t)>5]
            if distinctive and all(t in words for t in distinctive):
                hints.append(x["id"])
        record={"id":c["id"],"name":c["legal_name"],"country":c["country"],
                "exact_original_catalog_match":collisions,
                "possible_brand_or_group_matches":hints[:8],
                "career_url":c["careers_url"]}
        records.append(record)
        print("REG50_CATALOG_CROSSCHECK",json.dumps(record,ensure_ascii=False),flush=True)
    for s in existing:
        if s["route"][0] in ("personio","site_jobs","greenhouse","teamtailor"):
            if s["route"][0]=="personio" and s["id"] not in ("cafico-international","dm-financial","vivid-money"):continue
            if s["route"][0]=="site_jobs" and s["id"] not in ("bankera","payswix","ibanfirst"):continue
            if s["route"][0] not in ("personio","site_jobs"):continue
            print("REG50_ADAPTER_EXAMPLE",json.dumps(s,ensure_ascii=False),flush=True)
    # Limited requests: the careers page can be up but have NO openings.
    for c in d["candidates"]:
        if not c["careers_url"]:continue
        u=c["careers_url"]
        try:
            req=urllib.request.Request(u,headers={"User-Agent":"AML339-official-employer-careers-research/1.0"})
            with urllib.request.urlopen(req,timeout=10) as r:
                body=r.read(160000).decode("utf-8","replace")
                note={"status":r.status,"final_url":r.url,"length_sample":len(body),
                      "mentions_jobs":bool(re.search(r"job|career|position|vacanc",body,re.I))}
        except Exception as e:note={"error":type(e).__name__+": "+str(e)[:140]}
        print("REG50_CAREER_PREFLIGHT",json.dumps({"id":c["id"],**note},ensure_ascii=False),flush=True)
    Path("reg50_preflight_report.json").write_text(json.dumps({
        "candidate_count":50,"original_catalog_count":339,
        "matched_exact":sum(bool(x["exact_original_catalog_match"]) for x in records),
        "records":records,
        "disclosure":"Regulatory discovery != active ATS scan, verified personal work eligibility or open vacancy"
    },ensure_ascii=False,indent=2)+"\n")

if __name__=="__main__":main()
