"""v3.9 restores employer-owned ATS APIs for seven previously blocked/404 firms."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERIFIED={
    "Riskified":{"kind":"greenhouse","slug":"riskified"},
    "ComplyAdvantage":{"kind":"greenhouse","slug":"complyadvantage"},
    "Veriff":{"kind":"greenhouse","slug":"veriff"},
    "Alloy":{"kind":"greenhouse","slug":"alloy"},
    "PPRO":{"kind":"ashby","slug":"ppro"},
    "Clear Junction":{"kind":"workable","slug":"clearjunction"},
    "Strise":{"kind":"workable","slug":"strise"}
}

class SourceReliabilityV39(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[]
        for p in ("config/companies.json","config/extra_companies.json"):
            cls.rows+=json.loads((ROOT/p).read_text(encoding="utf-8"))
        cls.by={x["name"]:x for x in cls.rows}

    def test_500_unique_and_169_explicit_public_providers(self):
        self.assertEqual(len(self.rows),500)
        self.assertEqual(len({x["name"].casefold() for x in self.rows}),500)
        self.assertEqual(sum(bool(x.get("ats")) for x in self.rows),169)

    def test_seven_repaired_boards_identity_and_canonical_evidence(self):
        for n,t in VERIFIED.items():
            with self.subTest(company=n):
                row=self.by[n]
                self.assertTrue(row.get("enabled",True))
                self.assertEqual(row["ats"],[t])
                self.assertEqual(row["verification_level"],"official_ats_live_probe_passed")
                self.assertIn(n.casefold(),row["origin"].casefold())
                self.assertTrue(row["careers_url"].startswith("https://"))
                self.assertIn("GitHub Actions 2026-10-13",row["origin"])

    def test_user_contract_unchanged(self):
        import yaml
        p=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertEqual(p["remote_scope"],"Spain")
        self.assertTrue(p["strict_quality_gate"])
        state=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]),306)

if __name__=="__main__":
    unittest.main()
