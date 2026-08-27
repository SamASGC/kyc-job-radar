from __future__ import annotations
from job_radar.models import Job


async def fetch_workable(http, company: dict, slug: str):
    url = f"https://www.workable.com/api/accounts/{slug}?details=true"
    r = await http.get(url)
    r.raise_for_status()
    data = r.json()
    jobs = []
    for x in data.get("jobs", []):
        loc = ", ".join([str(v) for v in [x.get("city"), x.get("state"), x.get("country")] if v])
        desc = x.get("description") or x.get("full_description") or ""
        salary = ""
        if x.get("salary_from") or x.get("salary_to"):
            salary = f"{x.get('salary_currency','')} {x.get('salary_from','')}–{x.get('salary_to','')}".strip()
        jobs.append(Job(
            source=f"Workable:{slug}", source_kind="official ATS",
            company=company["name"], sector=company.get("sector", "Fintech"),
            title=x.get("title", ""), location=loc, description=desc,
            apply_url=x.get("url") or x.get("application_url") or x.get("shortlink") or "",
            external_id=x.get("shortcode") or x.get("code") or "",
            posted_at=x.get("created_at") or "", salary_text=salary,
        ).finalize())
    return jobs
