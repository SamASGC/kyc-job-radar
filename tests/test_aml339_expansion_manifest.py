"""No optional AML339 source failure can suppress the previously audited core."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aml339_source_manifest import CORE, EXPANSION, REGULATED, REGULATOR50, REG100_LIVE, collect, DYNAMIC_LIVE
from batch50_sources import BATCH50
from growth_wave50_sources import WAVE50_B


def snapshot(sid, *, failed=False, verified=True):
    return {
        "total_configured_sources": 339,
        "mode": "READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "sources": [{
            "source_id": sid,
            "state": "listing_failed" if failed else "listing_extracted",
            "list_complete": not failed,
            "relevant_leads": 0,
            "audited": [],
            "unverified_in_scope": 0 if verified else 1,
        }],
    }


class ExpansionManifestTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.core = self.base / "core"
        self.optional = self.base / "optional"
        self.core.mkdir()
        self.optional.mkdir()
        for sid in CORE:
            self.put(self.core / f"source_{sid}.json", snapshot(sid))

    def put(self, path, obj):
        path.write_text(json.dumps(obj), encoding="utf-8")

    def test_all_twenty_expand_to_38(self):
        for sid in EXPANSION:
            self.put(self.optional / f"candidate_{sid}.json", snapshot(sid))
        paths, ids, manifest = collect(self.core, self.optional)
        self.assertEqual(len(paths), 38)
        self.assertEqual(len(ids), 38)
        self.assertEqual(manifest["core_verified"], 18)
        self.assertEqual(manifest["expansion_verified"], 20)
        self.assertEqual(set(manifest["missing_or_failed_expansion"]),set(REGULATED)|set(BATCH50)|set(REGULATOR50)|set(REG100_LIVE)|set(WAVE50_B)|set(DYNAMIC_LIVE))

    def test_optional_http_failure_keeps_all_18_core(self):
        for sid in EXPANSION:
            self.put(self.optional / f"candidate_{sid}.json",
                     snapshot(sid, failed=(sid == "nium")))
        paths, ids, manifest = collect(self.core, self.optional)
        self.assertEqual(len(paths), 37)
        self.assertEqual(ids[:18], CORE)
        self.assertEqual(manifest["missing_or_failed_expansion"],
                         {"nium": "partial_or_failed_listing", **{sid:"no_live_source_evidence" for sid in REGULATED+BATCH50+REGULATOR50+REG100_LIVE+WAVE50_B+DYNAMIC_LIVE}})

    def test_optional_unverified_job_is_suppressed(self):
        self.put(self.optional / "candidate_nexpay.json",
                 snapshot("nexpay", verified=False))
        paths, ids, manifest = collect(self.core, self.optional)
        self.assertEqual(len(paths), 18)
        self.assertEqual(ids, CORE)
        self.assertEqual(manifest["missing_or_failed_expansion"]["nexpay"],
                         "unverified_in_scope_details")

    def test_core_missing_fails_closed_even_if_optional_works(self):
        (self.core / f"source_{CORE[0]}.json").unlink()
        self.put(self.optional / "candidate_iq-eq.json", snapshot("iq-eq"))
        with self.assertRaisesRegex(ValueError, "core evidence"):
            collect(self.core, self.optional)

    def test_mismatched_optional_identity_rejected(self):
        self.put(self.optional / "candidate_iq-eq.json", snapshot("nexpay"))
        with self.assertRaisesRegex(ValueError, "mismatched"):
            collect(self.core, self.optional)

    def test_duplicate_optional_fails_closed(self):
        self.put(self.optional / "candidate_iq-eq.json", snapshot("iq-eq"))
        dup = self.optional / "dup"
        dup.mkdir()
        self.put(dup / "candidate_iq-eq.json", snapshot("iq-eq"))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            collect(self.core, self.optional)


if __name__ == "__main__":
    unittest.main()
