"""Official Workday list and bounded, role-specific CXS detail enrichment.

List dates ("Posted Yesterday", absent) are NEVER trusted as original dates.
A matching public job detail's absolute startDate is required for 96h alerts.
Only candidates plausibly fresh (or no list date) and role-relevant receive
detail lookups; this avoids thousands of unnecessary Workday requests.
"""
from __future__ import annotations

import asyncio
import re
from urllib.parse import urlsplit

from job_radar.models import Job
from job_radar.v2_quality import original_posted_at, within_new_window, location_allowed
from job_radar.workday_detail import (
    workday_board, fetch_workday_detail, workday_original_date,
)

_TITLE = re.compile(
    r"\b(kyc|kyb|aml|cdd|edd|financial crime|fincrime|compliance|"
    r"sanction|screening|fraud|due diligence|monitoring|"
    r"investigat|risk analyst|risk operations|risk specialist|"
    r"client review|client onboarding|client acceptance|"
    r"regulatory reporting|regulatory control)\b", re.I,
)
_NEARBY = re.compile(
    r"\b(spain|espana|madrid|valencia|malaga|seville|"
    r"switzerland|swiss|zurich|geneva|basel|gland|lugano|"
    r"luxembourg|estonia|tallinn|lithuania|vilnius|kaunas|remote)\b", re.I,
)
_RELATIVE = re.compile(r"\bposted\s+(\d+)\s+days?\s+ago\b", re.I)
_DETAIL_LIMIT = 36


def possibly_recent_workday_listing(value: str) -> bool:
    """Relative 'Posted 2 Days Ago' is a prefetch hint ONLY, never a date."""
    val = str(value or "").strip()
    if not val:
        return True
    low = val.casefold()
    if "today" in low or "yesterday" in low or "hour" in low:
        return True
    match = _RELATIVE.search(low)
    if match:
        return int(match.group(1)) <= 4
    if "30+" in low or "week" in low or "month" in low:
        return False
    if original_posted_at(val) is not None:
        return within_new_window(val)
    # Unknown, nonstandard listing label: get exact date instead of guessing.
    return True


async def fetch_workday(http, company: dict, careers_url: str, search_terms: list[str] | None = None):
    board = workday_board(careers_url)
    if board is None:
        return []
    host, tenant, site, prefix = board
    endpoint = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    page_size = 20
    payload = {"appliedFacets": {}, "limit": page_size, "offset": 0, "searchText": ""}
    jobs_by_req: dict[str, Job] = {}
    # Huge banks can post thousands of jobs; first 500 generic records
    # may be mostly sales and unrelated roles. A manually verified board
    # may opt into targeted first-party Workday searchText queries. The
    # same exact requisition is not duplicated across overlapping terms.
    terms = list(dict.fromkeys(str(x).strip() for x in (search_terms or [""])
                               if str(x).strip()))[:8] if search_terms else [""]
    max_per_term = 120 if search_terms else 500
    for term in terms:
        payload["searchText"] = term
        offset = 0
        while offset < max_per_term:
            payload["offset"] = offset
            response = await http.post(
                endpoint, json=payload, headers={"Content-Type": "application/json"}
            )
            if response.status_code >= 400:
                if offset == 0:
                    response.raise_for_status()
                    raise RuntimeError(f"Workday API HTTP {response.status_code}")
                # Partial failures never justify inventing any opening/date.
                break
            data = response.json()
            batch = data.get("jobPostings") or []
            for row in batch:
                external = str(row.get("externalPath") or "")
                if not external.startswith("/job/") or external in jobs_by_req:
                    continue
                application_url = f"https://{host}{prefix}{external}"
                job = Job(
                    source=f"Workday:{tenant}/{site}", source_kind="official ATS",
                    company=company["name"], sector=company.get("sector", "Fintech"),
                    title=row.get("title", ""), location=row.get("locationsText", ""),
                    description="", apply_url=application_url, external_id=external,
                    # Relative labels are hints for limited detail fetching,
                    # never the official startDate or a publishable date.
                    posted_at=(str(row.get("postedOn") or "")
                               if original_posted_at(row.get("postedOn") or "") is not None
                               else ""),
                ).finalize()
                job._workday_list_posted_on = str(row.get("postedOn") or "")
                jobs_by_req[external] = job
            if len(batch) < page_size:
                break
            offset += page_size
    jobs = list(jobs_by_req.values())

    candidates = [
        job for job in jobs
        if _TITLE.search(job.title or "") and
        possibly_recent_workday_listing(
            getattr(job, "_workday_list_posted_on", "")
        )
    ]
    # Prefer geographically relevant candidates when the bounded detail
    # quota is exhausted; never infer Spain eligibility from global/EMEA.
    candidates.sort(key=lambda job: (
        not location_allowed(job),
        not bool(_NEARBY.search(job.location or "")),
        job.title.casefold(),
    ))
    candidates = candidates[:_DETAIL_LIMIT]
    gate = asyncio.Semaphore(5)

    async def enrich(job: Job):
        async with gate:
            try:
                info = await fetch_workday_detail(http, job)
                if not info:
                    return
                posted = workday_original_date(info, job)
                if posted:
                    job.posted_at = posted
                # Real Workday job requirements, not empty list snippets.
                if info.get("jobDescription"):
                    job.description = str(info["jobDescription"])
                # Never infer remotely eligible Spain just from the word
                # "remote"; official ATS location still controls geography.
                if not job.location and info.get("location"):
                    job.location = str(info["location"])
                job.fingerprint = ""
                job.finalize()
            except Exception:
                # Inconclusive detail fetch: leave undated; strict gate rejects.
                return

    if candidates:
        await asyncio.gather(*(enrich(job) for job in candidates))
    return jobs
