"""Job-specific ATS API evidence when a published application is JS-rendered.

Only use official public *read-only* endpoints. An HTTP 200 career page alone
is not enough. Never submit an application, infer a publication date, or treat
an ATS API failure as proof that a job is closed.
"""
from __future__ import annotations

import re
from urllib.parse import quote, urlsplit

from job_radar.models import Job, norm_text


def _https_host(url: str, hosts: set[str]) -> bool:
    try:
        parsed = urlsplit(url)
        return parsed.scheme == "https" and parsed.hostname in hosts
    except ValueError:
        return False


def _same_job(row: dict, job: Job, *, title_field: str = "title") -> bool:
    return (
        str(row.get("id") or "") == str(job.external_id or "")
        and bool(norm_text(job.title))
        and norm_text(str(row.get(title_field) or "")) == norm_text(job.title)
    )


def _official_board(job: Job) -> tuple[str, str] | None:
    if job.source_kind != "official ATS":
        return None
    family, sep, slug = (job.source or "").partition(":")
    if not sep or family not in {"Greenhouse", "Lever", "Ashby"}:
        return None
    # Board identifiers are taken from configured/discovered first-party ATS,
    # never guessed from the company name.
    # Real Ashby boards may include dots (e.g. flagright.com); disallow
    # separators and traversal instead of rejecting valid company slugs.
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", slug) or slug in {".", ".."}:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", str(job.external_id or "")):
        return None
    return family, slug


async def native_application_evidence(http, job: Job) -> bool:
    """Confirm exact currently published requisition and an ATS application.

    A missing CTA on server-rendered HTML can be a JavaScript false negative.
    Native evidence is accepted only for matching ID/title/board and an actual
    provider application surface. Upstream callers must independently verify
    the *original* posted date, geography and explicit closed-page text.
    """
    board = _official_board(job)
    if board is None:
        return False
    family, slug = board
    jid = quote(str(job.external_id), safe="")
    escaped_slug = quote(slug, safe="")

    if family == "Greenhouse":
        # Greenhouse publicly exposes job-specific application questions for
        # published job posts. No applicant data or POST request is involved.
        endpoint = (f"https://boards-api.greenhouse.io/v1/boards/"
                    f"{escaped_slug}/jobs/{jid}?questions=true")
        response = await http.get(endpoint)
        if not 200 <= response.status_code < 300:
            return False
        row = response.json()
        return (
            isinstance(row, dict)
            and _same_job(row, job)
            and isinstance(row.get("questions"), list)
            and _https_host(job.apply_url, {
                "job-boards.greenhouse.io", "boards.greenhouse.io",
                "boards.eu.greenhouse.io",
            })
        )

    if family == "Lever":
        host = urlsplit(job.apply_url).hostname
        hosts = {"jobs.lever.co", "jobs.eu.lever.co"}
        if host not in hosts or not _https_host(job.apply_url, hosts):
            return False
        api_host = "api.eu.lever.co" if host == "jobs.eu.lever.co" else "api.lever.co"
        endpoint = f"https://{api_host}/v0/postings/{escaped_slug}/{jid}"
        response = await http.get(endpoint)
        if not 200 <= response.status_code < 300:
            return False
        row = response.json()
        apply_url = row.get("applyUrl") if isinstance(row, dict) else ""
        return (
            isinstance(row, dict)
            and _same_job(row, job, title_field="text")
            and _https_host(apply_url or "", hosts)
            and urlsplit(apply_url).hostname == host
            and f"/{slug}/{job.external_id}/" in urlsplit(apply_url).path + "/"
        )

    # Ashby's public job-board API returns currently published postings;
    # isListed=false entries must never graduate to verified applications.
    if not _https_host(job.apply_url, {"jobs.ashbyhq.com"}):
        return False
    if not urlsplit(job.apply_url).path.startswith(f"/{slug}/"):
        return False
    endpoint = f"https://api.ashbyhq.com/posting-api/job-board/{escaped_slug}"
    response = await http.get(endpoint)
    if not 200 <= response.status_code < 300:
        return False
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        return False
    for row in payload["jobs"]:
        if not isinstance(row, dict) or not _same_job(row, job):
            continue
        apply_url = row.get("applyUrl") or ""
        if (
            row.get("isListed") is True
            and _https_host(apply_url, {"jobs.ashbyhq.com"})
            and urlsplit(apply_url).path.startswith(f"/{slug}/")
        ):
            return True
    return False
