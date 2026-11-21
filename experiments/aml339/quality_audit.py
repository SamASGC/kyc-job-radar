#!/usr/bin/env python3
"""Read-only evidence-based AML role triage on the original 339-source extractor.

A listing is a lead, not a verified active/recent job or a promise of training.
Never import production state; never post applications or send alerts.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import re
import time
from pathlib import Path
from collections import Counter
from amlradar.sources import Board, relevant
from amlradar.net import Client
from amlradar.model import clean, plain, freshness, date_interval, safe_url

TARGET = {
    "SoF":r"\b(?:source of funds|SoF\b|origen de (?:los )?fondos)\b",
    "SoW":r"\b(?:source of wealth|SoW\b|origen del patrimonio)\b",
    "PEP":r"\b(?:PEPs?|politically exposed persons?)\b",
    "Sanctions screening":r"\b(?:sanctions?|sanctioned (?:entities|individuals))\b",
    "Adverse media":r"\b(?:adverse media|negative media|negative news)\b",
    "TM":r"\b(?:transaction(?:al)? monitoring|monitoring transactions|transaction alerts?|suspicious transactions?)\b",
    "SAR/STR":r"\b(?:SARs?|STRs?|suspicious (?:activity|transaction) reports?)\b",
    "CDD/EDD/KYB":r"\b(?:CDD|EDD|KYB|KYC|due diligence|customer onboarding)\b",
}
RX={k:re.compile(v,re.I) for k,v in TARGET.items()}
MAIN=set(TARGET)-{"CDD/EDD/KYB"}
WEIGHT={"SoF":20,"SoW":20,"PEP":13,"Sanctions screening":16,"Adverse media":16,
        "TM":9,"SAR/STR":7,"CDD/EDD/KYB":3}
COUNTRY=re.compile(r"\b(?:Spain|España|Madrid|Lithuania|Lietuva|Vilnius|Kaunas|Estonia|Tallinn|Malta|Luxembourg)\b",re.I)
SWISS=re.compile(r"\b(?:Switzerland|Swiss|Zurich|Zürich|Geneva|Genève|Basel|Lugano)\b",re.I)
OUTSIDE=re.compile(r"\b(?:United States|USA|Canada|India|Singapore|Australia|Brazil|Mexico|Hong Kong|China|Japan|Philippines|Pakistan|Bangladesh|UAE|Dubai|South Africa|New York|London|Berlin|Paris|Bangalore|Bengaluru|Mumbai|Chennai|Delhi|Hyderabad|Manila|Sydney)\b",re.I)
UNSUPPORTED_LANGUAGE=re.compile(r"\b(?:Lithuanian|Estonian|Latvian|German|Deutsch|Dutch|Italian|Polish|Portuguese|Russian|Swedish|Finnish|Danish)\b",re.I)
MANDATORY_WORDS=re.compile(r"\b(?:must|required|mandatory|essential|need to|minimum|at least|fluen\w*|native|proficien\w*|excellent|C1\b|C2\b)\b",re.I)
SENIOR_TITLE=re.compile(r"\b(?:head of|director|chief|deputy mlro|mlro|vice president|vp\b|senior manager|team lead|principal|staff (?:officer|analyst)|global head)\b",re.I)
TECH_TITLE=re.compile(r"\b(?:engineer|developer|architect|product owner|account executive|sales|devops|data scientist|designer|cybersecurity)\b",re.I)
PRACTICAL=re.compile(r"\b(?:hands[- ]on|proven|previous|prior|demonstrated|practical|track record|experience (?:in|with|handling|conducting|performing|investigating))\b",re.I)
PRIORITY_SKILLS=re.compile(r"\b(?:screening|sanctions?|PEP|adverse media|source of (?:funds|wealth)|SoF|SoW|transaction monitoring|SAR|STR)\b",re.I)
YEAR_REQUIREMENT=re.compile(r"\b(?:minimum(?: of)?|at least|over|more than|requires?|must have)?\s*(\d+)\s*\+?\s*(?:years?|yrs?)\b",re.I)
DUTY=re.compile(r"\b(?:responsibilit|your role|what you(?:'ll| will) do|key duties|day.to.day|what you will be doing|main tasks|functions)\b",re.I)
REQ=re.compile(r"\b(?:requirements?|qualifications?|what (?:you'll|you will) bring|what we look for|must have|your profile|experience & skills|about you|essential skills)\b",re.I)
OPTIONAL=re.compile(r"\b(?:nice to have|preferred|desirable|would be a plus|advantageous|not required|or equivalent experience)\b",re.I)

def short_sentence(line:str)->str:
    return clean(line)[:230]

def sections(description):
    lines=[clean(x) for x in plain(description).splitlines() if clean(x)]
    mode="unknown"; parsed=[]
    for line in lines:
        if len(line)<105 and REQ.search(line):mode="requirements"
        elif len(line)<105 and DUTY.search(line):mode="duties"
        elif len(line)<105 and re.search(r"what we offer|benefits|perks|about us|why join",line,re.I):mode="other"
        parsed.append((mode,line))
    return parsed

def role_geography(loc):
    loc=clean(loc)
    if not loc:return "unknown"
    loc=re.sub(r"\bMalta\s+(?:Avenue|Ave|Street|Road|Drive)\b","",loc,flags=re.I)
    # An explicit Barcelona-only role is excluded; mixed sites require review.
    if re.search(r"\bBarcelona\b",loc,re.I):
        if re.search(r"\bMadrid\b|\bVilnius\b|\bTallinn\b|\bLuxembourg\b|\bMalta\b|\bKaunas\b",loc,re.I):
            return "mixed_location_review"
        return "excluded_barcelona"
    if COUNTRY.search(loc) and OUTSIDE.search(loc):return "mixed_location_review"
    if COUNTRY.search(loc):return "target"
    if SWISS.search(loc):return "swiss_future"
    if OUTSIDE.search(loc):return "outside_scope"
    if re.search(r"\b(?:remote|hybrid|EMEA|Europe|worldwide)\b",loc,re.I):return "remote_location_review"
    return "unknown"

def evaluate(job, application_verified:bool):
    title=clean(job.get("title"))
    body=plain(job.get("description"))
    loc=clean(job.get("location"))
    evidence=sections(body)
    skills={k for k,r in RX.items() if r.search(body)}
    title_skills={k for k,r in RX.items() if r.search(title)}
    skills|=title_skills
    duties={k for mode,line in evidence if mode=="duties" for k,r in RX.items() if r.search(line)}
    flags=[]; barriers=[]; traces=[]
    geo=role_geography(loc)
    if geo=="excluded_barcelona":barriers.append("Solo Barcelona")
    if geo=="outside_scope":barriers.append("Ubicación publicada fuera de países objetivo")
    if geo in ("unknown","remote_location_review","mixed_location_review"):
        flags.append("Ubicación/posibilidad de trabajar desde país objetivo por verificar")
    if geo=="swiss_future":flags.append("Suiza: vía profesional futura; no asumir elegibilidad actual")
    if SENIOR_TITLE.search(title):barriers.append("Puesto directivo o de alta responsabilidad")
    if TECH_TITLE.search(title):barriers.append("Función técnica/comercial ajena al objetivo")
    if not body or len(body)<120:flags.append("Descripción insuficiente; responsabilidades y requisitos no comprobados")
    # Read mandatory requirements as distinct from job duties and desirable qualifications.
    for mode,line in evidence:
        if mode!="requirements" or OPTIONAL.search(line):continue
        if len(line)>500:continue
        if UNSUPPORTED_LANGUAGE.search(line) and MANDATORY_WORDS.search(line):
            barriers.append("Idioma adicional obligatorio no acreditado")
            traces.append({"kind":"language_requirement","text":short_sentence(line)})
        if re.search(r"\b(?:degree|bachelor|master|university diploma|law degree)\b",line,re.I) and MANDATORY_WORDS.search(line):
            flags.append("Titulación universitaria terminada posiblemente obligatoria (Derecho en curso)")
            traces.append({"kind":"degree_requirement","text":short_sentence(line)})
        n=[int(m.group(1)) for m in YEAR_REQUIREMENT.finditer(line)]
        if n and max(n)>3 and re.search(r"\bexperience\b",line,re.I) and not OPTIONAL.search(line):
            barriers.append("Exige más de tres años de experiencia")
            traces.append({"kind":"years_requirement","text":short_sentence(line)})
        if PRACTICAL.search(line) and PRIORITY_SKILLS.search(line):
            # A sentence offering KYB/KYC as an alternative is not a hard technical requirement.
            alternatives=bool(re.search(r"\b(?:KYC|KYB|CDD)\b",line,re.I) and re.search(r"\bor\b|such as|e\.g\.",line,re.I))
            if alternatives:
                flags.append("Experiencia descrita con alternativas; confirmar que KYB es suficiente")
            else:
                barriers.append("Experiencia práctica previa en funciones objetivo aparentemente requerida")
            traces.append({"kind":"prior_skill_requirement","text":short_sentence(line)})
        if re.search(r"\b(?:banking|bank)\s+experience\b",line,re.I) and MANDATORY_WORDS.search(line):
            flags.append("Experiencia bancaria específica: comprobar si pagos/KYB es válida")
            traces.append({"kind":"banking_requirement","text":short_sentence(line)})
    # No hiring acceptance, training or legal-entity licensing can be inferred from missing requirements.
    if not any(mode=="requirements" for mode,_ in evidence):
        flags.append("Sección de requisitos no delimitada; no afirmar ausencia de experiencia previa")
    if not any(mode=="duties" for mode,_ in evidence):
        flags.append("Responsabilidades no delimitadas; comprobar si las funciones son prácticas")
    if not (skills & MAIN):
        flags.append("No acredita screening, SoF/SoW, TM o SAR; sólo CDD/EDD u otra función")
    recency=freshness(job.get("date"),hours=72)
    if recency!="fresh":flags.append("Publicación no confirmada dentro de las últimas 72 horas: "+recency)
    if not application_verified:flags.append("Candidatura directa no verificada")
    score=sum(WEIGHT[k] for k in skills)+sum(WEIGHT[k]//3 for k in duties)
    if geo=="target":score+=12
    if "SoF" in skills and "SoW" in skills:score+=5
    if "PEP" in skills and "Sanctions screening" in skills:score+=4
    score-=len(set(barriers))*20
    score-=len(set(flags))*2
    if barriers:classif="not_recommended"
    elif not (skills & MAIN):classif="low_incremental_learning"
    elif recency=="fresh" and application_verified and geo=="target" and not flags:
        classif="possible_match_confirmed_recent"
    else:classif="manual_review"
    return {"class":classif,"score":score,"geography":geo,"functions":sorted(skills),
        "explicit_duties":sorted(duties),"barriers":list(dict.fromkeys(barriers)),
        "uncertainties":list(dict.fromkeys(flags)),
        "requirement_evidence":traces[:7],
        "publication_status":recency,"original_posting_date":job.get("date"),
        "date_field":job.get("date_field"),"application_verified":application_verified,
        "training_confirmed":False,
        "training_note":"No se presume formación técnica ni aceptación de candidatos sin experiencia práctica."}

def candidate(job):
    title=clean(job.get("title"))
    return relevant(job) or bool(re.search(
        r"\b(?:merchant (?:risk|review)|account (?:review|verification)|financial (?:investigator|integrity)|payment investigations?)\b",title,re.I))

def prioritize(job):
    title=clean(job.get("title"))
    loc=role_geography(job.get("location"))
    date=job.get("date")
    interval=date_interval(date)
    recent=freshness(date,hours=72)
    # Priority is to inspect possible fresh and local vacancies, NOT alphabetical titles.
    relevance=sum(WEIGHT[k] for k,rx in RX.items() if rx.search(title+" "+str(job.get("description",""))))
    geo_rank={"target":0,"swiss_future":1,"remote_location_review":2,
              "mixed_location_review":3,"unknown":4,"excluded_barcelona":6,"outside_scope":7}[loc]
    fresh_rank={"fresh":0,"boundary":1,"undated":2,"old":3,"future":4}[recent]
    date_ts=interval[0].timestamp() if interval else 0
    return (geo_rank, fresh_rank, -relevance, -date_ts, title.casefold())

def collect(sources,limit=8,timeout=10,minutes=2):
    records=[];counters=Counter()
    for source in sources:
        c=Client(timeout=timeout,deadline=time.monotonic()+minutes*60)
        board=Board(source,c,max_minutes=minutes)
        result={"source_id":source["id"],"employer":source["name"],
                "state":"error","total_listed":None,"relevant_leads":None,
                "sample_limit":limit,"audited":[],"warnings":[]}
        try:
            all_jobs=board.listing()
            candidates=[j for j in all_jobs if candidate(j)]
            candidates.sort(key=prioritize)
            result.update(state="listing_extracted",total_listed=len(all_jobs),
                          relevant_leads=len(candidates),list_complete=board.complete,
                          skipped_leads=max(0,len(candidates)-limit))
            for job in candidates[:limit]:
                verification=False;err=""
                if source["route"][0]=="employer_external_jobs" or job.get("listing_only_external"):
                    err="El enlace externo no prueba que la ficha y candidatura sigan activas"
                else:
                    try:
                        board.hydrate(job)
                        if "_page" not in job:board.read_post(job)
                        board.verify(job)
                        verification=True
                    except Exception as e:
                        err=type(e).__name__+": "+str(e)[:160]
                evaluation=evaluate(job,verification)
                result["audited"].append({
                    "title":clean(job.get("title")),"url":job.get("url"),
                    "apply_url":job.get("apply_url") if verification else None,
                    "location":clean(job.get("location")),
                    "hiring_organization":clean(job.get("hiring_organization")),
                    "description_length":len(plain(job.get("description"))),
                    "verification_error":err,"evaluation":evaluation})
            result["warnings"]=board.warnings[:8]
            counters["listings_extracted"]+=1
        except Exception as e:
            result["error"]=type(e).__name__+": "+str(e)[:230]
            result["state"]="listing_failed";counters["listings_failed"]+=1
        counters["records_read"]+=len(result["audited"])
        print("QUALITY_SOURCE",json.dumps({
            "id":result["source_id"],"state":result["state"],
            "listed":result["total_listed"],"leads":result["relevant_leads"],
            "audited":len(result["audited"]),
            "skipped":result.get("skipped_leads"),
            "classes":dict(Counter(x["evaluation"]["class"] for x in result["audited"])),
            "error":result.get("error")},ensure_ascii=False),flush=True)
        records.append(result)
    return records,dict(counters)

def test():
    core={"title":"AML & KYC Operations Associate","description":"""Responsibilities
    Review PEP, sanctions and adverse media screening alerts.
    Assess source of funds and source of wealth.
    Requirements
    2 years of experience in KYC or KYB.
    English fluency required.""","location":"Vilnius, Lithuania",
    "date":dt.datetime.now(dt.timezone.utc).isoformat(),"date_field":"Greenhouse.first_published"}
    good=evaluate(core,True)
    assert good["class"]=="possible_match_confirmed_recent",good
    assert "SoF" in good["functions"] and "PEP" in good["functions"]
    bad=dict(core,description=core["description"].replace(
        "2 years of experience in KYC or KYB.",
        "Prior hands-on experience with PEP and sanctions screening required."))
    assert evaluate(bad,True)["class"]=="not_recommended"
    uncertain=dict(core,date=None)
    assert evaluate(uncertain,True)["class"]=="manual_review"
    assert evaluate(dict(core,location="Barcelona, Spain"),True)["class"]=="not_recommended"
    assert evaluate(dict(core,location="Malta Avenue, Texas"),True)["class"]=="manual_review" or evaluate(dict(core,location="Malta Avenue, Texas"),True)["class"]=="not_recommended"
    foreign=dict(core,description=core["description"]+"\\nFluent Lithuanian required.")
    assert evaluate(foreign,True)["class"]=="not_recommended"
    assert evaluate(dict(core,description="KYC and CDD only"),True)["class"]=="low_incremental_learning" or evaluate(dict(core,description="KYC and CDD only"),True)["class"]=="manual_review"
    assert role_geography("Madrid / Barcelona")=="mixed_location_review"
    print("QUALITY_SELFTEST_PASSED",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ids",default="vinted,verifo-lithuania,demivolt-lithuania,n26,corpay,wise")
    p.add_argument("--max-details",type=int,default=8)
    p.add_argument("--minutes-per-source",type=int,default=2)
    p.add_argument("--timeout",type=int,default=10)
    p.add_argument("--out",default="quality_results.json")
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    test()
    if args.self_test:return
    if not 1<=args.max_details<=12 or not 1<=args.minutes_per_source<=4:raise SystemExit("Limits exceeded")
    by={x["id"]:x for x in json.loads(Path("fuentes.json").read_text(encoding="utf-8"))["sources"]}
    ids=[x.strip() for x in args.ids.split(",") if x.strip()]
    if not ids or len(ids)>8 or len(set(ids))!=len(ids):raise SystemExit("1-8 distinct IDs required")
    if any(x not in by for x in ids):raise SystemExit("Unconfigured source")
    before=Path("fuentes.json").read_bytes()
    records,counts=collect([by[x] for x in ids],limit=args.max_details,
                           timeout=args.timeout,minutes=args.minutes_per_source)
    assert before==Path("fuentes.json").read_bytes()
    ranks=Counter(x["evaluation"]["class"] for r in records for x in r["audited"])
    result={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
            "limits":"Truncated sample of title-filtered leads, not an exhaustive audit of all postings",
            "application_definition":"HTTP 200 form or ATS application evidence, not confirmed actual acceptance",
            "total_configured_sources":len(by),
            "sources_requested":ids,"summary":counts|{"classes":dict(ranks)},
            "sources":records}
    Path(args.out).write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("QUALITY_SUMMARY",json.dumps(result["summary"],ensure_ascii=False),flush=True)

if __name__=="__main__":main()
