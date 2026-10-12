"""Conservative, evidence-first admission rules for v2.

Unknown != fresh; a date from an aggregator or updated_at is not the
original publication date. These rules run in addition to the existing
role/fit scoring, never in place of it.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from dateutil import parser as dateparser

from job_radar.matching import detect_country, detect_mode
from job_radar.models import Job, norm_text


def original_posted_at(value) -> datetime | None:
    """Parse an absolute posting date; reject relative/indexed/unknown dates."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        epoch = float(value)
        if epoch > 10_000_000_000:
            epoch /= 1000.0
        try:
            return datetime.fromtimestamp(epoch, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    raw = str(value).strip()
    if not raw or re.search(r"\b(today|yesterday|ago|posted|updated|hours?|days?)\b", raw, re.I):
        return None
    if raw.isdigit():
        return original_posted_at(int(raw))
    # No loose/fuzzy dateparser fallbacks ("October" alone, locale ambiguity).
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[Tt ][0-9:.+Zz-]+)?", raw):
        return None
    try:
        dt = dateparser.isoparse(raw)
    except (ValueError, TypeError, OverflowError):
        return None
    return dt.replace(tzinfo=timezone.utc) if not dt.tzinfo else dt.astimezone(timezone.utc)


def within_new_window(value, max_hours: int = 96, now: datetime | None = None) -> bool:
    dt = original_posted_at(value)
    if dt is None:
        return False
    now = now or datetime.now(timezone.utc)
    age = (now - dt).total_seconds()
    return 0 <= age <= max_hours * 3600


def location_allowed(job: Job) -> bool:
    """Require explicit Spain eligibility for remote; narrow relocation shortlist."""
    mode = detect_mode(job)
    loc = norm_text(job.location or "")
    hint = norm_text(job.remote_hint or "")
    if mode == "Remoto":
        if "hybrid" in loc or "hibrid" in loc or "hybrid" in hint:
            return False
        # Europe, EMEA, Global and Worldwide alone do NOT establish ability
        # to reside and be paid from the Canary Islands.
        return bool(re.search(r"\b(spain|espana|canary islands|canarias)\b", loc + " " + hint))

    if "barcelona" in loc:
        return False
    return detect_country(job.location) in {
        "Spain", "Estonia", "Lithuania", "Luxembourg", "Switzerland",
    }


def official_active_listing(job: Job) -> bool:
    """Only current employer ATS lists count as open; aggregator hits are leads.

    Inclusion in an active ATS feed + a job-specific URL is the minimum
    evidence. It is NOT a guarantee the Apply form has been tested end to end.
    """
    if job.source_kind != "official ATS":
        return False
    url = urlsplit(job.apply_url or "")
    if url.scheme != "https" or not url.netloc:
        return False
    path = (url.path or "").rstrip("/")
    if not path or path in {"/careers", "/jobs", "/join-us"}:
        return False
    return True


def passes_strict_gate(job: Job, max_hours: int = 96, now: datetime | None = None) -> bool:
    return (
        official_active_listing(job)
        and within_new_window(job.posted_at, max_hours=max_hours, now=now)
        and location_allowed(job)
    )


def previously_presented(job: Job, seen: dict) -> bool:
    """Avoid re-alerting same role after job URL, title suffix, or location shifts.

    Explicit *different* ATS IDs permit separate requisitions. Legacy seen
    entries often have no ID; with insufficient evidence prefer no repeat.
    """
    company = norm_text(job.company)
    title = norm_text(job.title)
    jid = str(job.external_id or "").strip()
    for rec in seen.values():
        if not isinstance(rec, dict):
            continue
        if norm_text(rec.get("company")) != company:
            continue
        prior_id = str(rec.get("external_id") or "").strip()
        if jid and prior_id and jid == prior_id:
            return True
        if norm_text(rec.get("title")) == title:
            if jid and prior_id and jid != prior_id:
                continue
            return True
    return False
