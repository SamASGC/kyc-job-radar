#!/usr/bin/env python3
"""Discover EXACTLY 100 additional authorised-EMI *leads* for AML339 v1.

Source of candidate names: licensedemis.com CC BY 4.0 CSV (derived from
EBA/FCA; secondary). DO NOT call this individual national-licence verification.
Cross-check legal names/trading aliases against both previous research inventory
and pinned original catalog, retaining conservative ambiguity labels.

This is DISCOVERY, not an ATS validation or proof that 100 companies hire now.
"""
from __future__ import annotations
import csv, datetime as dt, io, json, re, unicodedata, urllib.request, zipfile
from pathlib import Path

CSV_URL="https://licensedemis.com/data/emis.csv"
EBA_REGISTRY="https://www.eba.europa.eu/risk-and-data-analysis/data/registers/payment-institutions-register"
TARGETS={"LT":0,"MT":1,"LU":2,"EE":3,"ES":4,"IE":5,"NL":6,"BE":7,
         "LV":8,"CY":9,"PL":10,"PT":11,"FR":12,"DE":13,"CZ":14,"FI":15,"IT":16}
KNOWN_BRANDS=("amazon","stripe","revolut","wise ","airwallex","paypal","google","apple",
 "meta payments","tiktok","booking holdings","transferwise","facebook","microsoft",
 "klarna","mollie","monese","swan","mangopay","andaria","finxp","paydo",
 "nomupay","mifinity","trumia","zen.com","lightspark")
IGNORED_WORDS={"uab","ltd","limited","sa","s","a","bv","b","v","gmbh","plc","as",
               "europe","eu","payments","payment","financial","services","electronic",
               "money","institution","group","technologies","the","holding","company",
               "e","de","of","and","digital","finance","international","bank"}

def norm(value):
    t=unicodedata.normalize("NFKD",str(value or "").casefold())
    return re.sub(r"[^a-z0-9]+"," ","".join(c for c in t if not unicodedata.combining(c))).strip()

def distinctive_tokens(v):
    return {w for w in norm(v).split() if len(w)>=5 and w not in IGNORED_WORDS}

LEGAL_PARTS={"uab","ltd","limited","sa","as","bv","plc","gmbh","ee","lt",
             "es","de","nl","lu","mt","ie","eu","europe","european","company",
             "group","holdings"}
def brand_base(v):
    return " ".join(w for w in norm(v).split() if w not in LEGAL_PARTS)

def matches_existing(name, existing_list):
    normalized=norm(name)
    core=brand_base(name)
    distinct=distinctive_tokens(name)
    for e in existing_list:
        other=norm(e)
        other_core=brand_base(e)
        if normalized==other or core and core==other_core:
            return True
        # Company with alias appended in parentheses, or short operator legal
        # form appended after an otherwise identical group name.
        if len(normalized)>=8 and f" {normalized} " in f" {other} ":
            return True
        if len(other)>=8 and f" {other} " in f" {normalized} ":
            return True
        shared=distinct & distinctive_tokens(e)
        if len(shared)>=2 or (len(shared)==1 and len(distinct)==1
                             and len(distinctive_tokens(e))==1):
            return True
    return False

def snapshot():
    req=urllib.request.Request(CSV_URL,headers={
        "User-Agent":"AML339-official-register-discovery/1.0","Accept":"text/csv"})
    with urllib.request.urlopen(req,timeout=25) as resp:
        if resp.status!=200:raise ValueError("CSV dataset unavailable")
        content=resp.read(2500000)
    lines=content.decode("utf-8-sig").splitlines()
    if len(content)<30000 or not lines[0].startswith("# Licensed EMIs"):
        raise ValueError("Unknown, invalid or suspicious EMI register file")
    rows=list(csv.DictReader(x for x in lines if not x.startswith("#")))
    fields={"legal_name","country","regulator","license_type","license_number",
            "operational_status","license_granted_date","website","profile_url"}
    if not rows or not fields.issubset(rows[0]) or not 300<=len(rows)<=5000:
        raise ValueError("Unexpected license dataset schema or count")
    with zipfile.ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
        original=json.loads(z.read("fuentes.json"))["sources"]
    if len(original)!=339 or len({x["id"] for x in original})!=339:
        raise ValueError("The original source catalog is not 339 unique employers")
    previous=json.loads(Path("experiments/aml339/regulator50_external_candidates.json").read_text())
    if len(previous.get("candidates",[]))!=50:
        raise ValueError("Previous 50 regulated company records are missing")
    existing=[x.get("name","") for x in original]
    existing+= [x.get("id","") for x in original]
    existing+= [x.get("legal_name","") for x in previous["candidates"]]
    existing+= [x.get("trading_name","") for x in previous["candidates"]]
    existing+= ["ZEN.COM","Trumia","Andaria","FinXP","PayDo","NomuPay","MiFinity"]
    existing=[x for x in existing if x]
    existing_norm={norm(x) for x in existing if x}
    existing_distinctive=[distinctive_tokens(x) for x in existing]
    selected=[]
    pools=[]
    for x in rows:
        if x["country"] not in TARGETS or x["operational_status"]!="active":
            continue
        if x["license_type"]!="EMI":
            continue
        if not x["license_number"].strip() or not x["legal_name"].strip():
            continue
        if any(k in norm(x["legal_name"]) for k in KNOWN_BRANDS):
            continue
        name=norm(x["legal_name"])
        trading=norm(x.get("trading_name"))
        if matches_existing(x["legal_name"],existing) or (trading and matches_existing(trading,existing)):
            continue
        tokens=distinctive_tokens(x["legal_name"])
        if tokens and any(tokens==other and len(tokens)>=1 for other in existing_distinctive):
            continue
        # A one-token shared business brand is suspect even if the full legal
        # name differs. Keep only candidates without known exact distinctive
        # brand-token identity, and publish that this is not legal resolution.
        high_risk=bool(tokens and any(
            len(tokens & other)>=1 and len(tokens & other)>=min(len(tokens),len(other))
            for other in existing_distinctive if other
        ))
        if high_risk:continue
        year=(x.get("license_granted_date") or "")[:4]
        year=int(year) if year.isdecimal() else 1900
        priority=(TARGETS[x["country"]], -int(year>=2024),-year,
                  -int(bool(x.get("website"))), name)
        pools.append((priority,x))
    pools.sort(key=lambda z:z[0])
    # Country-diverse selection; maximum 40 from one country. Distribute
    # countries in priority order so no single market dominates all 100.
    by_country={}
    for _,x in pools:by_country.setdefault(x["country"],[]).append(x)
    target_order=list(TARGETS)
    while len(selected)<100:
        changed=False
        for country in target_order:
            if len(selected)>=100:break
            pool=by_country.get(country,[])
            already=sum(x["country"]==country for x in selected)
            while pool and already<30:
                next_record=pool.pop(0)
                if any(matches_existing(next_record["legal_name"],[
                       s["legal_name"]]) for s in selected):
                    continue
                selected.append(next_record);changed=True
                break
        if not changed:break
    if len(selected)!=100:raise ValueError("Fewer than 100 distinct eligible European EMI leads")
    output={
        "schema":1,"as_of":dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope":"100_EXTRA_COMPANY_DISCOVERY_LEADS_NOT_100_LIVE_ATS_FEEDS",
        "count":100,"original_catalog_count":339,
        "prior_regulator50_count":50,
        "source":{
           "secondary_csv":CSV_URL,"attribution":"Licensed EMIs, CC BY 4.0, https://licensedemis.com/",
           "primary_regulator_registry":EBA_REGISTRY,
           "regulatory_method":"Secondary data reports licence active; individual official national authority confirmation NOT completed",
           "source_rows":len(rows)
        },
        "candidates":[{
            "id":"reg100-"+x["country"].lower()+"-"+re.sub(r"[^a-z0-9]+","-",norm(x["legal_name"])).strip("-")[:75],
            "legal_name":x["legal_name"],
            "trading_name":x.get("trading_name",""),
            "country":x["country"],
            "regulator":x["regulator"],
            "licence_type":x["license_type"],
            "licence_reference":x["license_number"],
            "licence_granted_date":x["license_granted_date"],
            "source_reported_status":x["operational_status"],
            "regulator_source":EBA_REGISTRY,
            "secondary_profile_url":x["profile_url"],
            "website_in_secondary_directory":x["website"] or None,
            "licence_verified_national_authority":False,
            "official_careers_verified":False,
            "official_ats_verified":False,
            "live_monitoring_enabled":False,
            "discovery_status":"RESEARCH_QUEUE_NEEDS_REGULATOR_AND_OFFICIAL_ATS_VERIFICATION",
        } for x in selected],
    }
    if len({x["id"] for x in output["candidates"]})!=100:
        raise ValueError("Duplicate new candidate IDs")
    print("REG100_DISCOVERY_SUMMARY",json.dumps({
       "selected":len(selected),"by_country":{c:sum(x["country"]==c for x in selected)
           for c in target_order if any(x["country"]==c for x in selected)},
       "source_rows":len(rows),"eligible_pool":len(pools),
       "missing_websites":sum(not x.get("website") for x in selected),
       "status":"SECONDARY_AUTHORISATION_CANDIDATES_NOT_VERIFIED_OFFICIAL_LICENCES"
    },ensure_ascii=False),flush=True)
    print("REG100_DISCOVERY_DATA",json.dumps(output,ensure_ascii=False,separators=(",",":")),flush=True)

if __name__=="__main__":
    snapshot()
