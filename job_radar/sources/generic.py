from __future__ import annotations

import asyncio
import json
import re
from bs4 import BeautifulSoup

from job_radar.discovery import detect_ats, generic_job_links
from job_radar.models import Job


STRONG_TITLE = re.compile(r"\b(kyc|kyb|aml|fincrime|financial crime|compliance|sanction|fraud|risk|onboarding|due diligence|cdd|edd|screening|investigat|transaction monitoring)\b", re.I)


def _jsonld_job(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "JobPosting":
                return item
            for sub in item.get("@graph", []) if isinstance(item.get("@graph"), list) else []:
                if isinstance(sub, dict) and sub.get("@type") == "JobPosting":
                    return sub
    return {}


def _location(data: dict, visible: str) -> tuple[str, str]:
    remote_hint = ""
    if str(data.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        remote_hint = "Remote"
    parts=[]
    loc=data.get("jobLocation")
    locs=loc if isinstance(loc,list) else ([loc] if loc else [])
    for x in locs:
        if isinstance(x,dict):
            addr=x.get("address") or {}
            if isinstance(addr,dict):
                vals=[addr.get(k) for k in ("addressLocality","addressRegion","addressCountry") if addr.get(k)]
                if vals: parts.append(", ".join(map(str,vals)))
    req=data.get("applicantLocationRequirements")
    reqs=req if isinstance(req,list) else ([req] if req else [])
    for x in reqs:
        if isinstance(x,dict) and x.get("name"):
            parts.append(str(x["name"]))

    # Many career sites expose the city/country in JobPosting JSON-LD but keep the
    # work model (Hybrid / On-site / Remote) only in visible page text. Preserve both.
    mode_match=re.search(r"\b(Remote\s+(?:Global|Europe|EMEA)|Fully\s+Remote|Remote|Hybrid|On-site|Onsite)\b", visible, re.I)
    mode=mode_match.group(1) if mode_match else ""
    if mode and "remote" in mode.lower():
        remote_hint = "Remote"

    if parts:
        location=", ".join(dict.fromkeys(parts))
        if mode and mode.lower() not in location.lower():
            location=f"{location} - {mode}"
        return location, remote_hint

    if mode:
        return mode, remote_hint
    return "", remote_hint


def parse_generic_job_page(html: str, url: str, company: dict, fallback_title: str) -> Job:
    soup=BeautifulSoup(html,"html.parser")
    data=_jsonld_job(soup)
    visible=" ".join(soup.stripped_strings)
    title=str(data.get("title") or "") if data else ""
    if not title:
        h1=soup.find("h1")
        title=" ".join(h1.stripped_strings) if h1 else fallback_title
    raw_desc=(data.get("description") or "") if data else ""
    desc=BeautifulSoup(raw_desc,"html.parser").get_text(" ",strip=True) if raw_desc else visible
    loc,remote=_location(data,visible)
    posted=(data.get("datePosted") or "") if data else ""
    return Job(
        source=f"Career page:{company['name']}", source_kind="official career page",
        company=company["name"], sector=company.get("sector","Fintech"),
        title=title, location=loc, description=desc, apply_url=url,
        external_id=url, posted_at=posted, remote_hint=remote,
        employment_type=str(data.get("employmentType") or "") if data else "",
    ).finalize()


async def fetch_generic(http, company: dict):
    url = company["careers_url"]
    r = await http.get(url)
    r.raise_for_status()
    html = r.text
    final_url = str(r.url)
    detected = detect_ats(html, final_url)
    links = generic_job_links(html, final_url)

    # Enrich only links whose title already looks relevant. This raises coverage for
    # custom career sites/Teamtailor-like pages without hammering every job detail page.
    relevant = [x for x in links if STRONG_TITLE.search(x.get("title", ""))][:24]
    enriched: dict[str, Job] = {}
    async def one(x):
        try:
            rr=await http.get(x["url"])
            rr.raise_for_status()
            return parse_generic_job_page(rr.text, str(rr.url), company, x["title"])
        except Exception:
            return None
    if relevant:
        results=await asyncio.gather(*(one(x) for x in relevant))
        for job in results:
            if isinstance(job,Job):
                enriched[job.apply_url]=job

    jobs=[]
    for x in links:
        if x["url"] in enriched:
            jobs.append(enriched[x["url"]]); continue
        jobs.append(Job(
            source=f"Career page:{company['name']}", source_kind="official career page",
            company=company["name"], sector=company.get("sector", "Fintech"),
            title=x["title"], location="", description="", apply_url=x["url"],
            external_id=x["url"],
        ).finalize())
    return jobs, detected, final_url
