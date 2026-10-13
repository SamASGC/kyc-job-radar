"""VP Bank public Umantis vacancy parser, preserving job-specific original dates.

Only exact /Vacancies/<id>/Description/<lang> paths are admitted.
'Online since' dates come from the recruiting portal, never crawler timestamps.
"""
from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from job_radar.models import Job

HOST = "recruitingapp-2813.umantis.com"
JOB_PATH = re.compile(r"^/Vacancies/([0-9]+)/Description/([0-9]+)/?$")
ONLINE_SINCE = re.compile(r"\bOnline since:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})\b", re.I)


def _official_date(row) -> str:
    for span in row.select("span.tableaslist_text"):
        match = ONLINE_SINCE.search(span.get_text(" ", strip=True))
        if match:
            try:
                return datetime.strptime(match.group(1), "%m/%d/%Y").date().isoformat()
            except ValueError:
                return ""
    return ""


def _location(row) -> str:
    text = row.get_text(" ", strip=True)
    if re.search(r"\bLuxembourg\b", text, re.I):
        return "Luxembourg"
    if re.search(r"\b(?:Zurich|Zürich)\b", text, re.I):
        return "Zurich, Switzerland"
    if re.search(r"VP Bank \(Schweiz\)|\bSwitzerland\b", text, re.I):
        return "Switzerland"
    if re.search(r"\bSingapore\b", text, re.I):
        return "Singapore"
    if re.search(r"\bLiechtenstein\b", text, re.I):
        return "Liechtenstein"
    return ""


def parse_vp_bank_umantis_page(html: str, url: str, company: dict) -> list[Job]:
    if (urlsplit(url).hostname or "").casefold() != HOST:
        return []
    soup = BeautifulSoup(html, "html.parser")
    result = []
    seen = set()
    for row in soup.select("table.tableaslist tr"):
        a = row.select_one("a.HSTableLinkSubTitle[href]")
        if a is None:
            continue
        full = urljoin(url, a.get("href", ""))
        p = urlsplit(full)
        match = JOB_PATH.fullmatch(p.path)
        if p.scheme != "https" or (p.hostname or "").casefold() != HOST or not match:
            continue
        job_id = match.group(1)
        if job_id in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        seen.add(job_id)
        result.append(Job(
            source="Career page:VP Bank Group", source_kind="official career page",
            company=company["name"], sector=company.get("sector", "Banca"),
            title=title, location=_location(row), description="",
            apply_url=full, external_id=full, posted_at=_official_date(row),
        ).finalize())
    return result
