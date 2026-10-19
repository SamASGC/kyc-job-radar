"""First-party Mangopay Teamtailor public vacancy pages.

Only Mangopay's *live-probed* Teamtailor-hosted domain is enabled.
The posting's schema.org JobPosting.datePosted is the ORIGINAL date.
The often-recent article:modified_time MUST NEVER create a fresh alert.

Evidence: 2026-10-19 first-party GitHub Actions probes 39276923852 and
39277080325: seven individual Mangopay /jobs/{id}-{slug} pages, each has
JobPosting.datePosted == article:published_time, a distinct modification
timestamp on edited listings, official Mangopay hiringOrganization and
an "Apply for this job" CTA.
"""
from __future__ import annotations

import html
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from job_radar.models import Job, norm_text
from job_radar.v2_quality import original_posted_at


_PROVEN_BOARDS = {"mangopay": "career.mangopay.com"}
_PATH = re.compile(r"^/jobs/([0-9]{4,12})-[a-z0-9-]+/?$")
_ROLE_CTA = re.compile(r"\bapply for this job\b", re.I)


def _first_party_job_link(value: str, expected_host: str) -> bool:
    try:
        url = urlsplit(value)
    except ValueError:
        return False
    return bool(
        url.scheme == "https"
        and url.hostname == expected_host
        and not url.username and not url.password
        and not url.query and not url.fragment
        and _PATH.fullmatch(url.path)
    )


def _first_party_jobposting(soup: BeautifulSoup, company: dict, host: str) -> dict:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        items = data if isinstance(data, list) else [data]
        for obj in items:
            if not isinstance(obj, dict) or obj.get("@type") != "JobPosting":
                continue
            org = obj.get("hiringOrganization")
            if not isinstance(org, dict):
                continue
            if norm_text(org.get("name")) != norm_text(company["name"]):
                continue
            same_as = urlsplit(str(org.get("sameAs") or ""))
            if same_as.scheme != "https" or same_as.hostname != host:
                continue
            return obj
    return {}


def _job_location(info: dict, soup: BeautifulSoup) -> tuple[str, str]:
    locs = info.get("jobLocation") or []
    if not isinstance(locs, list):
        locs = [locs]
    parts = []
    for p in locs:
        if not isinstance(p, dict):
            continue
        addr = p.get("address")
        if not isinstance(addr, dict):
            continue
        vals = [str(addr[k]) for k in ("addressLocality", "addressRegion", "addressCountry")
                if addr.get(k)]
        if vals:
            parts.append(", ".join(vals))
    location = " / ".join(dict.fromkeys(parts))
    text = soup.get_text(" ", strip=True)
    mode = re.search(r"\b(?:Hybrid|On[- ]site|Remote)\b", text, re.I)
    remote_hint = ""
    if str(info.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        remote_hint = "Remote"
    if mode and location:
        location += " - " + mode.group(0)
    elif mode:
        location = mode.group(0)
    # Never infer Spain eligibility from the mere word 'Remote'.
    return location, remote_hint


def parse_teamtailor_job_page(raw_html: str, url: str, company: dict) -> Job | None:
    host = _PROVEN_BOARDS.get(norm_text(company.get("name") or ""))
    if not host or not _first_party_job_link(url, host):
        return None
    soup = BeautifulSoup(raw_html, "html.parser")
    info = _first_party_jobposting(soup, company, host)
    if not info or not info.get("title"):
        return None
    original = str(info.get("datePosted") or "")
    pub_tag = soup.select_one('meta[property="article:published_time"]')
    published = str(pub_tag.get("content") or "") if pub_tag else ""
    # Neither a modified date nor the crawler's first-seen time is an
    # original publication timestamp. Require two consistent first-party
    # representations before using the posting in the alert pipeline.
    parsed_original = original_posted_at(original)
    parsed_published = original_posted_at(published)
    if parsed_original is None or parsed_published is None or parsed_original != parsed_published:
        original = ""
    description = BeautifulSoup(html.unescape(str(info.get("description") or "")),
                                "html.parser").get_text(" ; ", strip=True)
    location, remote_hint = _job_location(info, soup)
    match = _PATH.fullmatch(urlsplit(url).path)
    return Job(
        source=f"Teamtailor:{host}", source_kind="official ATS",
        company=company["name"], sector=company.get("sector", "Payments"),
        title=str(info["title"]).strip(), location=location,
        description=description, apply_url=url,
        external_id=match.group(1) if match else "",
        posted_at=original, remote_hint=remote_hint,
        employment_type=str(info.get("employmentType") or ""),
    ).finalize()


async def fetch_teamtailor(http, company: dict, board_url: str) -> list[Job]:
    host = _PROVEN_BOARDS.get(norm_text(company.get("name") or ""))
    if not host or board_url != f"https://{host}/jobs":
        raise ValueError("Unverified Teamtailor owner or careers board")
    response = await http.get(board_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    urls: list[str] = []
    for a in soup.select("a[href]"):
        uri = urljoin(board_url, str(a.get("href") or ""))
        if _first_party_job_link(uri, host) and uri not in urls:
            urls.append(uri)
    # A reachable *empty* board is not a failure and does not generate alerts.
    # Avoid crawling application paths outside the explicitly verified board.
    urls = urls[:100]
    if not urls:
        return []
    import asyncio
    sem = asyncio.Semaphore(5)
    async def one(uri: str):
        async with sem:
            try:
                r = await http.get(uri)
                if not 200 <= r.status_code < 300:
                    return None
                return parse_teamtailor_job_page(r.text, uri, company)
            except Exception:
                return None
    found = await asyncio.gather(*(one(u) for u in urls))
    valid = [j for j in found if j is not None]
    if not valid:
        # A first-party board with *visible job links* but not even one
        # verifiable detail is NOT a legitimately empty employer feed.
        # Report it as unavailable so the source dashboard can expose it.
        # Zero listing links above remains a genuine reachable-empty case.
        raise RuntimeError(
            f"Teamtailor detail extraction failed for all {len(urls)} visible "
            "job links; refusing silent empty-source success"
        )
    return valid
