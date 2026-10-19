"""Fail closed before publishing a broken scan or destroying lifetime seen.

GitHub Actions can report SUCCESS even if every career source failed because
fetches degrade to empty results. This guard runs after the scan and before
any git commit or Pages deployment. It never creates jobs or notifications.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from job_radar.models import norm_text
from job_radar.v2_quality import original_posted_at


def check_release(companies: list[dict], coverage: dict, state: dict,
                  previous_state: dict, *, expected_direct: int = 500,
                  min_ats: int = 193, min_with_records: int = 280,
                  max_direct_errors: int = 120) -> dict:
    errors = []
    firms = [x for x in companies if x.get("enabled", True)]
    names = [norm_text(c.get("name")) for c in firms]
    if len(firms) != expected_direct or len(set(names)) != expected_direct or not all(names):
        errors.append("Configured employers changed, empty identity or duplicates")
    configured_ats = sum(bool(c.get("ats")) for c in firms)
    if configured_ats < min_ats:
        errors.append(f"ATS source coverage regressed: {configured_ats} < {min_ats}")
    direct = [x for x in coverage.get("sources", [])
              if x.get("origin_class") == "direct"]
    direct_names = [norm_text(x.get("company")) for x in direct]
    if len(direct_names) != expected_direct or set(direct_names) != set(names):
        errors.append("Direct employer inventory does not match source configuration")
    if int(coverage.get("direct_configured", -1)) != expected_direct:
        errors.append("Direct employer count differs from invariant")
    if int(coverage.get("ats_explicit", -1)) < min_ats:
        errors.append("Reported ATS coverage unexpectedly low")
    if int(coverage.get("direct_not_checked", -1)) != 0:
        errors.append("One or more direct employers were not checked")
    if int(coverage.get("direct_with_records", 0)) < min_with_records:
        errors.append("Catastrophic source collapse: too few employers returned data")
    direct_errors = int(coverage.get("direct_errors", 0))
    if direct_errors > max_direct_errors:
        errors.append(f"Mass source outage: {direct_errors} direct employers failed")
    direct_breakdown = sum(int(coverage.get(k, 0)) for k in (
        "direct_with_records", "direct_errors", "direct_reachable_zero",
        "direct_not_checked"))
    if direct_breakdown != expected_direct:
        errors.append("Source-status counts cannot reconcile to 500 direct companies")
    # Stronger than count comparisons: forbid disappearing historical fingerprints.
    old_seen = previous_state.get("seen", {})
    new_seen = state.get("seen", {})
    if not isinstance(old_seen, dict) or not isinstance(new_seen, dict):
        errors.append("Lifetime seen ledger is invalid")
    elif not set(old_seen).issubset(new_seen):
        errors.append(f"Lifetime anti-repeat ledger lost {len(set(old_seen)-set(new_seen))} fingerprints")
    jobs = state.get("jobs", {})
    if not isinstance(jobs, dict):
        errors.append("Current verified jobs must be a dictionary")
        jobs = {}
    for fp, job in jobs.items():
        if not isinstance(job, dict):
            errors.append("Malformed active job record")
            continue
        parsed = urlsplit(str(job.get("apply_url") or ""))
        if parsed.scheme != "https" or not parsed.netloc or parsed.username:
            errors.append(f"Non-HTTPS or non-applicant link in verified dashboard: {fp}")
        if not job.get("apply_verified_at") or original_posted_at(job.get("posted_at")) is None:
            errors.append(f"Verified job missing official application/date evidence: {fp}")
        if isinstance(new_seen, dict) and fp not in new_seen:
            errors.append(f"Displayed job omitted from historical dedup ledger: {fp}")
    report = {
        "configured_direct": len(firms), "configured_ats": configured_ats,
        "direct_with_records": coverage.get("direct_with_records"),
        "direct_errors": direct_errors, "seen": len(new_seen) if isinstance(new_seen,dict) else 0,
        "active": len(jobs), "passed": not errors, "errors": errors,
    }
    if errors:
        raise ValueError("; ".join(errors))
    return report


def main():
    import yaml
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior", required=True, help="Read-only checkout baseline state")
    args = parser.parse_args()
    from job_radar.config import ROOT
    root = ROOT
    companies = json.loads((root/"config/companies.json").read_text(encoding="utf-8"))
    companies += json.loads((root/"config/extra_companies.json").read_text(encoding="utf-8"))
    coverage = json.loads((root/"public/sources.json").read_text(encoding="utf-8"))
    state = json.loads((root/"data/state.json").read_text(encoding="utf-8"))
    prior = json.loads(Path(args.prior).read_text(encoding="utf-8"))
    profile = yaml.safe_load((root/"config/profile.yaml").read_text(encoding="utf-8"))
    if profile["max_post_age_hours"] != 96 or not profile["strict_quality_gate"] or profile["minimum_score"] != 62:
        raise ValueError("Hard source/date/score policy was weakened")
    if not profile["exclude_management_roles"] or profile["remote_scope"] != "Spain":
        raise ValueError("Management or Canary remote rules changed")
    for name in ("index.html", "feed.xml", "recall.json", "status.html", "sources.json"):
        if not (root/"public"/name).is_file():
            raise ValueError("Pages artifact missing: "+name)
    result = check_release(companies, coverage, state, prior)
    print("RADAR_V327_INTEGRITY",json.dumps(result,ensure_ascii=False))
    if result["direct_errors"] > 30:
        print("::warning::High number of direct employer source failures",flush=True)


if __name__=="__main__":
    main()
