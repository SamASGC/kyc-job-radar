"""v3.14 repairs Viva.com and Tazapay without mixing declared ATS and generic sites."""
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class TwoSourceRepairsV314(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[]
        for path in ("config/companies.json","config/extra_companies.json"):
            cls.rows+=json.loads((ROOT/path).read_text(encoding="utf-8"))
        cls.by={x["name"]:x for x in cls.rows}

    def test_500_unique_and_176_configured_public_ats(self):
        self.assertEqual(len(self.rows),500)
        self.assertEqual(len({x["name"].casefold() for x in self.rows}),500)
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.rows),176)

    def test_viva_public_workable_employer_board(self):
        x=self.by["Viva.com"]
        self.assertEqual(x["careers_url"],"https://apply.workable.com/viva/")
        self.assertEqual(x["ats"],[{"kind":"workable","slug":"viva"}])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("viva.com/en-es/about/careers",x["origin"])
        self.assertIn("44 public Workable",x["origin"])

    def test_tazapay_first_party_freshteam_not_invented_ats(self):
        x=self.by["Tazapay"]
        self.assertEqual(x["careers_url"],"https://tazapay.freshteam.com/jobs")
        self.assertFalse(x.get("ats"))
        self.assertEqual(x["verification_level"],"official_careers_url_not_necessarily_api")
        self.assertIn("tazapay.com/careers",x["origin"])
        self.assertIn("2 individually",x["origin"])

    def test_persist_96h_original_date_and_seen_ledger(self):
        import yaml
        profile=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertEqual(profile["max_post_age_hours"],96)
        self.assertTrue(profile["strict_quality_gate"])
        self.assertEqual(profile["remote_scope"],"Spain")
        ledger=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(ledger["seen"]),306)
        from job_radar.v2_quality import original_posted_at
        self.assertIsNone(original_posted_at("Posted Today"))

if __name__=="__main__":
    unittest.main()
