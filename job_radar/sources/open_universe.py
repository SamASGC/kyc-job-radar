from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from job_radar.models import Job


# Open-employer discovery is JD-first. We search the advert body, not just the title,
# because a generic role name can still have KYC/AML/EDD/SoF/SoW as its daily work.
JD_QUERIES = [
    "kyc",
    "kyb",
    "aml",
    "customer due diligence",
    "client due diligence",
    "enhanced due diligence",
    "source of funds",
    "source of wealth",
    "beneficial ownership",
    "pep screening",
    "adverse media",
    "sanctions screening",
    "transaction monitoring",
    "financial crime",
    "periodic review",
    "remediation",
    "customer risk assessment",
    "screening",
]

# Tiny fallback for the minority of jobs whose source does not expose a description.
TITLE_FALLBACK_QUERIES = ["kyc", "aml"]

ONSITE_COUNTRIES = "ES,LU,CH,EE,CZ,MT"


def _dedupe(jobs: list[Job]) -> list[Job]:
    out: dict[str, Job] = {}
    for job in jobs:
        job.finalize()
        out[job.fingerprint] = job
    return list(out.values())


def _mode_label(value: str) -> str:
    return {
        "remote": "Remote",
        "hybrid": "Hybrid",
        "on_site": "On-site",
        "not_stated": "",
    }.get((value or "").casefold(), value or "")


def _jobopportunities_row(x: dict) -> Job:
    mode = _mode_label(str(x.get("remote") or ""))
    location = str(x.get("location") or "").strip()
    if not location:
        city = str(x.get("city") or "").strip()
        country = str(x.get("country") or "").strip()
        location = ", ".join(v for v in (city, country) if v)
    if mode and mode.casefold() not in location.casefold():
        location = f"{location} - {mode}" if location else mode

    salary = str(x.get("salary_text") or x.get("salary") or "").strip()
    return Job(
        source="Job Opportunities API",
        source_kind="aggregator",
        company=str(x.get("company") or "Unknown"),
        sector="Fintech",
        title=str(x.get("title") or ""),
        location=location,
        description=str(x.get("description") or ""),
        apply_url=str(x.get("apply_url") or ""),
        external_id=str(x.get("id") or x.get("slug") or ""),
        posted_at=str(x.get("posted_at") or x.get("first_seen_at") or ""),
        salary_text=salary,
        remote_hint="Remote" if mode == "Remote" else mode,
        employment_type=str(x.get("employment_type") or ""),
    ).finalize()


async def _get_jobopportunities(http, params: dict) -> list[Job]:
    url = "https://api.jobopportunitiesapi.org/public/jobs"
    # Keyless traffic is documented around 40 requests/minute. The plan below uses
    # 36 body-search slices + 4 small title fallbacks and serializes them deliberately.
    await asyncio.sleep(0.78)
    r = await http.get(url, params=params, headers={"Accept": "application/json"})
    if r.status_code == 429:
        try:
            wait = min(15, max(1, int(r.headers.get("Retry-After") or "2")))
        except ValueError:
            wait = 2
        await asyncio.sleep(wait)
        r = await http.get(url, params=params, headers={"Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    return [_jobopportunities_row(x) for x in data.get("data", []) if isinstance(x, dict)]


async def fetch_jobopportunities_open_universe(http) -> list[Job]:
    """Search full JDs across an open employer universe.

    For every signal we search remote roles globally and onsite/hybrid roles in the
    allowed countries. Titles are not the main discovery gate anymore.
    """
    posted_after = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
    scopes = [
        {"remote": "remote"},
        {"country": ONSITE_COUNTRIES},
    ]
    jobs: list[Job] = []

    # Primary discovery: full advert body.
    for term in JD_QUERIES:
        for scope in scopes:
            params = {
                "description_contains": term,
                "limit": 50,
                "include_description": "true",
                "posted_after": posted_after,
                **scope,
            }
            try:
                jobs.extend(await _get_jobopportunities(http, params))
            except Exception:
                # One expensive full-text slice timing out must not kill the scan.
                continue

    # Minimal fallback for postings without an advert body.
    for term in TITLE_FALLBACK_QUERIES:
        for scope in scopes:
            params = {
                "title": term,
                "limit": 50,
                "include_description": "true",
                "posted_after": posted_after,
                **scope,
            }
            try:
                jobs.extend(await _get_jobopportunities(http, params))
            except Exception:
                continue

    return _dedupe(jobs)


def _remotelanders_row(x: dict) -> Job:
    loc = str(x.get("location") or "Remote").strip()
    if "remote" not in loc.casefold() and "worldwide" not in loc.casefold():
        loc = f"{loc} - Remote"
    return Job(
        source="Remote Landers",
        source_kind="aggregator",
        company=str(x.get("company") or "Unknown"),
        sector="Fintech",
        title=str(x.get("title") or ""),
        location=loc,
        description=" ".join(str(v) for v in (x.get("category"), " ".join(x.get("subtags") or [])) if v),
        apply_url=str(x.get("applyUrl") or x.get("url") or ""),
        external_id=str(x.get("slug") or ""),
        posted_at=str(x.get("postedDate") or ""),
        salary_text=str(x.get("salary") or ""),
        remote_hint="Remote",
        employment_type=str(x.get("type") or ""),
    ).finalize()


async def fetch_remote_landers(http, max_pages: int = 10) -> list[Job]:
    """Read ATS-direct remote jobs from Remote Landers' public API."""
    jobs: list[Job] = []
    for page in range(1, max_pages + 1):
        r = await http.get(
            "https://remotelanders.com/api/jobs",
            params={"limit": 100, "page": page},
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        batch = data.get("jobs") or []
        for x in batch:
            if isinstance(x, dict):
                jobs.append(_remotelanders_row(x))
        total = int(data.get("total") or 0)
        if not batch or page * 100 >= total:
            break
    return _dedupe(jobs)
