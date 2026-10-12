from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
import json

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

# Onsite/hybrid remains intentionally narrow. Remote discovery is Europe-only.
ONSITE_COUNTRIES = "ES,LU,CH,EE,LT"
EUROPE_REMOTE_COUNTRIES = (
    "AL,AT,BE,BA,BG,HR,CY,CZ,DK,EE,FI,FR,DE,GR,HU,IS,IE,IT,LV,LI,LT,LU,MT,ME,"
    "NL,MK,NO,PL,PT,RO,RS,SK,SI,ES,SE,CH,GB"
)


def selected_company_domain_batches(directory: list[dict], hour_bucket: int,
                                    companies_per_hour: int = 80,
                                    domains_per_request: int = 20) -> list[list[str]]:
    """Rotate reliable company websites through employer-domain API queries."""
    domains, unique = [], set()
    for entry in directory:
        try:
            web = urlsplit(str(entry.get("website") or ""))
            host = (web.hostname or "").lower().removeprefix("www.")
        except (ValueError, TypeError, AttributeError):
            continue
        if web.scheme != "https" or not host or "." not in host or host in unique:
            continue
        unique.add(host)
        domains.append(host)
    domains.sort()
    if not domains or companies_per_hour <= 0 or domains_per_request <= 0:
        return []
    n = min(companies_per_hour, len(domains))
    start = (hour_bucket * n) % len(domains)
    sampled = [domains[(start + i) % len(domains)] for i in range(n)]
    return [sampled[i:i + domains_per_request]
            for i in range(0, len(sampled), domains_per_request)]


async def fetch_licensed_employer_domain_jobs(http, directory_path: Path,
                                               companies_per_hour: int = 80) -> tuple[list[Job], dict]:
    """Discover leads by employer domains from an attributed/licensed directory.

    The company_domain filter is documented by Job Opportunities API. These
    are still AGGREGATOR leads, and cannot be delivered without independent
    official ATS verification later in the pipeline.
    """
    if not directory_path.exists():
        return [], {"queried_domains": 0, "batches": 0, "results": 0, "errors": 0}
    directory = json.loads(directory_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    batches = selected_company_domain_batches(
        directory, int(now.timestamp() // 3600), companies_per_hour
    )
    posted_after = (now - timedelta(days=5)).date().isoformat()
    results = []
    errors = 0
    for domains in batches:
        params = {
            "company_domain": ",".join(domains),
            "limit": 50,
            "include_description": "true",
            "posted_after": posted_after,
        }
        try:
            results.extend(await _get_jobopportunities(http, params))
        except Exception:
            errors += 1
    return _dedupe(results), {
        "queried_domains": sum(len(b) for b in batches),
        "batches": len(batches), "results": len(results), "errors": errors,
    }


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
    country = str(x.get("country") or "").strip()
    if not location:
        city = str(x.get("city") or "").strip()
        location = ", ".join(v for v in (city, country) if v)
    elif country and country.casefold() not in location.casefold():
        # Preserve the API's explicit country code so the final Europe gate can verify it.
        location = f"{location}, {country}"
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
    # Keyless traffic is documented around 40 requests/minute. We serialize deliberately.
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
    """Search full JDs across an open employer universe, restricted to Europe.

    For every signal we search remote jobs whose published country is European, plus
    onsite/hybrid jobs in the specifically authorised countries. Titles are not the main
    discovery gate.
    """
    posted_after = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
    scopes = [
        {"remote": "remote", "country": EUROPE_REMOTE_COUNTRIES},
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
    """Read ATS-direct remote jobs; the central Europe gate filters eligibility afterwards."""
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
