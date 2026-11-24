"""Offline replay must consume prior run's artifacts, not scan live job portals."""
import unittest
from pathlib import Path


class OfflineReplaySafetyTests(unittest.TestCase):
    def test_replay_uses_exact_source_run_and_no_live_career_scans(self):
        yaml=Path(".github/workflows/aml339_replay_verified_45434801153.yml").read_text()
        self.assertEqual(yaml.count("run-id: 45434801153"),7)
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
