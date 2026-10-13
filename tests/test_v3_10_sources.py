"""v3.10: recover three attributable public ATS boards, without adding employers."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VALID={
    "PayPal":{"kind":"workday","url":"https://paypal.wd1.myworkdayjobs.com/en-US/jobs"},
    "Trading 212":{"kind":"ashby","slug":"trading212"},
    "Trulioo":{"kind":"ashby","slug":"trulioo"}
}

class MoreATSProvidersV310(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.employers=[]
        for path in ("config/companies.json","config/extra_companies.json"):
            cls.employers.extend(json.loads((ROOT/path).read_text(encoding="utf-8")))
        cls.by_name={x["name"]:x for x in cls.employers}

    def test_exact_500_distinct_and_172_ats_connectors(self):
        self.assertEqual(len(self.employers),500)
        self.assertEqual(len({x["name"].casefold() for x in self.employers}),500)
        self.assertEqual(sum(bool(x.get("ats")) for x in self.employers),172)

    def test_three_live_attributable_public_recruitment_boards(self):
        for name,target in VALID.items():
            with self.subTest(company=name):
                x=self.by_name[name]
                self.assertTrue(x["enabled"])
                self.assertEqual(x["ats"],[target])
                self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
                self.assertIn(name.casefold().replace(" ",""), x["careers_url"].casefold().replace(" ",""))
                self.assertIn(x["careers_url"],x["origin"])
                self.assertIn("GitHub Actions",x["origin"])
                self.assertIn("2026-10-13",x["origin"])

    def test_date_and_lifetime_ledger_unchanged(self):
        import yaml
        p=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(p["strict_quality_gate"])
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertEqual(p["remote_scope"],"Spain")
        s=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(s["seen"]),306)

    def test_workday_relative_label_not_original_publication(self):
        from job_radar.v2_quality import original_posted_at
        self.assertIsNone(original_posted_at("Posted Today"))
        self.assertIsNone(original_posted_at("Posted 2 Days Ago"))

if __name__=="__main__":
    unittest.main()
