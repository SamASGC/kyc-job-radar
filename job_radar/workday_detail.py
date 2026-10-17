"""Read-only, exact first-party Workday CXS requisition detail verification.

Workday's list uses "Posted Yesterday" and sometimes omits postedOn.
Only the exact company's public CXS /job/ detail can establish absolute
startDate, full JD and active application (posted AND canApply).
Live probed 2026-10-17: PayPal, Entrust, Northern Trust, Worldpay;
workflow run 39065230044. Never turn relative listing labels into dates.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit
from job_radar.models import Job, norm_text
from job_radar.v2_quality import original_posted_at


_SITE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_PATH = re.compile(r"^/job/(?:[A-Za-z0-9_.%()-]+/){1,6}[A-Za-z0-9_.%()-]+$")
_LOCALE = re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$")


def workday_board(careers_url: str) -> tuple[str, str, str, str] | None:
    """Return exact Workday host, tenant, site and public prefix."""
    p = urlsplit(careers_url or "")
    host = (p.hostname or "").lower()
    if p.scheme != "https" or not host.endswith(".myworkdayjobs.com") or p.username or p.password:
        return None
    parts = [part for part in p.path.split("/") if part]
    if not parts:
        return None
    tenant = host.split(".")[0]
    site = parts[1] if len(parts) >= 2 and _LOCALE.fullmatch(parts[0]) else parts[0]
    if not _SITE.fullmatch(tenant) or not _SITE.fullmatch(site):
        return None
    prefix = p.path.rstrip("/")
    if prefix not in (f"/{site}", *(f"/{locale}/{site}" for locale in ("en-US", "en-GB", "de-DE", "fr-FR", "es-ES"))):
        return None
    return host, tenant, site, prefix


def workday_detail_endpoint(job: Job) -> str | None:
    if job.source_kind != "official ATS" or not job.source.startswith("Workday:"):
        return None
    board = job.source.removeprefix("Workday:")
    if "/" not in board:
        return None
    tenant_source, site_source = board.split("/", 1)
    if not _SITE.fullmatch(tenant_source) or not _SITE.fullmatch(site_source):
        return None
    public = urlsplit(job.apply_url or "")
    ext = str(job.external_id or "")
    if not _PATH.fullmatch(ext) or public.query or public.fragment:
        return None
    if not public.path.endswith(ext):
        return None
    prefix = public.path[:-len(ext)]
    parsed = workday_board(f"https://{public.netloc}{prefix}")
    if parsed is None:
        return None
    host, tenant, site, _ = parsed
    if tenant != tenant_source or site != site_source:
        return None
    return f"https://{host}/wday/cxs/{tenant}/{site}{ext}"


def workday_exact_job(info: dict, job: Job) -> bool:
    """Verify exact posting identity, never merely an employer or board."""
    if not isinstance(info, dict) or not workday_detail_endpoint(job):
        return False
    actual_title = norm_text(str(info.get("title") or ""))
    expected_posting_id = str(job.external_id).rsplit("/", 1)[-1]
    return bool(
        actual_title and actual_title == norm_text(job.title)
        and str(info.get("jobPostingId") or "") == expected_posting_id
        and str(info.get("id") or "").strip()
    )


def workday_original_date(info: dict, job: Job) -> str:
    """The original startDate is usable only for the exact public requisition."""
    if not workday_exact_job(info, job):
        return ""
    start = str(info.get("startDate") or "")
    return start if original_posted_at(start) is not None else ""


async def fetch_workday_detail(http, job: Job) -> dict:
    url = workday_detail_endpoint(job)
    if not url:
        return {}
    response = await http.get(url)
    if not 200 <= response.status_code < 300:
        return {}
    payload = response.json()
    info = payload.get("jobPostingInfo") if isinstance(payload, dict) else None
    return info if isinstance(info, dict) and workday_exact_job(info, job) else {}


async def native_workday_application_evidence(http, job: Job) -> bool:
    info = await fetch_workday_detail(http, job)
    if not info or info.get("posted") is not True or info.get("canApply") is not True:
        return False
    start = workday_original_date(info, job)
    from job_radar.v2_quality import original_posted_at
    original = original_posted_at(job.posted_at)
    return bool(start and original is not None and
                original.date() == original_posted_at(start).date())
