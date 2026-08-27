from __future__ import annotations

import html
from job_radar.models import Job


async def fetch_greenhouse(http, company: dict, slug: str, eu: bool = False):
    host = "https://boards-api.greenhouse.io" if not eu else "https://boards-api.greenhouse.io"
    url = f"{host}/v1/boards/{slug}/jobs?content=true"
    r = await http.get(url)
    r.raise_for_status()
    data = r.json()
    jobs = []
    for x in data.get("jobs", []):
        loc = (x.get("location") or {}).get("name", "")
        content = html.unescape(x.get("content") or "")
        jobs.append(Job(
            source=f"Greenhouse:{slug}", source_kind="official ATS",
            company=company["name"], sector=company.get("sector", "Fintech"),
            title=x.get("title", ""), location=loc, description=content,
            apply_url=x.get("absolute_url", ""), external_id=str(x.get("id", "")),
            posted_at=x.get("updated_at", "") or "",
        ).finalize())
    return jobs
