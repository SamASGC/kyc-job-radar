from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import traceback
from urllib.parse import urlsplit

from job_radar.config import load_json, load_yaml, save_json
from job_radar.http import Http
from job_radar.models import Job, norm_text, utcnow_iso
from job_radar.state import load_state, save_state
from job_radar.matching import score_job, obvious_non_job_content
from job_radar.salary import estimate_salary
from job_radar.dashboard import build_dashboard
from job_radar.sources.generic import fetch_generic
from job_radar.sources.greenhouse import fetch_greenhouse
from job_radar.sources.lever import fetch_lever
from job_radar.sources.ashby import fetch_ashby
from job_radar.sources.smartrecruiters import fetch_smartrecruiters
from job_radar.sources.workable import fetch_workable
from job_radar.sources.personio import fetch_personio
from job_radar.sources.workday import fetch_workday
from job_radar.sources.recruitee import fetch_recruitee
from job_radar.sources.breezy import fetch_breezy
from job_radar.sources.aggregators import (
    fetch_jobicy, fetch_remotive, fetch_arbeitnow, fetch_remoteok,
    fetch_himalayas, fetch_weworkremotely,
)

SOURCE_PRIORITY = {"official ATS": 3, "official career page": 2, "aggregator": 1}


def _ats_key(company: dict, target: dict) -> str:
    return f"{company['name']}::{target.get('kind')}::{target.get('slug') or target.get('url','')}"


async def fetch_target(http: Http, company: dict, target: dict) -> list[Job]:
    kind = target.get("kind")
    slug = target.get("slug", "")
    if kind == "greenhouse":
        return await fetch_greenhouse(http, company, slug)
    if kind == "lever":
        return await fetch_lever(http, company, slug, eu=False)
    if kind == "lever_eu":
        return await fetch_lever(http, company, slug, eu=True)
    if kind == "ashby":
        return await fetch_ashby(http, company, slug)
    if kind == "smartrecruiters":
        return await fetch_smartrecruiters(http, company, slug)
    if kind == "workable":
        return await fetch_workable(http, company, slug)
    if kind == "personio":
        return await fetch_personio(http, company, slug)
    if kind == "workday":
        return await fetch_workday(http, company, target.get("url") or company["careers_url"])
    if kind == "recruitee":
        return await fetch_recruitee(http, company, slug)
    if kind == "breezy":
        return await fetch_breezy(http, company, slug)
    return []


async def fetch_company(http: Http, company: dict, state: dict) -> tuple[list[Job], dict]:
    health = {"company": company["name"], "ok": True, "jobs": 0, "targets": [], "error": ""}
    discovery = state.setdefault("discovery", {}).get(company["name"], {})
    targets = company.get("ats") or discovery.get("targets") or []
    jobs: list[Job] = []
    errors = []

    if targets:
        for target in targets:
            try:
                got = await fetch_target(http, company, target)
                jobs.extend(got)
                health["targets"].append(target)
            except Exception as e:
                errors.append(f"{target.get('kind')}: {type(e).__name__}: {e}")
        # If all known ATS targets fail, re-discover from the official page.
        if not jobs and company.get("careers_url"):
            try:
                generic_jobs, detected, final_url = await fetch_generic(http, company)
                jobs.extend(generic_jobs)
                if detected:
                    prev_disc = state["discovery"].get(company["name"], {})
                    if prev_disc.get("targets") != detected or prev_disc.get("final_url") != final_url:
                        state["discovery"][company["name"]] = {"targets": detected, "final_url": final_url}
            except Exception as e:
                errors.append(f"rediscovery: {type(e).__name__}: {e}")
    else:
        try:
            generic_jobs, detected, final_url = await fetch_generic(http, company)
            jobs.extend(generic_jobs)
            if detected:
                prev_disc = state["discovery"].get(company["name"], {})
                if prev_disc.get("targets") != detected or prev_disc.get("final_url") != final_url:
                    state["discovery"][company["name"]] = {"targets": detected, "final_url": final_url}
                # Immediately use discovered structured feeds in the same scan.
                for target in detected:
                    try:
                        jobs.extend(await fetch_target(http, company, target))
                    except Exception as e:
                        errors.append(f"discovered {target.get('kind')}: {type(e).__name__}: {e}")
            else:
                if company["name"] not in state["discovery"]:
                    state["discovery"][company["name"]] = {"targets": [], "final_url": final_url}
        except Exception as e:
            errors.append(f"career page: {type(e).__name__}: {e}")

    # Deduplicate within one company/source fetch.
    uniq = {}
    for j in jobs:
        j.finalize()
        prev = uniq.get(j.fingerprint)
        if not prev or SOURCE_PRIORITY.get(j.source_kind, 0) > SOURCE_PRIORITY.get(prev.source_kind, 0):
            uniq[j.fingerprint] = j
    jobs = list(uniq.values())
    health["jobs"] = len(jobs)
    if errors:
        health["error"] = " | ".join(errors)[:1200]
        if not jobs:
            health["ok"] = False
    return jobs, health


async def fetch_aggregators(http: Http, config: dict) -> tuple[list[Job], list[dict], set[str]]:
    """Run reliable public feeds on a source-appropriate cadence.

    The whole radar runs hourly, but some feeds explicitly recommend less frequent polling.
    Skipped sources are returned so their existing dashboard jobs are not marked missing.
    """
    enabled = config.get("aggregators", {})
    cadence = config.get("aggregator_cadence_hours", {})
    hour = datetime.now(timezone.utc).hour
    specs = [
        ("Jobicy", "jobicy", fetch_jobicy),
        ("Remotive", "remotive", fetch_remotive),
        ("Arbeitnow", "arbeitnow", fetch_arbeitnow),
        ("Remote OK", "remoteok", fetch_remoteok),
        ("Himalayas", "himalayas", fetch_himalayas),
        ("We Work Remotely", "weworkremotely", fetch_weworkremotely),
    ]
    tasks, names = [], []
    health: list[dict] = []
    skipped: set[str] = set()
    for display, key, func in specs:
        if not enabled.get(key, True):
            continue
        every = max(1, int(cadence.get(display, 1)))
        if every > 1 and (hour % every) != 0:
            skipped.add(display)
            health.append({"company": display, "ok": True, "jobs": 0, "targets": [{"kind": f"cadence {every}h"}], "error": "skipped this hour by source cadence"})
            continue
        tasks.append(func(http))
        names.append(display)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    jobs: list[Job] = []
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            health.append({"company": name, "ok": False, "jobs": 0, "targets": [], "error": f"{type(result).__name__}: {result}"})
        else:
            jobs.extend(result)
            health.append({"company": name, "ok": True, "jobs": len(result), "targets": [{"kind": "aggregator"}], "error": ""})
    return jobs, health, skipped


def known_company_lookup(companies: list[dict]) -> dict[str, dict]:
    out = {}
    for c in companies:
        out[norm_text(c["name"])] = c
        for alias in c.get("aliases", []):
            out[norm_text(alias)] = c
    return out


def find_known_company(job: Job, lookup: dict[str, dict]) -> dict | None:
    n = norm_text(job.company)
    if n in lookup:
        return lookup[n]
    # Carefully allow exact substring for aliases/brands with suffixes ("Bank", legal suffix, etc.).
    for key, c in lookup.items():
        if len(key) >= 5 and (key in n or n in key):
            return c
    return None


def update_state_with_jobs(state: dict, raw_jobs: list[Job], companies: list[dict], profile: dict, skip_missing_sources: set[str] | None = None) -> tuple[dict, dict]:
    lookup = known_company_lookup(companies)
    skip_missing_sources = skip_missing_sources or set()
    now = utcnow_iso()
    current = state.setdefault("jobs", {})
    seen = state.setdefault("seen", {})
    new_count = 0
    accepted_count = 0
    raw_count = len(raw_jobs)
    semantic_changed = False

    # Remove false positives saved by older generic-crawler versions immediately,
    # rather than waiting for the normal stale timeout. Also remove them from seen.
    for fp, rec in list(current.items()):
        if obvious_non_job_content(rec.get("source_kind", ""), rec.get("title", ""), rec.get("apply_url", "")):
            current.pop(fp, None)
            seen.pop(fp, None)
            semantic_changed = True

    # Cross-source dedupe before scoring, preferring official sources.
    merged: dict[str, Job] = {}
    for j in raw_jobs:
        known = find_known_company(j, lookup)
        if known:
            j.company = known["name"]
            j.sector = known.get("sector", j.sector)
            j.fingerprint = ""
            j.finalize()
        prev = merged.get(j.fingerprint)
        if not prev or SOURCE_PRIORITY.get(j.source_kind, 0) > SOURCE_PRIORITY.get(prev.source_kind, 0):
            merged[j.fingerprint] = j

    fetched_active = set()
    for j in merged.values():
        known = find_known_company(j, lookup)
        scored, ok = score_job(j, profile, known_company=bool(known))
        if not ok:
            continue
        scored.salary_display = estimate_salary(scored)
        accepted_count += 1
        fp = scored.fingerprint
        fetched_active.add(fp)

        if fp in current:
            old = current[fp]
            d = scored.to_dict()
            d["first_seen"] = old.get("first_seen", old.get("discovered_at", now))
            # Keep the original discovery timestamp so a no-op scan does not modify the dataset.
            d["discovered_at"] = old.get("discovered_at", d.get("discovered_at", now))
            # A source may disappear temporarily. Clear missing_since only when it returns.
            if old.get("missing_since"):
                semantic_changed = True
            # Preserve no-op stability: do not store a constantly-changing last_seen timestamp.
            comparable_old = {k: v for k, v in old.items() if k not in {"missing_since"}}
            comparable_new = dict(d)
            if comparable_old != comparable_new:
                semantic_changed = True
            current[fp] = d
            seen.setdefault(fp, {"first_seen": d["first_seen"], "company": scored.company, "title": scored.title, "location": scored.location})
            continue

        # Never re-surface a previously presented vacancy after it left the active dashboard.
        if fp in seen:
            continue

        d = scored.to_dict()
        d["first_seen"] = now
        current[fp] = d
        seen[fp] = {"first_seen": now, "company": scored.company, "title": scored.title, "location": scored.location, "source": scored.source}
        new_count += 1
        semantic_changed = True

    stale_hours = float(profile.get("stale_after_hours", 72))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
    for fp in list(current):
        if fp in fetched_active:
            continue
        rec = current[fp]
        if rec.get("source") in skip_missing_sources:
            continue
        missing_since = rec.get("missing_since")
        if not missing_since:
            rec["missing_since"] = now
            semantic_changed = True
            continue
        try:
            dt = datetime.fromisoformat(missing_since.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
        if dt < cutoff:
            current.pop(fp, None)
            semantic_changed = True

    if semantic_changed or not state.get("dataset_updated_at"):
        state["dataset_updated_at"] = now

    stats = {
        "raw_jobs": raw_count,
        "accepted_this_scan": accepted_count,
        "new_this_scan": new_count,
        "active_dashboard": len(current),
        "seen_forever": len(seen),
        "semantic_changed": semantic_changed,
    }
    # Persist only stable counters; these change only when the dataset changes.
    state["stats"] = {
        "active_dashboard": len(current),
        "seen_forever": len(seen),
    }
    return state, stats


async def run_scan() -> dict:
    companies = load_json("config/companies.json")
    profile = load_yaml("config/profile.yaml")
    runtime = load_yaml("config/runtime.yaml")
    state = load_state()
    http = Http(concurrency=int(runtime.get("concurrency", 24)), timeout=float(runtime.get("timeout_seconds", 18)))
    enabled_companies = [x for x in companies if x.get("enabled", True)]
    total = len(enabled_companies)
    print(f"[RADAR] Escaneando {total} empresas...", flush=True)

    async def one_company(c):
        try:
            # This is a whole-company safety net. Per-request HTTP timeouts still apply.
            result = await asyncio.wait_for(fetch_company(http, c, state), timeout=float(runtime.get("company_timeout_seconds", 240)))
            return c, result, None
        except Exception as e:
            return c, None, e

    try:
        tasks = [asyncio.create_task(one_company(c)) for c in enabled_companies]
        raw_jobs: list[Job] = []
        health = []
        completed = 0
        for fut in asyncio.as_completed(tasks):
            c, result, error = await fut
            completed += 1
            if error is not None:
                health.append({"company": c["name"], "ok": False, "jobs": 0, "targets": [], "error": f"{type(error).__name__}: {error}"})
                print(f"[RADAR] {completed}/{total} {c['name']}: ERROR {type(error).__name__}", flush=True)
            else:
                jobs, h = result
                raw_jobs.extend(jobs)
                health.append(h)
                if completed == 1 or completed % 10 == 0 or not h.get("ok"):
                    status = "OK" if h.get("ok") else "FALLO"
                    print(f"[RADAR] {completed}/{total} completadas | {c['name']}: {status} | {len(jobs)} jobs", flush=True)

        print("[RADAR] Empresas terminadas. Consultando agregadores...", flush=True)
        agg_jobs, agg_health, skipped_aggregators = await fetch_aggregators(http, runtime)
        raw_jobs.extend(agg_jobs)
        health.extend(agg_health)
        print(f"[RADAR] Agregadores terminados | {len(agg_jobs)} jobs brutos", flush=True)
    finally:
        await http.close()

    state, run_stats = update_state_with_jobs(state, raw_jobs, companies, profile, skip_missing_sources=skipped_aggregators)
    save_state(state)
    # Health output contains no generated timestamp so a clean run stays git-clean.
    save_json("data/health.json", {"sources": health})
    jobs = list(state.get("jobs", {}).values())
    jobs.sort(key=lambda x: (-int(x.get("score", 0)), x.get("company", ""), x.get("title", "")))
    build_dashboard(jobs, state.get("stats", {}), "public/index.html", state.get("dataset_updated_at", ""))
    return run_stats
