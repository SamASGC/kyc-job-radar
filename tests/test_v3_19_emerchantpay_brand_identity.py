"""v3.19: a verified Workable feed and a brand collision exclusion."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class SourceFixV319Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all=[]
        for file in ("config/companies.json","config/extra_companies.json"):
            cls.all.extend(json.loads((ROOT/file).read_text(encoding="utf-8")))
        cls.by={x["name"]:x for x in cls.all}

    def test_exact_500_and_183_ats_configurations(self):
        self.assertEqual(len(self.all),500)
        self.assertEqual(len({x["name"].casefold() for x in self.all}),500)
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.all),183)

    def test_emerchantpay_first_party_attributed_workable_feed(self):
        x=self.by["emerchantpay"]
        self.assertEqual(x["careers_url"],"https://apply.workable.com/emerchantpay/")
        self.assertEqual(x["ats"],[{"kind":"workable","slug":"emerchantpay"}])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("emerchantpay.com/careers/",x["origin"])
        self.assertIn("13 individual requisition records",x["origin"])

    def test_swiss_neon_not_confused_with_gaming_payments_neon(self):
        from job_radar.discovery import ats_target_has_company_identity
        bank=self.by["neon Switzerland"]
        gaming={"kind":"ashby","slug":"neon"}
        self.assertFalse(bank.get("ats"))
        self.assertEqual(bank["disallowed_ats"],[gaming])
        self.assertFalse(ats_target_has_company_identity(bank,gaming))
        self.assertTrue(ats_target_has_company_identity({"name":"Neon"},gaming))
        self.assertTrue(ats_target_has_company_identity(
            {"name":"neon Switzerland","aliases":["neon"]}, {"kind":"ashby","slug":"neon"}
        ), "Default matching without employer-specific proof does not distinguish colliding brands")

    def test_strict_employment_eligibility_and_lifetime_dedup_retained(self):
        import yaml
        p=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(p["strict_quality_gate"])
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertEqual(p["remote_scope"],"Spain")
        state=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]),306)

if __name__=="__main__":
    unittest.main()
