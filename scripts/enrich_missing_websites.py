#!/usr/bin/env python3
"""Add official employer websites from public Wikidata entity evidence.

Processes a bounded batch of missing-URL licensed firms. Source matching is
conservative and reversible; no recruiting job is created from Wikidata alone.
State and overrides are saved independently of the CC BY 4.0 licensed register.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from job_radar.website_enrichment import (
    COUNTRY_ITEM, acceptable_official_url, entity_candidates,
    homepage_identity_matches, registry_key,
)

API = "https://www.wikidata.org/w/api.php"
USER_AGENT = "AML-Radar-v2.2/1.0 (public employer research; https://github.com/SamASGC/kyc-job-radar)"
RETRY_DAYS = 30


def candidates_to_research(directory: list[dict], attempted: dict,
                           limit: int, now: datetime) -> list[dict]:
    candidates = []
    unique = set()
    for row in directory:
        name, country = str(row.get("name", "")), str(row.get("country", "")).upper()
        key = registry_key(name, country)
        if (not name or not country or country not in COUNTRY_ITEM
                or row.get("website") or key in unique):
            continue
        unique.add(key)
        checked = attempted.get(key, {})
        try:
            previous = datetime.fromisoformat(str(checked.get("checked_at", "")).replace("Z", "+00:00"))
            if now - previous < timedelta(days=RETRY_DAYS):
                continue
        except (ValueError, TypeError):
            pass
        candidates.append(row)
    # Spread over legal regions instead of always starting with Lithuanian
    # and British firms whose names alphabetically dominate the register.
    candidates.sort(key=lambda x: (x.get("country", ""), x.get("name", "").casefold()))
    if not candidates:
        return []
    hour = int(now.timestamp() // 3600)
    start = (hour * max(1, limit)) % len(candidates)
    return [candidates[(start + i) % len(candidates)]
            for i in range(min(limit, len(candidates)))]


async def query_wikidata(client: httpx.AsyncClient, name: str) -> tuple[dict, dict]:
    params = {
        "action": "wbsearchentities", "format": "json",
        "language": "en", "search": name, "limit": 7,
        "type": "item",
    }
    r = await client.get(API, params=params)
    if r.status_code in (403, 429) or r.status_code >= 500:
        raise RuntimeError(f"Wikidata unavailable, HTTP {r.status_code}")
    r.raise_for_status()
    search = r.json()
    ids = [x.get("id") for x in search.get("search", []) if x.get("id")]
    if not ids:
        return search, {"entities": {}}
    params2 = {
        "action": "wbgetentities", "format": "json",
        "ids": "|".join(ids[:7]),
        "props": "labels|aliases|claims", "languages": "en|es|fr|de|lt",
    }
    r = await client.get(API, params=params2)
    if r.status_code in (403, 429) or r.status_code >= 500:
        raise RuntimeError(f"Wikidata entity detail unavailable, HTTP {r.status_code}")
    r.raise_for_status()
    return search, r.json()


async def verify_site(client: httpx.AsyncClient, site: str,
                      name: str) -> tuple[bool, str]:
    """No redirects to arbitrary sites; allow only same-domain www variants."""
    clean = acceptable_official_url(site)
    if not clean:
        return False, "unsafe_url"
    try:
        r = await client.get(clean, follow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308):
            redirect = str(r.headers.get("location") or "")
            from urllib.parse import urljoin
            redirect = acceptable_official_url(urljoin(clean, redirect))
            if not redirect:
                return False, "unsafe_redirect"
            a = (urlsplit(clean).hostname or "").removeprefix("www.")
            b = (urlsplit(redirect).hostname or "").removeprefix("www.")
            if a != b:
                return False, "redirects_to_different_domain"
            r = await client.get(redirect, follow_redirects=False)
        if r.status_code != 200:
            return False, "homepage_http_" + str(r.status_code)
        if "text/html" not in r.headers.get("content-type", "text/html").lower():
            return False, "homepage_not_html"
        if not homepage_identity_matches(r.text, name):
            return False, "homepage_brand_not_confirmed"
        return True, "verified_brand_site"
    except (httpx.HTTPError, UnicodeError) as exc:
        return False, "homepage_error_" + type(exc).__name__


async def enrich(directory: list[dict], attempted: dict, verified: list[dict],
                 limit: int = 20, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    sample = candidates_to_research(directory, attempted, limit, now)
    stats = {"missing_total": sum(not x.get("website") for x in directory),
             "selected": len(sample), "queried": 0, "matched_entities": 0,
             "new_verified_websites": 0, "held_for_manual_review": 0,
             "failures": 0, "status": "ok"}
    # Stable provenance; nonconfirmed matches are logged, never put in the ATS queue.
    current_sites = {registry_key(x["name"], x["country"]) for x in verified
                     if x.get("verified")}
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.8"},
        trust_env=True,
    ) as client:
        for row in sample:
            name, country = row["name"], row["country"]
            key = registry_key(name, country)
            try:
                search, entities = await query_wikidata(client, name)
                stats["queried"] += 1
                matches = entity_candidates(search, entities, name, country)
                stats["matched_entities"] += len(matches)
                if len(matches) > 1:
                    attempted[key] = {"checked_at": now.isoformat(), "status": "ambiguous_multiple_entities"}
                    stats["held_for_manual_review"] += 1
                    continue
                if not matches:
                    attempted[key] = {"checked_at": now.isoformat(), "status": "no_strict_match"}
                    continue
                match = matches[0]
                ok, reason = await verify_site(client, match["website"], name)
                attempted[key] = {"checked_at": now.isoformat(), "status": reason,
                                  "evidence_url": match["evidence_url"]}
                if not ok:
                    stats["held_for_manual_review"] += 1
                    continue
                if key not in current_sites:
                    verified.append({**match, "verified": True,
                                     "verified_at": now.isoformat(),
                                     "verification_method": "Wikidata country+name+P856 plus matching website identity"})
                    current_sites.add(key)
                    stats["new_verified_websites"] += 1
            except (RuntimeError, httpx.HTTPError) as exc:
                # Stop on API quota/network errors rather than marking other
                # candidates tried. This makes the next run retry safely.
                stats["failures"] += 1
                stats["status"] = str(exc)[:150]
                break
            await asyncio.sleep(0.8)  # Conservative request spacing
    stats["total_verified_websites"] = len(current_sites)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path("data/fintech_directory.json"))
    parser.add_argument("--state", type=Path, default=Path("data/enrichment_state.json"))
    parser.add_argument("--verified", type=Path, default=Path("data/verified_company_websites.json"))
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.limit <= 60:
        parser.error("--limit must be 1 to 60")
    directory = json.loads(args.directory.read_text(encoding="utf-8"))
    data = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else {}
    attempted = data.get("attempted", {})
    verified = json.loads(args.verified.read_text(encoding="utf-8")) if args.verified.exists() else []
    stats = asyncio.run(enrich(directory, attempted, verified, limit=args.limit))
    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.verified.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(json.dumps({"attempted": attempted},indent=2,ensure_ascii=False)+"\n",
                          encoding="utf-8")
    args.verified.write_text(json.dumps(verified,indent=2,ensure_ascii=False)+"\n",
                             encoding="utf-8")
    print(json.dumps(stats,ensure_ascii=False))
    if stats["status"] != "ok":
        raise RuntimeError(stats["status"])


if __name__ == "__main__":
    main()
