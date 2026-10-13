"""Read Prospective's public employer-specific Swiss bank vacancy listing API.

Raiffeisen and BEKB's own career frontends reference the Prospective public
medium IDs below. Only the provider's original start_date is used for posting
age, never last_modification_timestamp, scan time or search-engine index date.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from job_radar.models import Job

MEDIUMS = {"Raiffeisen Switzerland": 1950, "Berner Kantonalbank": 1509}
APPLY_HOSTS = {
    1950: frozenset({
        "raiffeisen.wd3.myworkdayjobs.com",
        "www.raiffeisen.ch",
        "jobs.raiffeisen.ch",
        "raiffeisen.ch",
    }),
    1509: frozenset({"bekb.abacuscity.ch", "bekb.ch", "www.bekb.ch"}),
}


def _text(x) -> str:
    return BeautifulSoup(str(x or ""), "html.parser").get_text(" ", strip=True)


def _parse(job: dict, company: dict, medium_id: int, now: datetime) -> Job | None:
    ident = str(job.get("id") or "").strip()
    title = _text(job.get("title"))
    source = job.get("szas") or {}
    url = str(source.get("sza_apply_link") or "").strip()
    parsed = urlsplit(url)
    if not ident.isdigit() or not title or parsed.scheme != "https":
        return None
    if (parsed.hostname or "").casefold() not in APPLY_HOSTS[medium_id]:
        return None
    # An explicitly expired listing is not an open vacancy even if cached in
    # the provider's first-party listing API.
    end = str(job.get("end_date") or "")
    if end:
        try:
            when = datetime.fromisoformat(end.replace("Z", "+00:00"))
            if when.tzinfo is None:
                return None
            if when <= now:
                return None
        except (ValueError, OverflowError):
            return None
    country = _text(source.get("sza_location.country"))
    country = "Switzerland" if country.casefold() in {"schweiz", "suisse", "svizzera"} else country
    city = _text(source.get("sza_location.city") or source.get("sza_workplace.city"))
    location = ", ".join(x for x in (city, country) if x)
    # Read only first-party employer job descriptions / language requirements,
    # never external advertising, cookies, JS or snippets.
    fields = ("sza_introduction", "sza_tasks", "sza_requirements",
              "sza_language_requirements", "sza_role", "sza_additional_text")
    description = " ".join(_text(source.get(k)) for k in fields if source.get(k))
    # Explicit source start_date is the employer's scheduled initial publish
    # date. last_modification_timestamp is *not* a first-posting timestamp.
    published = str(job.get("start_date") or "")
    return Job(
        source=f"Prospective:{medium_id}", source_kind="official ATS",
        company=company["name"], sector=company.get("sector", "Banca"),
        title=title, location=location, description=description,
        apply_url=url, external_id=f"{medium_id}:{ident}",
        posted_at=published, employment_type=_text(source.get("sza_employment_type")),
    ).finalize()


async def fetch_prospective(http, company: dict, medium_id: int) -> list[Job]:
    # Both portal IDs must be bound to the original bank's public frontend.
    if MEDIUMS.get(company.get("name")) != medium_id:
        raise ValueError("Prospective medium ID does not belong to this employer")
    endpoint = f"https://ohws.prospective.ch/public/v1/medium/{medium_id}/jobs"
    offset, page_size = 0, 50
    seen = set()
    out = []
    now = datetime.now(timezone.utc)
    while offset < 500:
        r = await http.get(f"{endpoint}?lang=de&offset={offset}&limit={page_size}")
        r.raise_for_status()
        payload = r.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Prospective returned an invalid jobs response")
        if str(payload.get("medium_id")) != str(medium_id):
            raise ValueError("Prospective returned postings from a different employer medium")
        jobs = payload["jobs"]
        for item in jobs:
            if not isinstance(item, dict):
                continue
            posting = _parse(item, company, medium_id, now)
            if posting and posting.external_id not in seen:
                seen.add(posting.external_id)
                out.append(posting)
        total = payload.get("total")
        if len(jobs) < page_size:
            break
        offset += page_size
        if isinstance(total, int) and offset >= total:
            break
    return out
