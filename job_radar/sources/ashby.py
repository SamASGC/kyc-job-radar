from __future__ import annotations
from job_radar.models import Job
from urllib.parse import urlsplit, unquote
import re


def _public_posting_id(row: dict, slug: str) -> str:
    """Ashby public postings frequently lack an id but include a jobUrl."""
    explicit = str(row.get("id") or "").strip()
    if explicit:
        return explicit
    try:
        url = urlsplit(str(row.get("jobUrl") or ""))
        parts = [unquote(part) for part in url.path.split("/") if part]
        if (url.scheme == "https" and url.hostname == "jobs.ashbyhq.com"
                and len(parts) >= 2 and parts[0].casefold() == slug.casefold()
                and re.fullmatch(r"[A-Za-z0-9_-]{3,100}", parts[1])):
            return parts[1]
    except (TypeError, ValueError):
        pass
    return ""


async def fetch_ashby(http, company: dict, slug: str):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
    r = await http.get(url)
    r.raise_for_status()
    data = r.json()
    jobs = []
    for x in data.get("jobs", []):
        if not x.get("isListed", True):
            continue
        comp = x.get("compensation") or {}
        salary = comp.get("scrapeableCompensationSalarySummary") or comp.get("compensationTierSummary") or ""
        jobs.append(Job(
            source=f"Ashby:{slug}", source_kind="official ATS",
            company=company["name"], sector=company.get("sector", "Fintech"),
            title=x.get("title", ""), location=x.get("location", ""),
            description=x.get("descriptionPlain", "") or x.get("descriptionHtml", "") or "",
            apply_url=x.get("jobUrl") or x.get("applyUrl") or "",
            external_id=_public_posting_id(x, slug),
            posted_at=x.get("publishedAt", "") or "", salary_text=salary,
            employment_type=x.get("employmentType", "") or "",
        ).finalize())
    return jobs
