"""Conservative enrichment of missing company websites.

Wikidata entities are leads, not authoritative corporate ownership records.
Only an exact normalized entity label + compatible country + an official
website property may become a candidate. A separate company homepage check
is required before adding a site to hourly source coverage.
"""
from __future__ import annotations

import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit

COUNTRY_ITEM = {
    "AT": "Q40", "BE": "Q31", "BG": "Q219", "HR": "Q224",
    "CY": "Q229", "CZ": "Q213", "DK": "Q35", "EE": "Q191",
    "FI": "Q33", "FR": "Q142", "DE": "Q183", "GR": "Q41",
    "HU": "Q28", "IS": "Q189", "IE": "Q27", "IT": "Q38",
    "LV": "Q21197", "LI": "Q347", "LT": "Q37", "LU": "Q32",
    "MT": "Q233", "NL": "Q55", "NO": "Q20", "PL": "Q36",
    "PT": "Q45", "RO": "Q218", "SK": "Q214", "SI": "Q215",
    "ES": "Q29", "SE": "Q34", "GB": "Q145",
}
LEGAL_SUFFIXES = {
    "ltd", "limited", "plc", "gmbh", "ag", "sa", "sas", "sarl",
    "bv", "nv", "uab", "sro", "srl", "oy", "aps", "as", "ab",
    "spa", "inc", "llc", "se", "pvt", "corp", "corporation",
    "company", "co", "sociedad", "anonima", "societe", "anonyme",
    "bankas", "bank", "holding", "holdings",
}


def normalized_business_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value).casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    tokens = re.findall(r"[a-z0-9]+", value)
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def registry_key(name: str, country: str) -> str:
    return normalized_business_name(name) + "|" + str(country).upper().strip()


def acceptable_official_url(raw: str) -> str:
    """Block private hosts/IPs, credentials, non-HTTPS schemes and tracking."""
    try:
        p = urlsplit(str(raw))
        host = (p.hostname or "").lower().strip(".")
        if p.scheme.lower() != "https" or not host or p.username or p.password:
            return ""
        if host.startswith(("localhost", "127.")) or host.endswith(
            (".local", ".internal", ".test", ".example", ".localhost")
        ) or "." not in host:
            return ""
        try:
            ipaddress.ip_address(host)
            return ""
        except ValueError:
            pass
        if not re.fullmatch(r"[a-z0-9.-]+", host) or ".." in host:
            return ""
        return p._replace(query="", fragment="").geturl()
    except (TypeError, ValueError):
        return ""


def entity_candidates(search_result: dict, entity_payload: dict,
                      name: str, country: str) -> list[dict]:
    """Match exact-name company entities with national location + P856."""
    country_qid = COUNTRY_ITEM.get(str(country).upper().strip())
    if not country_qid:
        return []
    want = normalized_business_name(name)
    if len(want) < 4:
        return []
    entities = entity_payload.get("entities", {})
    seen = set()
    out = []
    for hit in search_result.get("search", []):
        qid = hit.get("id")
        entity = entities.get(qid, {})
        if not entity or "missing" in entity:
            continue
        labels = list((entity.get("labels") or {}).values())
        aliases = sum(((v or []) for v in (entity.get("aliases") or {}).values()), [])
        names = [v.get("value", "") for v in labels + aliases if isinstance(v, dict)]
        if not any(normalized_business_name(label) == want for label in names):
            continue
        claims = entity.get("claims", {})
        countries = set()
        for prop in ("P17", "P495"):
            for claim in claims.get(prop, []):
                val = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                if isinstance(val, dict) and val.get("id"):
                    countries.add(val["id"])
        if country_qid not in countries:
            continue
        for claim in claims.get("P856", []):
            site = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
            site = acceptable_official_url(site)
            if not site or site in seen:
                continue
            seen.add(site)
            out.append({
                "name": name, "country": country.upper().strip(),
                "website": site, "wikidata_id": qid,
                "evidence": "Wikidata P856 + matching name + country P17/P495",
                "evidence_url": "https://www.wikidata.org/wiki/" + qid,
            })
    return out


def homepage_identity_matches(html: str, company_name: str) -> bool:
    """Require company brand in title, branded metadata or site header."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html[:140_000], "html.parser")
    brand = normalized_business_name(company_name)
    if len(brand) < 4:
        return False
    evidence = []
    if soup.title:
        evidence.append(soup.title.get_text(" ", strip=True))
    for m in soup.select('meta[property="og:site_name"],meta[name="application-name"]'):
        evidence.append(str(m.get("content") or ""))
    for h in soup.select("header img[alt], header [aria-label]")[:8]:
        evidence.append(str(h.get("alt") or h.get("aria-label") or ""))
    return any(brand in normalized_business_name(value) for value in evidence)


def overlay_directory(rows: list[dict], verified: list[dict]) -> list[dict]:
    """Apply proven websites only to matching currently undated register rows.

    The licensed data is never overwritten; disabled/withdrawn registry records
    are not re-enabled from an enrichment record.
    """
    by_key = {registry_key(x.get("name", ""), x.get("country", "")): x
              for x in verified if x.get("verified") is True
              and acceptable_official_url(x.get("website", ""))}
    merged = []
    for row in rows:
        updated = dict(row)
        key = registry_key(row.get("name", ""), row.get("country", ""))
        found = by_key.get(key)
        if not updated.get("website") and found:
            updated["website"] = acceptable_official_url(found["website"])
            updated["enabled"] = bool(updated["website"])
            updated["website_provenance"] = found.get("evidence", "")
            updated["website_verified_at"] = found.get("verified_at", "")
        merged.append(updated)
    return merged
