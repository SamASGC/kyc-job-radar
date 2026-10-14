"""Public Sygnum Salesforce vacancy list; preserves individual vacancyNo URLs.

Not an authenticated Salesforce API. The employer publishes these pages publicly.
No posting timestamp is available on the list, so this source never fabricates one.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlsplit
from bs4 import BeautifulSoup
from job_radar.models import Job


SYGNUM_HOST = "sygnumpeopleportal.my.salesforce-sites.com"
SYGNUM_LIST = "https://" + SYGNUM_HOST + "/recruit/fRecruit__ApplyJobList"


def parse_sygnum_vacancies(html: str, page_url: str, company: dict) -> list[Job]:
    if (urlsplit(page_url).hostname or "").lower() != SYGNUM_HOST:
        return []
    soup = BeautifulSoup(html, "html.parser")
    jobs: dict[str, Job] = {}
    for a in soup.select("a[href]"):
        full = urljoin(page_url, a.get("href", ""))
        p = urlsplit(full)
        if (p.hostname or "").lower() != SYGNUM_HOST or p.path != "/recruit/fRecruit__ApplyJob":
            continue
        selectors = parse_qs(p.query)
        ids = selectors.get("vacancyNo", [])
        if len(ids) != 1 or not re.fullmatch(r"VN\d+", ids[0], re.I):
            continue
        title = a.get_text(" ", strip=True)
        if not title or title.casefold() in ("apply", "apply now", "job details"):
            continue
        cells = a.find_parent("tr")
        cols = [c.get_text(" ", strip=True) for c in cells.find_all("td")] if cells else []
        location = ", ".join(v for v in (cols[2:3] + cols[1:2]) if v)
        mode = cols[5] if len(cols) > 5 else ""
        if mode:
            location = f"{location} - {mode}" if location else mode
        job = Job(
            source="Sygnum Salesforce careers", source_kind="official career page",
            company=company["name"], sector=company.get("sector", "Banca"),
            title=title, location=location, description="",
            apply_url=full, external_id=ids[0], posted_at="",
            employment_type=cols[3] if len(cols) > 3 else "",
        ).finalize()
        jobs[ids[0].upper()] = job
    return list(jobs.values())
