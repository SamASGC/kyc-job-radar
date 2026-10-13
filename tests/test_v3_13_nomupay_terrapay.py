"""Recover two blocked payment-processor official recruiting feeds without expanding companies."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class EmployerFeedsV313(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[]
        for name in ("config/companies.json","config/extra_companies.json"):
            cls.rows+=json.loads((ROOT/name).read_text(encoding="utf-8"))
        cls.by_name={x["name"]:x for x in cls.rows}

    def test_exact_500_distinct_and_175_provider_configs(self):
        self.assertEqual(len(self.rows),500)
        self.assertEqual(len({x["name"].casefold() for x in self.rows}),500)
        self.assertEqual(sum(bool(x.get("ats")) for x in self.rows),175)

    def test_nomupay_real_personio_recruitment(self):
        x=self.by_name["NomuPay"]
        self.assertEqual(x["careers_url"],"https://nomupay.jobs.personio.com/")
        self.assertEqual(x["ats"],[{"kind":"personio","slug":"nomupay"}])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("nomupay.com/career",x["origin"])
        self.assertIn("4 individually identified",x["origin"])

    def test_terrapay_real_workable_recruitment(self):
        x=self.by_name["TerraPay"]
        self.assertEqual(x["careers_url"],"https://apply.workable.com/terrapay/")
        self.assertEqual(x["ats"],[{"kind":"workable","slug":"terrapay"}])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("terrapay.com/careers",x["origin"])
        self.assertIn("8 individual",x["origin"])

    def test_missing_original_date_must_never_generate_96h_alert(self):
        from job_radar.v2_quality import original_posted_at
        for x in ("", "Posted Today", "Posted Yesterday", "2 days ago"):
            self.assertIsNone(original_posted_at(x))
        import yaml
        p=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(p["strict_quality_gate"])
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertEqual(p["remote_scope"],"Spain")
        state=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]),306)

if __name__=="__main__":
    unittest.main()
