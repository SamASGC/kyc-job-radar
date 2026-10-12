#!/usr/bin/env python3
"""Import a legitimately obtained fintech directory CSV as discovery candidates.

Usage:
  python scripts/import_fintech_directory.py eu_fintech_export.csv
Requires at minimum a company/name column. Without a website, the row is
catalogued but cannot be fetched as a career source. No scraping or API key.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

RELEVANT = {"payments", "banking", "crypto and defi", "regtech",
            "embedded finance", "spend management", "wealth management",
            "financial management solutions", "lending"}


def get(row: dict, *keys: str) -> str:
    normalized = {str(k).strip().casefold(): str(v or "").strip()
                  for k, v in row.items() if k}
    for key in keys:
        if normalized.get(key.casefold()):
            return normalized[key.casefold()]
    return ""


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url and "://" not in url:
        url = "https://" + url.lstrip("/")
    parts = urlsplit(url)
    return url if parts.scheme == "https" and parts.hostname and "." in parts.hostname else ""


def classify(sector: str) -> tuple[int, str]:
    s = sector.casefold().strip()
    if "payment" in s:
        return 1, "Payments"
    if "banking" in s:
        return 2, "Banca"
    if any(word in s for word in ("crypto", "regtech", "embedded finance", "spend management")):
        return 3, "Fintech"
    if any(word in s for word in RELEVANT):
        return 5, "Fintech"
    return 20, "Fintech"


def parse_directory_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = {}
        for row in reader:
            name = get(row, "firm name", "company name", "company", "name", "firm")
            if not name:
                continue
            website = normalize_url(get(row, "website", "website url", "url", "company website"))
            category = get(row, "sector", "sectors", "category", "industry")
            country = get(row, "country", "headquarters country", "hq country")
            priority, sector = classify(category)
            key = name.casefold().strip() + "|" + country.casefold().strip()
            item = {"name": name, "website": website, "sector": sector,
                    "original_sector": category, "country": country,
                    "priority": priority, "enabled": bool(website),
                    "directory_source": path.name}
            prior = rows.get(key)
            if not prior or (website and not prior.get("website")):
                rows[key] = item
    return sorted(rows.values(), key=lambda item: (item["priority"], item["name"].casefold()))


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage European fintech firms for ATS discovery")
    ap.add_argument("csv_file", type=Path)
    ap.add_argument("--out", type=Path, default=Path("data/fintech_directory.json"))
    args = ap.parse_args()
    rows = parse_directory_csv(args.csv_file)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    usable = sum(bool(x["website"]) for x in rows)
    relevant = sum(x["priority"] <= 5 for x in rows)
    print(f"Imported {len(rows)} unique firm-country entries: {usable} with usable HTTPS websites, "
          f"{relevant} priority fintech candidates. Output: {args.out}")
    print("Directory entry != ATS integrated != vacancy source; see README before enabling scans.")


if __name__ == "__main__":
    main()
