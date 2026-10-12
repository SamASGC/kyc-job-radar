#!/usr/bin/env python3
"""Sync a CC BY 4.0 public fintech licence register into *candidates*, not jobs.

Source: Fintechnologica, European fintech licence index, compiled from EBA,
ESMA and FCA registers. https://fintechnologica.com/data
Licence: Creative Commons Attribution 4.0
The register is third-party compiled, not an official regulator certification.
"""
from __future__ import annotations

import argparse
import io
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

URL = "https://fintechnologica.com/data/european-fintech-licence-register.csv"
MAX_BYTES = 15_000_000


def normalize_rows(data: str) -> tuple[list[dict], dict]:
    from scripts.import_fintech_directory import get, normalize_url, classify
    entries: dict[str, dict] = {}
    total = 0
    for row in csv.DictReader(io.StringIO(data)):
        total += 1
        company = get(row, "name", "company name", "firm name", "legal name")
        if not company:
            continue
        site = normalize_url(get(row, "website", "website url", "company website"))
        country = get(row, "country")
        sector_label = get(row, "authorised services", "sector", "register", "licence class")
        status = get(row, "status").casefold()
        if status in {"withdrawn", "revoked", "closed", "inactive", "liquidation"}:
            continue
        priority, sector = classify(sector_label)
        # All payment/e-money / CASP entities are of interest by licence even
        # if the label does not include the marketing keyword 'payments'.
        if priority == 20:
            priority = 4
        key = (company.casefold().strip(), country.casefold().strip())
        entry = {
            "name": company, "website": site, "sector": sector,
            "original_sector": sector_label, "country": country,
            "priority": priority, "enabled": bool(site),
            "directory_source": "Fintechnologica European fintech licence index",
            "source_url": "https://fintechnologica.com/data",
            "license": "CC BY 4.0",
        }
        previous = entries.get("|".join(key))
        if previous is None or (site and not previous["website"]):
            entries["|".join(key)] = entry
    result = sorted(entries.values(), key=lambda r: (r["priority"], r["name"].casefold()))
    return result, {
        "input_rows": total, "unique_firm_country": len(result),
        "with_website": sum(bool(r["website"]) for r in result),
        "without_website": sum(not bool(r["website"]) for r in result),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("data/fintech_directory.json"))
    p.add_argument("--source", default=URL)
    args = p.parse_args()
    if args.source != URL:
        p.error("Source URL is fixed to the explicitly licensed register")
    with httpx.Client(timeout=45, follow_redirects=True) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        if len(resp.content) > MAX_BYTES:
            raise ValueError("Directory exceeded safe maximum download size")
        rows, stats = normalize_rows(resp.content.decode("utf-8-sig"))
    if not rows or stats["input_rows"] < 200:
        raise ValueError("Directory unexpectedly small, refusing to overwrite existing index")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Fintechnologica CC BY 4.0: https://fintechnologica.com/data")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
