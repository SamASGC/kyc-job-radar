"""Release safety: cron sweeps must not overwrite a completing deployment."""
from pathlib import Path
import unittest


class HourlyWorkflowSafetyTests(unittest.TestCase):
    def test_cron_and_baseline_uncorrupted(self):
        p = Path(__file__).resolve().parents[1] / ".github/workflows/hourly.yml"
        workflow = p.read_text(encoding="utf-8")
        self.assertIn('cron: "17 * * * *"', workflow)
        self.assertIn('cron: "47 * * * *"', workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("timeout-minutes: 12", workflow)

    def test_engine_changes_trigger_guarded_scan_without_bot_commit_loop(self):
        p = Path(__file__).resolve().parents[1] / ".github/workflows/hourly.yml"
        workflow = p.read_text(encoding="utf-8")
        for path in ('"job_radar/**"', '"radar.py"', '"config/**"',
                     '"requirements.txt"'):
            self.assertIn(path, workflow)
        # The scan itself only commits these dataset/artifact files. None
        # should match a push trigger or spin another scanning workflow.
        for path in ('"data/state.json"', '"public/**"', '"data/**"'):
            self.assertNotIn(f'      - {path}', workflow)
        self.assertIn("Run regression tests", workflow)
        self.assertIn("Verify source coverage and preserve all historical job fingerprints", workflow)

    def test_never_commit_transient_health_telemetry(self):
        p = Path(__file__).resolve().parents[1] / ".github/workflows/hourly.yml"
        workflow = p.read_text(encoding="utf-8")
        self.assertIn("git restore -- data/health.json", workflow)
        self.assertNotIn("git add data/health.json", workflow)
        self.assertIn("git add data/state.json public/index.html public/feed.xml",
                      workflow)
        self.assertIn("git pull --rebase origin main", workflow)
        self.assertNotIn("git push --force", workflow)


if __name__ == "__main__":
    unittest.main()
