from __future__ import annotations
from job_radar.models import Job


async def fetch_smartrecruiters(http, company: dict, slug: str):
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100"
    r = await http.get(url)
    r.raise_for_status()
    data = r.json()
    items = data.get("content") or data.get("postings") or []
    jobs = []
    for x in items:
        jid = x.get("id") or x.get("uuid") or ""
        detail = {}
        try:
            d = await http.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{jid}")
            if d.status_code == 200:
                detail = d.json()
        except Exception:
            pass
        locd = detail.get("location") or x.get("location") or {}
        if isinstance(locd, dict):
            loc = ", ".join([v for v in [locd.get("city"), locd.get("region"), locd.get("country")] if v])
        else:
            loc = str(locd)
        sections = detail.get("jobAd") or {}
        sec_text = []
        if isinstance(sections, dict):
            for v in sections.values():
                if isinstance(v, dict):
                    sec_text.append(v.get("text") or "")
        desc = "\n".join(sec_text)
        jobs.append(Job(
            source=f"SmartRecruiters:{slug}", source_kind="official ATS",
            company=company["name"], sector=company.get("sector", "Fintech"),
            title=detail.get("name") or x.get("name") or "", location=loc,
            description=desc, apply_url=detail.get("applyUrl") or x.get("applyUrl") or detail.get("jobAdUrl") or "",
            external_id=str(jid), posted_at=detail.get("releasedDate") or x.get("releasedDate") or "",
        ).finalize())
    return jobs
