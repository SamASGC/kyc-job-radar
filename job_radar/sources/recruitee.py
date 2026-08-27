from __future__ import annotations
from job_radar.models import Job


async def fetch_recruitee(http, company: dict, slug: str):
    url = f"https://{slug}.recruitee.com/api/offers/"
    r = await http.get(url)
    r.raise_for_status()
    data = r.json()
    jobs = []
    for x in data.get("offers", []):
        loc = x.get("location") or ""
        if isinstance(loc, dict):
            loc = loc.get("city") or loc.get("name") or ""
        jobs.append(Job(
            source=f"Recruitee:{slug}", source_kind="official ATS",
            company=company["name"], sector=company.get("sector", "Fintech"),
            title=x.get("title", ""), location=str(loc), description=x.get("description", "") or "",
            apply_url=x.get("careers_url") or x.get("url") or f"https://{slug}.recruitee.com/",
            external_id=str(x.get("id", "")),
        ).finalize())
    return jobs
