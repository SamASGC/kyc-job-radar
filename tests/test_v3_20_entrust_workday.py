"""v3.20: Entrust's employer-owned Workday is a real provider, not a careers-link claim."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRUST = "https://entrust.wd1.myworkdayjobs.com/EntrustCareers"

class EntrustRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = []
        for f in ("config/companies.json", "config/extra_companies.json"):
            cls.rows.extend(json.loads((ROOT / f).read_text(encoding="utf-8")))
        cls.by = {c["name"]: c for c in cls.rows}

    def test_500_distinct_direct_employers_with_at_least_184_declared_ats(self):
        self.assertEqual(len(self.rows), 500)
        self.assertEqual(len({c["name"].casefold() for c in self.rows}), 500)
        self.assertGreaterEqual(sum(bool(c.get("ats")) for c in self.rows), 184)

    def test_entrust_board_is_company_owned_and_probed(self):
        c = self.by["Entrust / Onfido"]
        self.assertEqual(c["careers_url"], ENTRUST)
        self.assertEqual(c["ats"], [{"kind": "workday", "url": ENTRUST}])
        self.assertEqual(c["verification_level"], "official_ats_live_probe_passed")
        self.assertIn("entrust.com/company/careers", c["origin"])
        self.assertIn("88 individually identified jobs", c["origin"])
        self.assertEqual(c["aliases"], ["Entrust", "Onfido"])

    def test_strict_original_date_not_inferred_from_workday_relative_labels(self):
        from job_radar.v2_quality import original_posted_at
        self.assertIsNone(original_posted_at("Posted Today"))
        self.assertIsNone(original_posted_at("Posted Yesterday"))
        import yaml
        cfg = yaml.safe_load((ROOT / "config/profile.yaml").read_text(encoding="utf-8"))
        self.assertEqual(cfg["max_post_age_hours"], 96)
        self.assertTrue(cfg["strict_quality_gate"])
        self.assertEqual(cfg["remote_scope"], "Spain")
        state = json.loads((ROOT / "data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]), 306)

if __name__ == "__main__":
    unittest.main()
