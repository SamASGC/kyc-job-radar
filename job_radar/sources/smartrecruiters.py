from __future__ import annotations

import asyncio

from job_radar.models import Job


async def fetch_smartrecruiters(http, company: dict, slug: str) -> list[Job]:
    """Fetch public employer-scoped postings; bound pagination and detail concurrency.

    The first 100 positions are not the entire recruiting board. SmartRecruiters
    supplies totalFound plus offset; in particular IQ-EQ had 125 postings on
    2026-10-13. Preserve only provider-sourced releasedDate as publication date.
    """
    limit = 100
    cap = 500
    postings = []
    seen = set()
    offset = 0

    while offset < cap:
        url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit={limit}"
        if offset:
            url += f"&offset={offset}"
        r = await http.get(url)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise ValueError("SmartRecruiters returned non-object JSON")
        page = data.get("content") or data.get("postings") or []
        if not isinstance(page, list):
            raise ValueError("SmartRecruiters returned invalid posting list")

        added = 0
        for item in page:
            if not isinstance(item, dict):
                continue
            jid = str(item.get("id") or item.get("uuid") or "")
            if not jid or jid in seen:
                continue
            # Guard the bank/funds employer which is easily confused with IQE.
            # No cross-employer posting may be attributed to IQ-EQ.
            if company.get("name") == "IQ-EQ":
                owner = item.get("company") or {}
                if not isinstance(owner, dict) or str(owner.get("identifier") or "").casefold() != "iqeq":
                    continue
            seen.add(jid)
            postings.append(item)
            added += 1
            if len(postings) >= cap:
                break

        # Some boards ignore an offset parameter. Never loop on a repeated
        # first page or artificially count repeat postings as coverage.
        if not page or not added or len(page) < limit or len(postings) >= cap:
            break
        offset += len(page)
        total = data.get("totalFound", data.get("total"))
        if isinstance(total, int) and offset >= total:
            break

    sem = asyncio.Semaphore(8)

    async def enrich(item):
        jid = str(item.get("id") or item.get("uuid") or "")
        detail = {}
        async with sem:
            try:
                url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{jid}"
                r = await http.get(url)
                if r.status_code == 200:
                    payload = r.json()
                    if isinstance(payload, dict):
                        detail = payload
            except Exception:
                # A missing job detail cannot invent an application or date.
                pass
        locd = detail.get("location") or item.get("location") or {}
        if isinstance(locd, dict):
            loc = ", ".join(str(v) for v in
                            (locd.get("city"), locd.get("region"), locd.get("country")) if v)
        else:
            loc = str(locd)
        sections = detail.get("jobAd") or {}
        descriptions = []
        if isinstance(sections, dict):
            for v in sections.values():
                if isinstance(v, dict):
                    descriptions.append(v.get("text") or "")
        apply = detail.get("applyUrl") or item.get("applyUrl") or detail.get("jobAdUrl") or ""
        posted = detail.get("releasedDate") or item.get("releasedDate") or ""
        return Job(
            source=f"SmartRecruiters:{slug}", source_kind="official ATS",
            company=company["name"], sector=company.get("sector", "Fintech"),
            title=detail.get("name") or item.get("name") or "", location=loc,
            description="\n".join(descriptions), apply_url=apply,
            external_id=jid, posted_at=posted,
        ).finalize()

    return list(await asyncio.gather(*(enrich(item) for item in postings)))
