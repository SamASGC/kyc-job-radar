"""Discover *official* ATS boards referenced by aggregator job links.

Aggregator data is a discovery hint ONLY. A company/job is fetched again from
its ATS and then subject to the exact same original-date/open/Spain gates.
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from job_radar.models import Job, norm_text


def ats_target_from_url(url: str) -> dict | None:
    try:
        p = urlsplit(url or "")
        host = (p.hostname or "").lower()
        parts = [unquote(x) for x in p.path.strip("/").split("/") if x]
    except (ValueError, TypeError):
        return None
    if p.scheme != "https" or not parts:
        return None

    kind, slug = "", ""
    if host in {"job-boards.greenhouse.io", "boards.greenhouse.io",
                "job-boards.eu.greenhouse.io"} and len(parts) >= 2:
        kind, slug = "greenhouse", parts[0]
    elif host in {"jobs.lever.co", "jobs.eu.lever.co"} and len(parts) >= 2:
        kind, slug = ("lever_eu" if host == "jobs.eu.lever.co" else "lever"), parts[0]
    elif host == "jobs.ashbyhq.com" and len(parts) >= 2:
        kind, slug = "ashby", parts[0]
    elif host == "apply.workable.com" and len(parts) >= 2:
        kind, slug = "workable", parts[0]
    elif host.endswith(".jobs.personio.com") and parts[0] == "job":
        kind, slug = "personio", host.removesuffix(".jobs.personio.com")
    elif host.endswith(".breezy.hr") and parts[0] in {"p", "jobs"}:
        kind, slug = "breezy", host.removesuffix(".breezy.hr")
    elif host.endswith(".recruitee.com") and parts[0] in {"o", "offers"}:
        kind, slug = "recruitee", host.removesuffix(".recruitee.com")
    elif host == "jobs.smartrecruiters.com" and len(parts) >= 2:
        kind, slug = "smartrecruiters", parts[0]

    if not slug or not re.fullmatch(r"[a-zA-Z0-9_-]{2,70}", slug):
        return None
    return {"kind": kind, "slug": slug}


def discover_aggregator_ats(
    jobs: list[Job],
    known_names: set[str],
    limit: int = 40,
) -> list[tuple[dict, dict]]:
    """Unique previously unknown ATS company boards; bounded per scan."""
    known = {norm_text(x) for x in known_names}
    result, visited = [], set()
    from job_radar.v2_quality import within_new_window
    ranked = sorted(jobs, key=lambda j: (
        not within_new_window(j.posted_at),
        not any(x in norm_text(j.title) for x in ("kyc", "kyb", "aml", "financial crime", "transaction monitoring")),
    ))
    for j in ranked:
        if j.source_kind != "aggregator" or norm_text(j.company) in {"", "unknown"}:
            continue
        if norm_text(j.company) in known:
            continue
        target = ats_target_from_url(j.apply_url)
        if not target:
            continue
        key = (target["kind"], target["slug"].casefold())
        if key in visited:
            continue
        visited.add(key)
        company = {
            "name": j.company, "sector": j.sector or "Fintech",
            "careers_url": j.apply_url, "enabled": True,
            "priority": "discovered ATS",
        }
        result.append((company, target))
        if len(result) >= limit:
            break
    return result


# These sites are discovery leads, NOT proof that an opening is active.
# Never fetch arbitrary private/internal hosts from untrusted feed records.
AGGREGATOR_DOMAINS = {
    "jobicy.com", "remotive.com", "himalayas.app",
    "remoteok.com", "arbeitnow.com", "weworkremotely.com",
    "remotelanders.com",
}


def approved_feed_url(url: str) -> bool:
    try:
        p = urlsplit(url or "")
        host = (p.hostname or "").casefold()
        return (
            p.scheme == "https"
            and not p.username
            and any(host == domain or host == "www." + domain
                    for domain in AGGREGATOR_DOMAINS)
        )
    except (ValueError, TypeError):
        return False


async def extract_ats_from_aggregator_page(http, lead: Job) -> dict | None:
    """One request to a known job-board result; follow *public* Apply links.

    Returning an ATS board does not verify this specific advertised vacancy.
    The subsequent official ATS re-fetch and strict gates remain mandatory.
    """
    if not approved_feed_url(lead.apply_url):
        return None
    try:
        response = await http.get(lead.apply_url)
        if response.status_code != 200:
            return None
        direct = ats_target_from_url(str(response.url))
        if direct:
            return direct
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text[:220_000], "html.parser")
        from urllib.parse import urljoin
        for a in soup.find_all("a", href=True):
            label = norm_text(a.get_text(" ", strip=True) + " "
                              + str(a.get("aria-label") or ""))
            if not any(token in label for token in (
                "apply", "application", "original job", "company website",
            )):
                continue
            dest = urljoin(str(response.url), a["href"])
            target = ats_target_from_url(dest)
            if target:
                return target
    except Exception:
        return None
    return None


async def discover_ats_via_aggregator_pages(
    http, jobs: list[Job], known_names: set[str],
    max_pages: int = 24, hour_bucket: int = 0,
) -> list[tuple[dict, dict]]:
    """Conservatively enrich official ATS source coverage over successive runs."""
    import asyncio
    known = {norm_text(x) for x in known_names}
    relevant = ("kyc", "kyb", "aml", "edd", "cdd", "sanctions",
                "financial crime", "transaction monitoring",
                "merchant risk", "fraud investigation", "compliance")
    leads = [j for j in jobs
             if j.source_kind == "aggregator"
             and norm_text(j.company) not in known
             and any(x in norm_text(j.title) for x in relevant)
             and approved_feed_url(j.apply_url)]
    leads.sort(key=lambda j: (norm_text(j.company), norm_text(j.title)))
    if not leads or max_pages <= 0:
        return []
    limit = min(max_pages, len(leads))
    start = (hour_bucket * limit) % len(leads)
    sample = [leads[(start + i) % len(leads)] for i in range(limit)]
    results = await asyncio.gather(
        *(extract_ats_from_aggregator_page(http, j) for j in sample),
        return_exceptions=True,
    )
    out, seen_targets = [], set()
    for lead, target in zip(sample, results):
        if not isinstance(target, dict):
            continue
        key = (target["kind"], target["slug"].casefold())
        if key in seen_targets:
            continue
        seen_targets.add(key)
        out.append(({
            "name": lead.company, "sector": lead.sector or "Fintech",
            "careers_url": lead.apply_url, "enabled": True,
            "priority": "discovered ATS from aggregator",
        }, target))
    return out
