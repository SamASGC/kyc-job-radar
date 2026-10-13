"""Restore Northern Trust's actual branded public Workday board."""
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NT="https://ntrs.wd1.myworkdayjobs.com/northerntrust"

class NorthernTrustV312(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[]
        for f in ("config/companies.json","config/extra_companies.json"):
            cls.rows+=json.loads((ROOT/f).read_text(encoding="utf-8"))
        cls.by={x["name"]:x for x in cls.rows}

    def test_500_unique_and_173_declared_ats(self):
        self.assertEqual(len(self.rows),500)
        self.assertEqual(len({x["name"].casefold() for x in self.rows}),500)
        self.assertEqual(sum(bool(x.get("ats")) for x in self.rows),173)

    def test_source_owner_and_real_workday_connector(self):
        x=self.by["Northern Trust"]
        self.assertEqual(x["careers_url"],NT)
        self.assertEqual(x["ats"],[{"kind":"workday","url":NT}])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("Northern Trust",x["origin"])
        self.assertIn("GitHub Actions 2026-10-13",x["origin"])

    def test_no_fabricated_workday_date_or_alerts(self):
        from job_radar.v2_quality import original_posted_at
        for v in ("Posted Today","Posted Yesterday","Posted 30+ Days Ago"):
            self.assertIsNone(original_posted_at(v))
        import yaml
        cfg=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertEqual(cfg["max_post_age_hours"],96)
        self.assertTrue(cfg["strict_quality_gate"])
        self.assertEqual(cfg["remote_scope"],"Spain")
        state=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]),306)

if __name__=="__main__":
    unittest.main()
