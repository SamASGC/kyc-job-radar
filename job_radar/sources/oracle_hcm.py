from __future__ import annotations

import asyncio
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from job_radar.models import Job


STRONG_TITLE = re.compile(
    r"\b(kyc|kyb|aml|fincrime|financial crime|compliance|sanction|fraud|risk|onboarding|due diligence|cdd|edd|screening|investigat|transaction monitoring)\b",
    re.I,
)


def _plain(value) -> str:
    if value is None:
        return ""
    return BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)


def _walk_requisition_items(node) -> list[dict]:
    """Find Oracle Candidate Experience requisition-list rows inside nested payloads."""
    out: list[dict] = []
    if isinstance(node, dict):
        if node.get("Id") and node.get("Title") and any(
            k in node for k in ("PrimaryLocation", "PostedDate", "ExternalResponsibilitiesStr", "ShortDescriptionStr")
        ):
            out.append(node)
        for value in node.values():
            out.extend(_walk_requisition_items(value))
    elif isinstance(node, list):
        for value in node:
            out.extend(_walk_requisition_items(value))
    return out


def _detail_object(data) -> dict:
    if isinstance(data, dict):
        if data.get("Id") or data.get("RequisitionId") or data.get("Title"):
            return data
        items = data.get("items")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            return items[0]
    return {}


def _description(data: dict) -> str:
    parts = [
        data.get("ShortDescriptionStr"),
        data.get("ExternalDescriptionStr"),
        data.get("ExternalResponsibilitiesStr"),
        data.get("ExternalQualificationsStr"),
        data.get("CorporateDescriptionStr"),
    ]
    clean = []
    seen = set()
    for part in parts:
        text = _plain(part)
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            clean.append(text)
    return " ".join(clean)


def _location(data: dict) -> tuple[str, str]:
    loc = str(data.get("PrimaryLocation") or "").strip()
    workplace = str(data.get("WorkplaceType") or "").strip()
    remote_hint = "Remote" if "remote" in workplace.casefold() else ""
    if workplace and workplace.casefold() not in loc.casefold():
        loc = f"{loc} - {workplace}" if loc else workplace
    return loc, remote_hint


def _job_from_row(company: dict, origin: str, language: str, site: str, row: dict) -> Job:
    rid = str(row.get("Id") or row.get("RequisitionId") or "").strip()
    loc, remote = _location(row)
    apply = f"{origin}/hcmUI/CandidateExperience/{language}/sites/{site}/job/{rid}" if rid else company["careers_url"]
    return Job(
        source=f"OracleHCM:{site}",
        source_kind="official ATS",
        company=company["name"],
        sector=company.get("sector", "Fintech"),
        title=str(row.get("Title") or "").strip(),
        location=loc,
        description=_description(row),
        apply_url=apply,
        external_id=rid,
        posted_at=str(row.get("PostedDate") or row.get("PostingStartDate") or ""),
        remote_hint=remote,
        employment_type=str(row.get("JobType") or row.get("WorkerType") or row.get("ContractType") or ""),
    ).finalize()


async def fetch_oracle_hcm(http, company: dict, target: dict) -> list[Job]:
    """Fetch Oracle Fusion HCM Candidate Experience postings used by career sites such as Amex.

    Oracle documents the recruitingCEJobRequisitions collection and the requisitionList
    child used by Candidate Experience sites. We use the public career-site endpoint at a
    low cadence and enrich only compliance/risk-like titles with the details endpoint.
    """
    configured = target.get("url") or company.get("careers_url") or ""
    p = urlsplit(configured)
    if not p.scheme or not p.netloc:
        return []
    origin = f"{p.scheme}://{p.netloc}"
    site = str(target.get("site") or "CX_1")
    language = str(target.get("language") or "en")
    api_version = str(target.get("api_version") or "11.13.18.05")
    list_endpoint = f"{origin}/hcmRestApi/resources/{api_version}/recruitingCEJobRequisitions"

    rows_by_id: dict[str, dict] = {}
    page_size = 100
    for offset in range(0, 500, page_size):
        finder = f"findReqs;siteNumber={site},limit={page_size},offset={offset}"
        r = await http.get(
            list_endpoint,
            params={"finder": finder, "expand": "requisitionList", "onlyData": "true"},
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        batch = _walk_requisition_items(data)
        before = len(rows_by_id)
        for row in batch:
            rid = str(row.get("Id") or row.get("RequisitionId") or "").strip()
            if rid:
                rows_by_id[rid] = row
        # Stop when this page added fewer than a full page, or nothing new.
        added = len(rows_by_id) - before
        if added == 0 or len(batch) < page_size:
            break

    jobs_by_id = {
        rid: _job_from_row(company, origin, language, site, row)
        for rid, row in rows_by_id.items()
    }

    # Enrich only titles likely to survive the KYC/AML matcher. This avoids fetching
    # hundreds of unrelated Amex details pages while preserving full JD text for scoring.
    relevant_ids = [
        rid for rid, job in jobs_by_id.items()
        if STRONG_TITLE.search(job.title)
    ][:40]

    async def enrich(rid: str):
        endpoint = f"{origin}/hcmRestApi/resources/{api_version}/recruitingCEJobRequisitionDetails/{rid}"
        try:
            rr = await http.get(
                endpoint,
                params={"expand": "all", "onlyData": "true"},
                headers={"Accept": "application/json"},
            )
            rr.raise_for_status()
            detail = _detail_object(rr.json())
            if not detail:
                return rid, None
            merged = dict(rows_by_id.get(rid, {}))
            merged.update(detail)
            return rid, _job_from_row(company, origin, language, site, merged)
        except Exception:
            return rid, None

    if relevant_ids:
        results = await asyncio.gather(*(enrich(rid) for rid in relevant_ids))
        for rid, job in results:
            if isinstance(job, Job):
                jobs_by_id[rid] = job

    return list(jobs_by_id.values())
