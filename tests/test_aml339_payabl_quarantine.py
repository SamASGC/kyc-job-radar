"""Fail-closed per-source, fail-open publication for Payabl Workable HTTP429 only.

This is the actual production blocker in run 45383138855. Source-specific
errors must not suppress other employers, and must not generate/close jobs.
"""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aml339_source_manifest import CORE, STRICT_CORE, QUARANTINABLE_CORE, collect
from scripts.aml339_site import build
from alert_history import blank_history, read_evidence, select_and_merge


def source(sid,failed=False):
    return {
       "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
       "total_configured_sources":339,
       "sources":[{
          "source_id":sid,
          "state":"listing_failed" if failed else "listing_extracted",
          "list_complete":not failed,
          "total_listed":0 if not failed else None,
          "relevant_leads":0 if not failed else None,
          "audited":[],
          "unverified_in_scope":0,
          "listing_role_keys":[] if not failed else [],
          "listing_untrackable_count":0 if not failed else 0,
          "errors":["HTTP 429: Retry-After 46747 seconds"] if failed else [],
       }]
    }


class CoreQuarantineTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.core=self.root/"core"
        self.extra=self.root/"extra"
        self.core.mkdir()
        self.extra.mkdir()
        for sid in CORE:
            self.put(sid,source(sid))

    def put(self,sid,d):
        (self.core/f"source_{sid}.json").write_text(json.dumps(d),encoding="utf-8")

    def test_only_payabl_can_be_quarantined(self):
        self.assertEqual(QUARANTINABLE_CORE,("payabl",))
        self.assertEqual(len(CORE),18)
        self.assertEqual(len(STRICT_CORE),17)
        self.assertEqual(set(CORE)-set(STRICT_CORE),{"payabl"})

    def test_429_payabl_does_not_block_17_source_publish(self):
        self.put("payabl",source("payabl",failed=True))
        paths,ids,m=collect(self.core,self.extra)
        self.assertEqual(len(paths),17)
        self.assertEqual(len(ids),17)
        self.assertNotIn("payabl",ids)
        self.assertEqual(m["core_expected"],18)
        self.assertEqual(m["core_verified"],17)
        self.assertEqual(m["strict_core_verified"],17)
        self.assertEqual(m["missing_or_failed_core"],{"payabl":"incomplete_or_rate_limited_source"})
        self.assertEqual(m["expansion_verified"],0)
        prior=blank_history()
        state,report=select_and_merge(
            read_evidence(paths),prior,configured_sources=ids,
            strict_novelty=True,listing_keys={sid:[] for sid in ids})
        self.assertEqual(report["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":0})
        dest=self.root/"site"
        build(paths,state,report,dest,m)
        summary=json.loads((dest/"summary.json").read_text())
        self.assertEqual(summary["sources_complete"],17)
        self.assertEqual(summary["core_sources_complete"],17)
        self.assertEqual(summary["core_sources_expected"],18)
        self.assertEqual(summary["missing_or_failed_core"],{"payabl":"incomplete_or_rate_limited_source"})
        self.assertIn("Payabl",(dest/"index.html").read_text())
        self.assertTrue(summary["novelty_guard_enabled"])

    def test_missing_payabl_artifact_may_publish_but_is_explicit(self):
        (self.core/"source_payabl.json").unlink()
        paths,ids,m=collect(self.core,self.extra)
        self.assertEqual(len(paths),17)
        self.assertEqual(m["missing_or_failed_core"],{"payabl":"no_live_source_evidence"})

    def test_any_other_original_core_missing_fails_hard(self):
        (self.core/"source_wise.json").unlink()
        self.put("payabl",source("payabl",failed=True))
        with self.assertRaisesRegex(ValueError,"core evidence"):
            collect(self.core,self.extra)

    def test_payabl_identity_tamper_is_fatal_not_silently_quarantined(self):
        invalid=source("wise",failed=True)
        self.put("payabl",invalid)
        with self.assertRaisesRegex(ValueError,"identity"):
            collect(self.core,self.extra)

    def test_all_eighteen_complete_sources_still_pass_as_before(self):
        paths,ids,m=collect(self.core,self.extra)
        self.assertEqual(len(paths),18)
        self.assertEqual(ids,CORE)
        self.assertEqual(m["core_verified"],18)
        self.assertFalse(m["missing_or_failed_core"])

    def test_workflow_retains_original_strict_core_and_marks_optional_failures_nonfatal(self):
        yaml=Path(".github/workflows/aml339_main18.yml").read_text()
        self.assertIn("continue-on-error: ${{ matrix.source == 'payabl' }}",yaml)
        self.assertIn("strict_core_verified",yaml)
        self.assertIn("needs.scan.result == 'success'",yaml)
        self.assertGreaterEqual(yaml.count("continue-on-error: true"),6)


if __name__=="__main__":
    unittest.main()
