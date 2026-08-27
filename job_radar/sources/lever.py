from __future__ import annotations

from job_radar.models import Job


async def fetch_lever(http, company: dict, slug: str, eu: bool = False):
    base = "https://api.eu.lever.co" if eu else "https://api.lever.co"
    url = f"{base}/v0/postings/{slug}?mode=json"
    r = await http.get(url)
    r.raise_for_status()
    data = r.json()
    jobs = []
    for x in data if isinstance(data, list) else []:
        cats = x.get("categories") or {}
        loc = cats.get("location") or ""
        desc = "\n".join(filter(None, [x.get("descriptionPlain", ""), x.get("additionalPlain", "")]))
        jobs.append(Job(
            source=f"Lever:{slug}", source_kind="official ATS",
            company=company["name"], sector=company.get("sector", "Fintech"),
            title=x.get("text", ""), location=loc, description=desc,
            apply_url=x.get("hostedUrl") or x.get("applyUrl") or "",
            external_id=x.get("id", ""), employment_type=cats.get("commitment") or "",
        ).finalize())
    return jobs
