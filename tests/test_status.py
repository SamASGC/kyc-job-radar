from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from job_radar.status import build_status


class PublicHealthTests(unittest.TestCase):
    def test_status_files_reflect_reachable_and_failed_sources(self):
        checks = [
            {"company":"TestPay","ok":True,"jobs":5},
            {"company":"NewPay","ok":True,"jobs":0},
            {"company":"DeadFeed","ok":False,"jobs":0},
            {"company":"v2 application verification","ok":True,"jobs":1},
        ]
        with tempfile.TemporaryDirectory() as td:
            snap=build_status(checks, {"active_dashboard":1,"seen_forever":304},
                              out_dir=td,generated_at="2026-10-12T17:00:00+00:00")
            self.assertEqual(snap["source_checks"],3)
            self.assertEqual(snap["reachable_source_checks"],2)
            self.assertEqual(snap["source_checks_with_jobs"],1)
            self.assertEqual(snap["source_checks_failed"],1)
            self.assertEqual(snap["active_verified_jobs"],1)
            js=json.loads((Path(td)/"status.json").read_text())
            self.assertEqual(js["checked_at_utc"],"2026-10-12T17:00:00+00:00")
            page=(Path(td)/"status.html").read_text()
            self.assertIn("Estado del Radar AML",page)
            self.assertIn("GitHub Actions",page)


if __name__=="__main__":
    unittest.main()
