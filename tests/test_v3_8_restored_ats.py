"""Existing direct sources: employer-owned public ATS feeds verified in live GitHub probe."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVEN = {
    "Airwallex": {"kind":"ashby","slug":"airwallex"},
    "Coinbase": {"kind":"greenhouse","slug":"coinbase"},
    "Fireblocks": {"kind":"greenhouse","slug":"fireblocks"},
}

class RestoredATSFeedV38(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.companies = []
        for f in ("config/companies.json","config/extra_companies.json"):
            cls.companies.extend(json.loads((ROOT/f).read_text(encoding="utf-8")))
        cls.by_name={c["name"]:c for c in cls.companies}

    def test_same_500_employers_with_at_least_162_configured_ats(self):
        self.assertEqual(len(self.companies),500)
        self.assertEqual(len({c["name"].casefold() for c in self.companies}),500)
        self.assertGreaterEqual(sum(bool(c.get("ats")) for c in self.companies),162)

    def test_three_attributable_public_recruiting_feeds(self):
        for company,connector in PROVEN.items():
            with self.subTest(company=company):
                c=self.by_name[company]
                self.assertEqual(c["ats"],[connector])
                self.assertEqual(c["verification_level"],"official_ats_live_probe_passed")
                self.assertIn(company.casefold(),c["origin"].casefold())
                self.assertTrue(c["enabled"])

    def test_canonical_employer_links_preserved(self):
        self.assertEqual(self.by_name["Airwallex"]["careers_url"],
            "https://jobs.ashbyhq.com/airwallex")
        self.assertEqual(self.by_name["Coinbase"]["careers_url"],
            "https://www.coinbase.com/careers")
        self.assertEqual(self.by_name["Fireblocks"]["careers_url"],
            "https://www.fireblocks.com/careers")
        self.assertFalse(self.by_name["OakNorth"].get("ats"),
            "OakNorth's observed Lever API 404 is not a valid connector")

    def test_original_publication_and_apply_gates_still_strict(self):
        import yaml
        p=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(p["strict_quality_gate"])
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertEqual(p["remote_scope"],"Spain")
        s=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(s["seen"]),306)

if __name__=="__main__":
    unittest.main()
