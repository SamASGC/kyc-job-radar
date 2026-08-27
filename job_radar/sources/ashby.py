from __future__ import annotations
from job_radar.models import Job


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
            apply_url=x.get("jobUrl") or x.get("applyUrl") or "", external_id=x.get("id", ""),
            posted_at=x.get("publishedAt", "") or "", salary_text=salary,
            employment_type=x.get("employmentType", "") or "",
        ).finalize())
    return jobs
