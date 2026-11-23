#!/usr/bin/env python3
"""Combine 18 mandatory with 20+50 optional catalog and 2 outside-catalog EMIs.

The original 18 must ALL pass exactly as before. Newly added source failures
are recorded honestly but cannot stop refreshing the original 18. No failed
or unverified optional source may produce a vacancy or alter alert history.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "aml339"))
from alert_history import verify_input_coverage
from batch50_sources import BATCH50

CORE = (
    "vinted", "verifo-lithuania", "demivolt-lithuania", "lt-neo-finance",
    "swedbank", "luminor", "n26", "wise", "corpay", "openpayd",
    "transfergo", "bvnk", "bnf-bank-malta", "medirect-bank-malta",
    "payabl", "airwallex", "mollie", "truelayer",
)
EXPANSION = (
    "iq-eq", "aztec-group", "ebury", "nexpay",
    "nium", "keyrock", "mirabaud", "convera",
    "complyadvantage", "hawk", "clearbank", "modulr",
    "lemonway", "ecommpay", "crossmint", "moonpay",
    "genome", "wallester", "bybit", "zilch",
)
# Separately audited employers NOT in the immutable original 339-source ZIP.
REGULATED = ("emi-trumia-mt", "emi-zen-lt")
OPTIONAL = EXPANSION + BATCH50 + REGULATED


def collect(core_dir: Path, optional_dir: Path):
    core_paths = sorted(core_dir.rglob("source_*.json"))
    if len(core_paths) != len(CORE):
        raise ValueError("Missing or duplicate core evidence: 18 complete sources required")
    verify_input_coverage(core_paths, CORE, require_complete=True)
    extras = sorted(optional_dir.rglob("candidate_*.json")) if optional_dir.exists() else []
    if len(extras) > len(OPTIONAL):
        raise ValueError("Duplicate/unexpected extra source artifact")
    by_id = {}
    for path in extras:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("total_configured_sources") != 339:
                raise ValueError("Wrong source catalog")
            if data.get("mode") != "READ_ONLY_ISOLATED_NO_PRODUCTION_DATA":
                raise ValueError("Wrong source evidence mode")
            arr = data.get("sources")
            if not isinstance(arr, list) or len(arr) != 1:
                raise ValueError("Not a single-source evidence file")
            obj = arr[0]
            sid = obj.get("source_id")
            if sid not in OPTIONAL or path.name != f"candidate_{sid}.json":
                raise ValueError("Unexpected or mismatched source identifier")
            # External sources cannot claim they were part of the original 339.
            # Reject unverified source-registry injection in either direction.
            if sid in REGULATED and (data.get("source_registry") != "regulated_emi_sidecar_v1"
                                     or data.get("original_catalog_sources") != 339):
                raise ValueError("Missing verifiable external EMI registry declaration")
            if sid in EXPANSION and data.get("source_registry") not in (None,"original_339"):
                raise ValueError("Unexpected or mismatched source identifier")
            if sid in by_id:
                raise ValueError("Duplicate source evidence")
            by_id[sid] = (path, obj, None)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"Invalid optional artifact {path.name}: {exc}") from exc

    accepted = []
    skipped = {}
    for sid in OPTIONAL:
        data = by_id.get(sid)
        if data is None:
            skipped[sid] = "no_live_source_evidence"
            continue
        path, obj, _ = data
        if obj.get("state") != "listing_extracted" or obj.get("list_complete") is not True:
            skipped[sid] = "partial_or_failed_listing"
            continue
        audited = obj.get("audited")
        if not isinstance(obj.get("relevant_leads"), int) or not isinstance(audited, list) or len(audited) != obj["relevant_leads"]:
            skipped[sid] = "incomplete_role_detail_audit"
            continue
        if any(not isinstance(role.get("evaluation"), dict) for role in audited):
            skipped[sid] = "missing_role_evaluation"
            continue
        if obj.get("unverified_in_scope", 0) != 0:
            # A future optional source should be added only after all relevant
            # in-scope details can be checked, never by title alone.
            skipped[sid] = "unverified_in_scope_details"
            continue
        accepted.append(path)

    paths = core_paths + accepted
    ids = CORE + tuple(sid for sid in OPTIONAL if sid not in skipped)
    verify_input_coverage(paths, ids, require_complete=True)
    manifest = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "configured_original": 339,
        "core_expected": len(CORE),
        "core_verified": len(CORE),
        "expansion_expected": len(OPTIONAL),
        "expansion_verified": len(accepted),
        "original_optional_expected": len(EXPANSION),
        "bulk50_expected": len(BATCH50),
        "bulk50_verified": sum(sid not in skipped for sid in BATCH50),
        "bulk50_verified_ids": [sid for sid in BATCH50 if sid not in skipped],
        "regulated_external_expected": len(REGULATED),
        "regulated_external_verified": sum(sid not in skipped for sid in REGULATED),
        "regulated_external_ids": list(REGULATED),
        "total_verified": len(paths),
        "verified_source_ids": list(ids),
        "missing_or_failed_expansion": skipped,
        "new_sources_are_optional": True,
        "core_failures_block_publication": True,
    }
    return paths, ids, manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--core-dir", required=True)
    p.add_argument("--expansion-dir", required=True)
    p.add_argument("--paths-out", required=True)
    p.add_argument("--ids-out", required=True)
    p.add_argument("--manifest-out", required=True)
    a = p.parse_args()
    paths, ids, manifest = collect(Path(a.core_dir), Path(a.expansion_dir))
    Path(a.paths_out).write_text("\n".join(map(str, paths)) + "\n", encoding="utf-8")
    Path(a.ids_out).write_text(",".join(ids) + "\n", encoding="utf-8")
    Path(a.manifest_out).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("AML339_GUARDED_EXPANSION", json.dumps({
        "core": manifest["core_verified"],
        "new": manifest["expansion_verified"],
        "failed_optional": manifest["missing_or_failed_expansion"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
