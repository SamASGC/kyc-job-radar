from __future__ import annotations
import re
from urllib.parse import urlsplit
from job_radar.models import Job


async def fetch_workday(http, company: dict, careers_url: str):
    p = urlsplit(careers_url)
    host = p.netloc
    parts = [x for x in p.path.split('/') if x]
    if not host or "myworkdayjobs.com" not in host or not parts:
        return []
    tenant = host.split('.')[0]
    site = parts[0]
    endpoint = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    payload = {"appliedFacets": {}, "limit": 100, "offset": 0, "searchText": ""}
    jobs = []
    offset = 0
    while offset < 500:
        payload["offset"] = offset
        r = await http.post(endpoint, json=payload, headers={"Content-Type": "application/json"})
        if r.status_code >= 400:
            break
        data = r.json()
        batch = data.get("jobPostings") or []
        for x in batch:
            ext = x.get("externalPath") or ""
            apply = f"https://{host}{p.path.rstrip('/')}{ext}" if ext.startswith('/') else careers_url
            jobs.append(Job(
                source=f"Workday:{tenant}/{site}", source_kind="official ATS",
                company=company["name"], sector=company.get("sector", "Fintech"),
                title=x.get("title", ""), location=x.get("locationsText", ""), description="",
                apply_url=apply, external_id=ext, posted_at=x.get("postedOn", ""),
            ).finalize())
        if len(batch) < 100:
            break
        offset += 100
    return jobs
