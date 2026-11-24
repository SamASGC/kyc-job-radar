"""Offline replay must consume prior run's artifacts, not scan live job portals."""
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.aml339_replay_artifacts import expected_artifacts, list_complete_run_artifacts, RUN_ID


class OfflineReplaySafetyTests(unittest.TestCase):
    def test_replay_uses_exact_source_run_and_no_live_career_scans(self):
        yaml=Path(".github/workflows/aml339_replay_verified_45434801153.yml").read_text()
        self.assertEqual(yaml.count("--run-id 45434801153"),1)
        self.assertIn("scripts/aml339_replay_artifacts.py",yaml)
        self.assertEqual(len(expected_artifacts()),147)
        self.assertIn("id: deployment",yaml)
        self.assertIn("id: deployment_retry",yaml)
        self.assertIn('if: ${{ steps.deployment.outcome == \'failure\' }}',yaml)
        self.assertIn("AML339_REPLAY_PARENT",yaml)
        self.assertIn('or not 0<=age<=24',yaml)
        self.assertIn("python3 scripts/aml339_site.py",yaml)
        self.assertIn("python3 scripts/aml339_source_manifest.py",yaml)
        self.assertIn("--strict-novelty",yaml)
        self.assertIn("git add data/aml339_main18_state.json public/aml339/",yaml)
        self.assertIn("git push origin HEAD:main",yaml)
        for forbidden in (
            "python3 live_e2e18_full.py --source",
            "python3 live_growth50_probe.py --source",
            "python3 live_batch50_probe.py --source",
            "python3 live_regulated_sidecar.py --source",
            "python3 live_reg100_active.py --source",
        ):
            self.assertNotIn(forbidden,yaml)

    def test_paginated_github_api_finds_late_original_core_jobs(self):
        # Cross-run actions/download-artifact only exposed the FIRST 100
        # artifacts; five mandatory sources were in the 48 later artifacts.
        first=[{"name":"first-"+str(i)} for i in range(100)]
        second=[{"name":"second-"+str(i)} for i in range(48)]
        with patch("scripts.aml339_replay_artifacts.api_json",side_effect=[
            {"total_count":148,"artifacts":first},
            {"total_count":148,"artifacts":second},
        ]) as api:
            all_items=list_complete_run_artifacts("owner/repo","fake-key",RUN_ID)
        self.assertEqual(len(all_items),148)
        self.assertEqual(api.call_count,2)
        self.assertIn("second-47",all_items)

    def test_source_recovery_expected_inventory_is_exactly_18_plus_129(self):
        entries=expected_artifacts()
        self.assertEqual(len(entries),147)
        self.assertEqual(sum(1 for sid,core in entries.values() if core),18)
        self.assertIn("aml339-main18-source-vinted",entries)
        self.assertIn("aml339-main18-source-transfergo",entries)
        self.assertIn("aml339-growth50-live-source-xapo-bank",entries)

    def test_replay_trigger_is_separate_from_daily_scan_paths(self):
        replay=Path(".github/workflows/aml339_replay_verified_45434801153.yml").read_text()
        main=Path(".github/workflows/aml339_main18.yml").read_text()
        trigger="docs/aml339_replay_trigger_45434801153.txt"
        self.assertIn(trigger,replay)
        self.assertNotIn(trigger,main)
        self.assertIn("    branches: [main]",replay)
        self.assertIn("group: kyc-job-radar-hourly",replay)
        self.assertIn("original_run_conclusion",replay)
        self.assertIn('timeout-minutes: 12',replay)


if __name__=="__main__":
    unittest.main()
