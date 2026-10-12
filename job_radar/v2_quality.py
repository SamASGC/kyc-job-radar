"""Conservative, evidence-first admission rules for v2.

Unknown != fresh; a date from an aggregator or updated_at is not the
original publication date. These rules run in addition to the existing
role/fit scoring, never in place of it.
"""
from __future__ import annotations

import re
import json
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


def extract_original_jobposting_date(soup, expected_title: str) -> str:
    """Only schema.org JobPosting.datePosted for THIS exact role is trusted."""
    title_expected = norm_text(expected_title)
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            document = json.loads(script.string or script.get_text() or "")
        except (ValueError, TypeError):
            continue
        queue = [document]
        while queue:
            item = queue.pop()
            if isinstance(item, list):
                queue.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            types = item.get("@type", [])
            types = types if isinstance(types, list) else [types]
            if "JobPosting" in types:
                actual_title = norm_text(str(item.get("title") or ""))
                if actual_title and actual_title == title_expected:
                    date = item.get("datePosted") or ""
                    if original_posted_at(date) is not None:
                        return str(date)
            queue.extend(v for k, v in item.items() if k in {"@graph", "mainEntity", "itemListElement"})
    return ""


async def verify_application_page(http, job: Job, max_hours: int = 96) -> bool:
    """Second check of a fresh ATS posting, against its specific apply page.

    Non-200, blocked, removed, or pages without an identifiable application
    action are withheld. No CAPTCHA bypass, cookies or applicant login.
    """
    if not official_active_listing(job):
        return False
    try:
        response = await http.get(job.apply_url)
        if not 200 <= response.status_code < 300:
            return False
        page = response.text[:350_000]
    except Exception:
        return False
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page, "html.parser")
    # Use embedded original JobPosting.datePosted only if ATS did not expose
    # an original publication date. Never use updated/first-seen timestamps.
    if original_posted_at(job.posted_at) is None:
        exact_date = extract_original_jobposting_date(soup, job.title)
        if exact_date:
            job.posted_at = exact_date
    if not within_new_window(job.posted_at, max_hours=max_hours):
        return False
    text = soup.get_text(" ", strip=True).casefold()
    closed = (
        "no longer accepting applications", "applications are closed",
        "this job is no longer available", "this position has been filled",
        "this posting has expired", "job is closed",
    )
    if any(phrase in text for phrase in closed):
        return False
    # Form or explicit job application call-to-action on employer/ATS page.
    apply_cta = ("apply for this job", "apply for this position", "apply now",
                 "submit application", "apply for this role",
                 "apply to this job", "start your application")
    has_form = soup.find("form") is not None
    has_cta = any(p in text for p in apply_cta)
    if not has_cta:
        for a in soup.find_all(["a", "button"]):
            label = a.get_text(" ", strip=True).casefold()
            if label in {"apply", "apply now", "apply here", "apply for this job"}:
                has_cta = True
                break
    return bool(has_form or has_cta)
