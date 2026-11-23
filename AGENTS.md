# Engineering agent instructions — KYC / KYB / AML Job Radar

This repository monitors **official employer recruitment sources** and publishes a strictly verified AML/KYC vacancy dashboard. A green CI check is necessary but does **not** prove live source coverage or that newly published vacancies were detected.

## Read first
- `README.md` for the product contract and source-class distinctions.
- `config/profile.yaml`, `job_radar/v2_quality.py`, `job_radar/production_guard.py` and the relevant source adapter.
- `.github/workflows/hourly.yml` and `.github/workflows/v2_tests.yml`.
- The most recent failed/successful GitHub Actions runs, plus `public/status.json` and `public/sources.json` when investigating production failures.

## Standard verification
1. Reproduce the reported defect using the exact failing workflow, step, traceback, and commit when available.
2. Install with `python -m pip install -r requirements.txt`.
3. Run `python -m compileall -q radar.py job_radar tests`.
4. Run `python -m unittest discover -s tests -v`.
5. Add a targeted regression test that fails before the fix and passes afterward, if practical.
6. Separate offline/unit checks from live network/ATS smoke checks. A mocked HTTP response does not prove the real employer website works. Report which checks were and were not performed.

## Never silently weaken these invariants
- Original, independently supportable posting date no older than the configured 96-hour window; never substitute `updated_at`, scraping time, Google index time, or a guessed date.
- A genuinely open, job-specific official application path; 403, 404, anti-bot, redirect problems, and generic careers pages must not be presented as confirmed availability.
- Employer identity, configured geographies, mandatory language fit, and 500 distinct direct employers; keep source counts accurate (configured != productive != vacancies).
- Preserve the full lifetime `data/state.json` `seen` history, deduplication semantics, and the strict admission/production guard. Never invent jobs to meet numerical targets.
- Preserve secure TLS/HTTPS validation and safe URL/hostname boundaries. Do not bypass robots, login, anti-bot, or paywalls.
- A legitimate zero-results run differs from a broken source. Record failures and degraded coverage rather than claiming success.

## Common source of false test failures
- Job fixtures with a hard-coded `end_date` can expire as calendar time advances. Make time-sensitive tests deterministic or give *pagination-only* fixtures a currently valid expiry. Do not remove expiry checks from production merely to satisfy a stale test.

## Change and review discipline
- Work on a **separate branch and pull request**, never write directly to `main`, never force-push, and never auto-merge a repair.
- Avoid edits to `data/state.json`, `public/` generated dashboards, and historical fingerprints in code-only fixes.
- Never print or commit secrets, personal emails, credentials, or application tokens.
- Explain evidence in every PR: root cause, changed behavior, tests, source coverage limitations, potential regression risks, and links to relevant workflow runs.
- If fixing an outage requires a live external source that cannot be verified, clearly state the blocker; do not present the remediation as proven.
