#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from job_radar.config import ROOT
import job_radar.scanner as scanner_module
import job_radar.matching as matching_module
from job_radar.fit_adjustments import apply_fit_adjustments
from job_radar.sources.oracle_hcm import fetch_oracle_hcm
from job_radar.sources.open_universe import (
    fetch_jobopportunities_open_universe,
    fetch_remote_landers,
)
from job_radar.state import load_state
from job_radar.dashboard import build_dashboard


_BASE_LOAD_JSON = scanner_module.load_json
_BASE_LOCATION_RULE = matching_module.location_score_and_allowed
_BASE_SCORE_JOB = scanner_module.score_job
_BASE_FETCH_TARGET = scanner_module.fetch_target
_BASE_FETCH_AGGREGATORS = scanner_module.fetch_aggregators


def _load_json_with_expansions(path):
    data = _BASE_LOAD_JSON(path)
    if str(path) == "config/companies.json":
        try:
            extra = _BASE_LOAD_JSON("config/extra_companies.json")
        except FileNotFoundError:
            extra = []
        if extra:
            existing = {str(x.get("name", "")).casefold() for x in data}
            data = list(data) + [x for x in extra if str(x.get("name", "")).casefold() not in existing]
    return data


# ATS/API feeds often publish ISO country codes rather than full country names. Add the
# codes we care about so the geography gate does not mistake "DE - Remote" for unknown.
matching_module.COUNTRY_ALIASES.update({
    "es": "Spain", "lu": "Luxembourg", "ch": "Switzerland", "ee": "Estonia", "cz": "Czechia", "mt": "Malta",
    "al": "Albania", "at": "Austria", "be": "Belgium", "ba": "Bosnia and Herzegovina", "bg": "Bulgaria",
    "hr": "Croatia", "cy": "Cyprus", "dk": "Denmark", "fi": "Finland", "fr": "France", "de": "Germany",
    "gr": "Greece", "hu": "Hungary", "is": "Iceland", "ie": "Ireland", "it": "Italy", "lv": "Latvia",
    "li": "Liechtenstein", "lt": "Lithuania", "me": "Montenegro", "nl": "Netherlands", "mk": "North Macedonia",
    "no": "Norway", "pl": "Poland", "pt": "Portugal", "ro": "Romania", "rs": "Serbia", "sk": "Slovakia",
    "si": "Slovenia", "se": "Sweden", "gb": "United Kingdom",
    # Common non-European codes: explicit detection means they are hard-rejected for Europe-only remote.
    "us": "United States", "mx": "Mexico", "ca": "Canada", "br": "Brazil", "ar": "Argentina",
    "in": "India", "sg": "Singapore", "au": "Australia", "ae": "United Arab Emirates", "za": "South Africa",
})


def _location_rule_with_scope(job, preliminary_score, skills, profile):
    mode = matching_module.detect_mode(job)
    scope = str(profile.get("remote_scope", "Europe")).casefold()

    if mode == "Remoto" and scope == "europe":
        country = matching_module.detect_country(job.location)
        low = matching_module.norm_text(job.location + " " + job.remote_hint)

        # Explicit country wins over vague labels such as "global". This prevents a row
        # like "Mexico - Remote / global team" from leaking into a Europe-only dashboard.
        if country:
            if country in matching_module.EUROPE_COUNTRIES:
                return 15, True, f"remoto en {country}"
            return -25, False, f"remoto fuera de Europa: {country}"

        if any(matching_module.norm_text(x) in low for x in matching_module.BLOCKED_REMOTE_TERMS):
            return -25, False, "remoto restringido fuera de Europa"

        # Europe/EMEA and genuinely global/worldwide roles are usable from Europe.
        if any(matching_module.norm_text(x) in low for x in matching_module.EUROPE_TERMS):
            return 15, True, "remoto disponible desde Europa"

        # Strict mode: a bare "Remote" with no eligibility geography is not enough.
        return -12, False, "remoto sin elegibilidad europea verificable"

    # Retain the old global behavior only if the profile is explicitly changed back to Global.
    if mode == "Remoto" and scope == "global":
        country = matching_module.detect_country(job.location)
        if country:
            return 15, True, f"remoto en {country}"
        low = matching_module.norm_text(job.location + " " + job.remote_hint)
        if any(matching_module.norm_text(x) in low for x in matching_module.EUROPE_TERMS):
            return 15, True, "remoto global/EMEA/Europa"
        allowed = preliminary_score >= 68
        return (10 if allowed else -3), allowed, "remoto global; país no indicado"

    return _BASE_LOCATION_RULE(job, preliminary_score, skills, profile)


def _score_job_with_must_have_gaps(job, profile, known_company=False):
    scored, ok = _BASE_SCORE_JOB(job, profile, known_company=known_company)
    return apply_fit_adjustments(scored, profile, ok)


async def _fetch_target_with_oracle(http, company, target):
    if target.get("kind") == "oracle_hcm":
        return await fetch_oracle_hcm(http, company, target)
    return await _BASE_FETCH_TARGET(http, company, target)


async def _fetch_aggregators_with_open_universe(http, config):
    """Keep the original feeds and add broad employer-direct discovery surfaces."""
    jobs, health, skipped = await _BASE_FETCH_AGGREGATORS(http, config)

    specs = [
        ("Job Opportunities API", fetch_jobopportunities_open_universe),
        ("Remote Landers", fetch_remote_landers),
    ]
    results = await asyncio.gather(*(func(http) for _, func in specs), return_exceptions=True)
    for (name, _), result in zip(specs, results):
        if isinstance(result, Exception):
            health.append({
                "company": name,
                "ok": False,
                "jobs": 0,
                "targets": [{"kind": "open-universe aggregator"}],
                "error": f"{type(result).__name__}: {result}",
            })
            skipped.add(name)
        else:
            jobs.extend(result)
            health.append({
                "company": name,
                "ok": True,
                "jobs": len(result),
                "targets": [{"kind": "open-universe aggregator"}],
                "error": "",
            })
    return jobs, health, skipped


# Expand role discovery beyond conventional KYC/AML titles. These terms do NOT claim
# experience; they only make relevant jobs discoverable and scorable.
matching_module.ROLE_TERMS.update({
    "source of funds": 22,
    "source of wealth": 22,
    "beneficial ownership": 22,
    "pep": 18,
    "adverse media": 18,
    "financial integrity": 20,
    "client review": 18,
    "customer risk assessment": 20,
})

_existing_growth_labels = {str(label).casefold() for label, _ in matching_module.GROWTH_SKILLS}
if "source of funds (sof)" not in _existing_growth_labels:
    matching_module.GROWTH_SKILLS.append((
        "Source of Funds (SoF)",
        ["source of funds", "source-of-funds", "sof review", "sof assessment"],
    ))
if "source of wealth (sow)" not in _existing_growth_labels:
    matching_module.GROWTH_SKILLS.append((
        "Source of Wealth (SoW)",
        ["source of wealth", "source-of-wealth", "sow review", "sow assessment"],
    ))

# Keep expansion targets separate from the large original company file while making
# every normal scan (local and GitHub Actions) consume both lists transparently.
scanner_module.load_json = _load_json_with_expansions
matching_module.location_score_and_allowed = _location_rule_with_scope
scanner_module.score_job = _score_job_with_must_have_gaps
scanner_module.fetch_target = _fetch_target_with_oracle
scanner_module.fetch_aggregators = _fetch_aggregators_with_open_universe


def cmd_scan(args):
    stats = asyncio.run(scanner_module.run_scan())
    print(json.dumps(stats, indent=2, ensure_ascii=False))


def cmd_build(args):
    state = load_state()
    jobs = list(state.get("jobs", {}).values())
    jobs.sort(key=lambda x: (-int(x.get("score", 0)), x.get("company", ""), x.get("title", "")))
    build_dashboard(jobs, state.get("stats", {}), "public/index.html", state.get("dataset_updated_at", ""))
    print(f"Built: {ROOT / 'public/index.html'}")


def cmd_health(args):
    p = ROOT / "data/health.json"
    if not p.exists():
        print("No health report yet. Run: python radar.py scan")
        return
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("sources", [])
    failed = [x for x in rows if not x.get("ok")]
    print(f"Sources: {len(rows)} | OK: {len(rows)-len(failed)} | Failed: {len(failed)}")
    for x in failed:
        print(f"- {x.get('company')}: {x.get('error')}")


def main():
    ap = argparse.ArgumentParser(description="KYC/KYB/AML hourly job radar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="Fetch sources, score, dedupe, update state and dashboard").set_defaults(func=cmd_scan)
    sub.add_parser("build", help="Rebuild HTML from existing state without network").set_defaults(func=cmd_build)
    sub.add_parser("health", help="Show source failures from last scan").set_defaults(func=cmd_health)
    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
