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
