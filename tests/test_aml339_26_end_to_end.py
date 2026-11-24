"""Full 38-source synthetic E2E: separate official source evidence and dedup state."""
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.aml339_source_manifest import CORE, EXPANSION, REGULATED, REGULATOR50, REG100_LIVE, collect, DYNAMIC_LIVE
from batch50_sources import BATCH50
from growth_wave50_sources import WAVE50_B
from scripts.aml339_site import build
from alert_history import blank_history, select_and_merge, read_evidence
from two_lane_alert_preview import role_template


def evidence(sid, role=None, *, failed=False):
    rows = [role] if role is not None else []
    return {
        "total_configured_sources": 339,
        "mode": "READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "sources": [{
            "source_id": sid, "state": "listing_failed" if failed else "listing_extracted",
            "list_complete": not failed, "relevant_leads": len(rows), "audited": rows,
            "unverified_in_scope": 0,
        }],
    }


class ExpandedFeedE2E(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.core = self.root / "core"
        self.extra = self.root / "extra"
        self.core.mkdir()
        self.extra.mkdir()
        self.role = role_template(
            title="KYC AML Screening Analyst", url="https://example.org/jobs/241700",
        )
        for sid in CORE:
            (self.core / f"source_{sid}.json").write_text(json.dumps(evidence(sid)), encoding="utf-8")
        for sid in EXPANSION:
            (self.extra / f"candidate_{sid}.json").write_text(
                json.dumps(evidence(sid, self.role if sid == "nexpay" else None)), encoding="utf-8"
            )

    def _run(self, prior=None):
        paths, ids, manifest = collect(self.core, self.extra)
        rows = read_evidence(paths)
        new_history, report = select_and_merge(
            rows, prior if prior is not None else blank_history(),
            "full-26-test", configured_sources=ids,
        )
        out = self.root / "site"
        build(paths, new_history, report, out, manifest)
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        return new_history, report, manifest, summary, out

    def test_all_38_publish_only_verified_roles_and_no_replay_duplicates(self):
        history, report, manifest, summary, out = self._run()
        self.assertEqual(summary["sources_complete"], 38)
        self.assertEqual(summary["expanded_sources_complete"], 20)
        self.assertEqual(summary["core_sources_complete"], 18)
        self.assertEqual(report["new_counts"]["promising_date_unconfirmed"], 1)
        root = ET.fromstring((out / "review.xml").read_text(encoding="utf-8"))
        self.assertEqual(len(root.findall("./channel/item")), 1)
        guid = root.findtext("./channel/item/guid")
        history2, replay, manifest2, summary2, out2 = self._run(prior=history)
        self.assertEqual(replay["new_counts"], {
            "confirmed_recent": 0, "promising_date_unconfirmed": 0,
        })
        self.assertEqual(summary2["sources_complete"], 38)
        self.assertEqual(ET.fromstring((out2 / "review.xml").read_text()).findtext(
            "./channel/item/guid"
        ), guid)
        self.assertEqual(set(history["records"]), set(history2["records"]))

    def test_degraded_optional_portal_keeps_history_and_core_feed_alive(self):
        first, _, _, _, _ = self._run()
        (self.extra / "candidate_nexpay.json").write_text(
            json.dumps(evidence("nexpay", failed=True)), encoding="utf-8"
        )
        history, report, manifest, summary, out = self._run(prior=first)
        self.assertEqual(summary["sources_complete"], 37)
        self.assertEqual(summary["core_sources_complete"], 18)
        self.assertEqual(summary["missing_or_failed_expansion"], {
            "nexpay": "partial_or_failed_listing",
            **{sid:"no_live_source_evidence" for sid in REGULATED+BATCH50+REGULATOR50+REG100_LIVE+WAVE50_B+DYNAMIC_LIVE},
        })
        self.assertEqual(report["new_counts"], {
            "confirmed_recent": 0, "promising_date_unconfirmed": 0,
        })
        self.assertEqual(set(first["records"]), set(history["records"]))
        self.assertEqual(
            len(ET.fromstring((out / "review.xml").read_text()).findall("./channel/item")), 0,
        )
        # A failed extra is unknown/temporarily unavailable, not a closed vacancy.

    def test_second_eight_missing_still_publish_original_26_and_old_history(self):
        first, _, _, _, _ = self._run()
        for sid in EXPANSION[8:]:
            (self.extra / f"candidate_{sid}.json").unlink()
        history, replay, manifest, summary, out = self._run(prior=first)
        self.assertEqual(summary["sources_complete"], 26)
        self.assertEqual(summary["expanded_sources_complete"], 8)
        self.assertEqual(set(summary["missing_or_failed_expansion"]), set(EXPANSION[8:]) | set(REGULATED) | set(BATCH50) | set(REGULATOR50) | set(REG100_LIVE)|set(WAVE50_B)|set(DYNAMIC_LIVE))
        self.assertEqual(replay["new_counts"], {
            "confirmed_recent": 0, "promising_date_unconfirmed": 0,
        })
        self.assertEqual(set(history["records"]), set(first["records"]))

    def test_unverified_expansion_without_manifest_never_publishes(self):
        paths, ids, manifest = collect(self.core, self.extra)
        history, report = select_and_merge(read_evidence(paths), blank_history(),
                                           configured_sources=ids)
        with self.assertRaisesRegex(ValueError, "manifest"):
            build(paths, history, report, self.root / "refused")
        self.assertFalse((self.root / "refused").exists())


if __name__ == "__main__":
    unittest.main()
