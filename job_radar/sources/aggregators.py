from __future__ import annotations

from datetime import datetime, timezone
import html as html_lib
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

from job_radar.models import Job


def _plain(value: str | None) -> str:
    if not value:
        return ""
    return BeautifulSoup(html_lib.unescape(str(value)), "html.parser").get_text(" ", strip=True)


def _dedupe(jobs: list[Job]) -> list[Job]:
    out = {}
    for j in jobs:
        j.finalize()
        out[j.fingerprint] = j
    return list(out.values())


async def fetch_jobicy(http):
    """Broad Europe feed + targeted keyword queries so niche KYC/AML jobs aren't pushed out by newer tech jobs."""
    base = "https://jobicy.com/api/v2/remote-jobs"
    queries = [None, "kyc", "kyb", "aml", "compliance", "financial crime", "transaction monitoring", "sanctions", "onboarding"]
    jobs: list[Job] = []
    for q in queries:
        params = {"count": 200, "geo": "europe"}
        if q:
            params["tag"] = q
        r = await http.get(base, params=params)
        r.raise_for_status()
        data = r.json()
        for x in data.get("jobs", []):
            company = x.get("companyName") or x.get("company") or "Unknown"
            salary = x.get("annualSalaryMin") or x.get("salaryMin")
            salary_to = x.get("annualSalaryMax") or x.get("salaryMax")
            curr = x.get("salaryCurrency") or ""
            sal = ""
            if salary or salary_to:
                sal = f"{curr} {salary or ''}–{salary_to or ''}".strip()
            jobs.append(Job(
                source="Jobicy", source_kind="aggregator",
                company=company, sector="Fintech", title=x.get("jobTitle") or x.get("title") or "",
                location=x.get("jobGeo") or x.get("location") or "Remote Europe",
                description=_plain(x.get("jobDescription") or x.get("description") or x.get("jobExcerpt") or ""),
                apply_url=x.get("url") or x.get("jobUrl") or "",
                external_id=str(x.get("id") or x.get("jobId") or x.get("jobSlug") or ""),
                posted_at=x.get("pubDate") or x.get("date") or "",
                salary_text=sal, remote_hint="Remote Europe",
                employment_type=", ".join(x.get("jobType") or []) if isinstance(x.get("jobType"), list) else (x.get("jobType") or ""),
            ).finalize())
    return _dedupe(jobs)


async def fetch_remotive(http):
    # Remotive recommends only a few requests/day. Scanner caches this source for 6h.
    r = await http.get("https://remotive.com/api/remote-jobs")
    r.raise_for_status()
    data = r.json()
    jobs = []
    for x in data.get("jobs", []):
        jobs.append(Job(
            source="Remotive", source_kind="aggregator",
            company=x.get("company_name") or "Unknown", sector="Fintech",
            title=x.get("title") or "", location=x.get("candidate_required_location") or "Remote",
            description=_plain(x.get("description") or ""), apply_url=x.get("url") or "",
            external_id=str(x.get("id") or ""), posted_at=x.get("publication_date") or "",
            salary_text=x.get("salary") or "", remote_hint="Remote",
            employment_type=x.get("job_type") or "",
        ).finalize())
    return _dedupe(jobs)


async def fetch_arbeitnow(http, max_pages: int = 10):
    """Walk more pages than v2; filtering/scoring happens after fetch."""
    jobs = []
    for page in range(1, max_pages + 1):
        r = await http.get(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        r.raise_for_status()
        data = r.json()
        for x in data.get("data", []):
            tags = " ".join(x.get("tags") or [])
            created = x.get("created_at")
            posted = ""
            if created:
                try:
                    posted = datetime.fromtimestamp(int(created), tz=timezone.utc).isoformat()
                except (TypeError, ValueError, OSError, OverflowError):
                    posted = str(created)
            jobs.append(Job(
                source="Arbeitnow", source_kind="aggregator",
                company=x.get("company_name") or "Unknown", sector="Fintech",
                title=x.get("title") or "", location=x.get("location") or ("Remote Europe" if x.get("remote") else ""),
                description=_plain(x.get("description") or "") + " " + tags,
                apply_url=x.get("url") or "", external_id=x.get("slug") or x.get("url") or "",
                posted_at=posted, remote_hint="Remote Europe" if x.get("remote") else "",
            ).finalize())
        if not data.get("links", {}).get("next") and not data.get("next_page_url"):
            break
    return _dedupe(jobs)


async def fetch_remoteok(http):
    r = await http.get("https://remoteok.com/api")
    r.raise_for_status()
    data = r.json()
    jobs = []
    for x in data if isinstance(data, list) else []:
        if not isinstance(x, dict) or not x.get("position"):
            continue
        epoch = x.get("epoch")
        posted = ""
        if epoch:
            try:
                posted = datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
            except Exception:
                pass
        jobs.append(Job(
            source="Remote OK", source_kind="aggregator",
            company=x.get("company") or "Unknown", sector="Fintech",
            title=x.get("position") or "", location=x.get("location") or "Remote",
            description=_plain(x.get("description") or ""), apply_url=x.get("url") or "https://remoteok.com/",
            external_id=str(x.get("id") or ""), posted_at=posted,
            salary_text=(f"USD {x.get('salary_min')}–{x.get('salary_max')}" if x.get('salary_min') or x.get('salary_max') else ""),
            remote_hint="Remote",
        ).finalize())
    return _dedupe(jobs)


async def fetch_himalayas(http):
    """Targeted public API searches; source data refreshes roughly daily, so scanner caches 24h."""
    base = "https://himalayas.app/jobs/api/search"
    queries = ["kyc", "kyb", "aml", "compliance", "financial crime", "transaction monitoring", "sanctions", "onboarding"]
    jobs: list[Job] = []
    for q in queries:
        r = await http.get(base, params={"q": q, "sort": "recent", "page": 1})
        r.raise_for_status()
        data = r.json()
        for x in data.get("jobs", []):
            company_obj = x.get("company")
            company_name = x.get("companyName") or (company_obj.get("name") if isinstance(company_obj, dict) else "") or "Unknown"
            locs = x.get("locationRestrictions") or x.get("locations") or []
            if isinstance(locs, list):
                loc = ", ".join(str(v.get("name") if isinstance(v, dict) else v) for v in locs if v)
            else:
                loc = str(locs or "")
            if x.get("worldwide"):
                loc = "Worldwide"
            sal = ""
            if x.get("minSalary") or x.get("maxSalary"):
                sal = f"{x.get('currency','')} {x.get('minSalary','')}–{x.get('maxSalary','')}".strip()
            jobs.append(Job(
                source="Himalayas", source_kind="aggregator",
                company=company_name,
                sector="Fintech", title=x.get("title") or "", location=loc or "Remote",
                description=_plain(x.get("description") or x.get("excerpt") or ""),
                apply_url=x.get("applicationLink") or x.get("url") or x.get("jobUrl") or "https://himalayas.app/jobs",
                external_id=str(x.get("guid") or x.get("id") or ""), posted_at=x.get("pubDate") or x.get("publishedAt") or "",
                salary_text=sal, remote_hint="Remote",
                employment_type=x.get("employmentType") or "",
            ).finalize())
    return _dedupe(jobs)


def _rss_text(item, suffix: str) -> str:
    for child in list(item):
        if child.tag.lower().endswith(suffix.lower()):
            return (child.text or "").strip()
    return ""


async def fetch_weworkremotely(http):
    feeds = [
        "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss",
        "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
        "https://weworkremotely.com/categories/all-other-remote-jobs.rss",
    ]
    jobs: list[Job] = []
    for url in feeds:
        r = await http.get(url)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        for item in root.findall(".//item"):
            raw_title = _rss_text(item, "title")
            company = _rss_text(item, "creator") or "Unknown"
            title = raw_title
            if ":" in raw_title and company == "Unknown":
                left, right = raw_title.split(":", 1)
                if len(left) < 100 and right.strip():
                    company, title = left.strip(), right.strip()
            region = _rss_text(item, "region") or _rss_text(item, "location") or "Remote"
            link = _rss_text(item, "link")
            desc = _plain(_rss_text(item, "description"))
            jobs.append(Job(
                source="We Work Remotely", source_kind="aggregator",
                company=company, sector="Fintech", title=title, location=region,
                description=desc, apply_url=link, external_id=_rss_text(item, "guid") or link,
                posted_at=_rss_text(item, "pubDate"), remote_hint="Remote",
            ).finalize())
    return _dedupe(jobs)
