from __future__ import annotations
from job_radar.models import Job


async def fetch_breezy(http, company: dict, slug: str):
    url = f"https://{slug}.breezy.hr/json"
    r = await http.get(url)
    r.raise_for_status()
    data = r.json()
    jobs = []
    if isinstance(data, dict):
        data = data.get("positions") or data.get("jobs") or []
    for x in data if isinstance(data, list) else []:
        loc = x.get("location") or {}
        if isinstance(loc, dict):
            loc = loc.get("name") or loc.get("city") or ""
        jobs.append(Job(
            source=f"Breezy:{slug}", source_kind="official ATS",
            company=company["name"], sector=company.get("sector", "Fintech"),
            title=x.get("name") or x.get("title") or "", location=str(loc),
            description=x.get("description") or "", apply_url=x.get("url") or f"https://{slug}.breezy.hr/",
            external_id=str(x.get("id") or x.get("friendly_id") or ""),
        ).finalize())
    return jobs
