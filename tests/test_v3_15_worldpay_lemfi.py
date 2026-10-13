"""v3.15: recover Worldpay/LemFi using attributable structured recruiting feeds."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORLD="https://worldpay.wd5.myworkdayjobs.com/Worldpay_External_Careers_Site"
LEMFI="https://jobs.ashbyhq.com/lemfi"

class FinancialSourceRepairsV315(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.employers=[]
        for file in ("config/companies.json","config/extra_companies.json"):
            cls.employers+=json.loads((ROOT/file).read_text(encoding="utf-8"))
        cls.by={e["name"]:e for e in cls.employers}

    def test_500_unique_employers_and_exactly_179_ats_configs(self):
        self.assertEqual(len(self.employers),500)
        self.assertEqual(len({x["name"].casefold() for x in self.employers}),500)
        self.assertEqual(sum(bool(x.get("ats")) for x in self.employers),179)

    def test_worldpay_live_first_party_workday(self):
        x=self.by["Worldpay"]
        self.assertEqual(x["careers_url"],WORLD)
        self.assertEqual(x["ats"],[{"kind":"workday","url":WORLD}])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("95 individual public CXS",x["origin"])
        self.assertIn("CDD Advisory Analyst",x["origin"])

    def test_lemfi_live_employer_ashby(self):
        x=self.by["LemFi"]
        self.assertEqual(x["careers_url"],LEMFI)
        self.assertEqual(x["ats"],[{"kind":"ashby","slug":"lemfi"}])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("14 public structured Ashby",x["origin"])
        self.assertIn("Fincrime Analyst",x["origin"])

    def test_dlocal_public_lever(self):
        x=self.by["dLocal"]
        self.assertEqual(x["careers_url"],"https://jobs.lever.co/dlocal")
        self.assertEqual(x["ats"],[{"kind":"lever","slug":"dlocal"}])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("52 distinct",x["origin"])

    def test_vp_bank_umantis_remains_verified_public_site_not_fake_api(self):
        x=self.by["VP Bank Group"]
        self.assertEqual(x["careers_url"],
            "https://recruitingapp-2813.umantis.com/Jobs/All?CompanyID=All&Reset=G&lang=eng")
        self.assertFalse(x.get("ats"))
        self.assertIn("10 individual",x["origin"])
        self.assertEqual(x["verification_level"],"official_careers_url_not_necessarily_api")

    def test_no_claim_of_other_blocked_ats_sources(self):
        # OakNorth/Papara still show Cloudflare/protected/corporate 403
        self.assertFalse(self.by["OakNorth"].get("ats"))
        self.assertFalse(self.by["Sygnum Bank"].get("ats"))
        self.assertFalse(self.by["Papara"].get("ats")) if "Papara" in self.by else None

    def test_lifetime_and_strict_96_hour_original_date_filters_unchanged(self):
        import yaml
        p=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(p["strict_quality_gate"])
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertEqual(p["remote_scope"],"Spain")
        ledger=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(ledger["seen"]),306)
        from job_radar.v2_quality import original_posted_at
        self.assertIsNone(original_posted_at("Posted Today"))
        self.assertIsNone(original_posted_at("Posted 1 day ago"))

if __name__=="__main__":
    unittest.main()
