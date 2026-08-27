from __future__ import annotations

import asyncio
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from job_radar.models import Job


def _text(node, name):
    el = node.find(name)
    return (el.text or "").strip() if el is not None and el.text else ""


def _plain_html(value: str | None) -> str:
    return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)


def _find_jobposting_jsonld(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw)
        except Exception:
            continue
        queue = data if isinstance(data, list) else [data]
        for item in queue:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "JobPosting":
                return item
            graph = item.get("@graph")
            if isinstance(graph, list):
                for sub in graph:
                    if isinstance(sub, dict) and sub.get("@type") == "JobPosting":
                        return sub
    return {}


def _location_from_jsonld(data: dict, visible_text: str = "") -> tuple[str, str]:
    remote_hint = ""
    pieces: list[str] = []
    if str(data.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        remote_hint = "Remote"
    req = data.get("applicantLocationRequirements")
    reqs = req if isinstance(req, list) else ([req] if req else [])
    for x in reqs:
        if isinstance(x, dict):
            name = x.get("name")
            if name:
                pieces.append(str(name))
            addr = x.get("address")
            if isinstance(addr, dict):
                for key in ("addressLocality", "addressRegion", "addressCountry"):
                    if addr.get(key): pieces.append(str(addr[key]))
    loc = data.get("jobLocation")
    locs = loc if isinstance(loc, list) else ([loc] if loc else [])
    for x in locs:
        if isinstance(x, dict):
            addr = x.get("address") or {}
            if isinstance(addr, dict):
                vals = [addr.get(k) for k in ("addressLocality", "addressRegion", "addressCountry") if addr.get(k)]
                if vals:
                    pieces.append(", ".join(str(v) for v in vals))
    if not pieces:
        if re.search(r"\bremote\s+global\b", visible_text, re.I):
            return "Remote Global", "Remote"
        if re.search(r"\bremote\b", visible_text, re.I):
            return "Remote", "Remote"
    # Preserve order, drop duplicates.
    seen = set(); clean=[]
    for p in pieces:
        k=p.casefold()
        if k not in seen:
            seen.add(k); clean.append(p)
    loc_text = ", ".join(clean)
    if remote_hint and not loc_text:
        loc_text = "Remote"
    return loc_text, remote_hint


def parse_personio_job_page(html: str, url: str, company: dict, account: str) -> Job:
    """Parse a public Personio job page, preferring schema.org JobPosting when available."""
    soup = BeautifulSoup(html, "html.parser")
    data = _find_jobposting_jsonld(soup)
    visible = " ".join(soup.stripped_strings)
    title = str(data.get("title") or "") if data else ""
    if not title:
        h1 = soup.find("h1")
        title = " ".join(h1.stripped_strings) if h1 else "Job opening"
    desc = _plain_html(data.get("description") if data else "")
    if not desc:
        main = soup.find("main") or soup.body or soup
        desc = " ".join(main.stripped_strings)
    location, remote_hint = _location_from_jsonld(data, visible)
    if not location:
        # Personio's rendered pages commonly put the location directly below the title.
        m = re.search(r"\b(Remote\s+Global|Remote\s+Europe|Remote|Hybrid|On-site|Onsite)\b", visible, re.I)
        if m:
            location = m.group(1)
            if "remote" in location.lower():
                remote_hint = "Remote"
    m = re.search(r"/job/(\d+)", url)
    jid = m.group(1) if m else url
    salary = ""
    base_salary = data.get("baseSalary") if data else None
    if isinstance(base_salary, dict):
        currency = base_salary.get("currency") or ""
        value = base_salary.get("value") or {}
        if isinstance(value, dict):
            lo, hi = value.get("minValue"), value.get("maxValue")
            if lo or hi:
                salary = f"{currency} {lo or ''}–{hi or ''}".strip()
    return Job(
        source=f"Personio:{account}", source_kind="official ATS",
        company=company["name"], sector=company.get("sector", "Fintech"),
        title=title, location=location, description=desc, apply_url=url,
        external_id=jid, posted_at=(data.get("datePosted") or "") if data else "",
        salary_text=salary, remote_hint=remote_hint,
        employment_type=str(data.get("employmentType") or "") if data else "",
    ).finalize()


async def _fetch_public_career_pages(http, company: dict, account: str) -> list[Job]:
    last_error = None
    for domain in ("jobs.personio.com", "jobs.personio.de"):
        index_url = f"https://{account}.{domain}/"
        try:
            r = await http.get(index_url)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            links = []
            seen = set()
            for a in soup.find_all("a", href=True):
                href = urljoin(str(r.url), a.get("href", ""))
                if not re.search(r"/job/\d+", href):
                    continue
                href = href.split("?", 1)[0]
                if href not in seen:
                    seen.add(href); links.append(href)
            if not links:
                continue
            async def one(u):
                rr = await http.get(u)
                rr.raise_for_status()
                return parse_personio_job_page(rr.text, str(rr.url), company, account)
            results = await asyncio.gather(*(one(u) for u in links[:100]), return_exceptions=True)
            jobs = [x for x in results if isinstance(x, Job)]
            if jobs:
                return jobs
        except Exception as e:
            last_error = e
    if last_error:
        raise last_error
    return []


async def fetch_personio(http, company: dict, account: str):
    """Try Personio XML first, then public career pages when the employer has not enabled XML."""
    response = None
    last_error = None
    for domain in ("jobs.personio.com", "jobs.personio.de"):
        url = f"https://{account}.{domain}/xml?language=en"
        try:
            r = await http.get(url)
            if r.status_code == 200 and "<" in r.text:
                try:
                    root = ET.fromstring(r.text)
                    if root.findall(".//position"):
                        response = r
                        break
                except ET.ParseError:
                    pass
            last_error = RuntimeError(f"{url} -> feed unavailable or empty (HTTP {r.status_code})")
        except Exception as e:
            last_error = e

    jobs: list[Job] = []
    if response is not None:
        root = ET.fromstring(response.text)
        for pos in root.findall(".//position"):
            title = _text(pos, "name")
            office = _text(pos, "office")
            city = _text(pos, "recruitingCategory")
            loc = office or city
            desc_parts = []
            for jd in pos.findall(".//jobDescription"):
                for child in list(jd):
                    if child.text:
                        desc_parts.append(child.text.strip())
            desc = " ".join(x for x in desc_parts if x)
            jid = _text(pos, "id")
            host = str(response.url).split("/xml", 1)[0]
            apply = f"{host}/job/{jid}" if jid else host + "/"
            jobs.append(Job(
                source=f"Personio:{account}", source_kind="official ATS",
                company=company["name"], sector=company.get("sector", "Fintech"),
                title=title, location=loc, description=desc, apply_url=apply,
                external_id=jid,
            ).finalize())
    if jobs:
        return jobs

    # XML is optional in Personio. The public career page is still usable and is the
    # important fallback for employers such as Peratera.
    fallback = await _fetch_public_career_pages(http, company, account)
    if fallback:
        return fallback
    raise last_error or RuntimeError("Personio public jobs unavailable")
