"""v3.7: repairs must produce attributable sources and never loosen eligibility."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDMAN = "https://hdpc.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/LateralHiring"
FUNCRAFT = "https://apply.workable.com/fundcraft/"
OKB = "https://okb.abacuscity.ch/de/jobportal"
MORGAN = "https://morganstanley.eightfold.ai/careers?domain=morganstanley.com"


class EmployerRepairsV37Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.all = []
        for f in ("config/companies.json", "config/extra_companies.json"):
            cls.all += json.loads((ROOT / f).read_text(encoding="utf-8"))
        cls.by_name = {x["name"]:x for x in cls.all}

    def test_500_unique_and_minimum_159_real_configured_connectors(self):
        self.assertEqual(len(self.all), 500)
        self.assertEqual(len({x["name"].casefold() for x in self.all}), 500)
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.all), 159)

    def test_goldman_oracle_requisitions_not_corporate_403_page(self):
        c = self.by_name["Goldman Sachs"]
        self.assertEqual(c["careers_url"], GOLDMAN)
        self.assertEqual(c["ats"], [{"kind":"oracle_hcm","site":"LateralHiring",
                                      "language":"en","url":GOLDMAN}])
        self.assertIn("higher.gs.com/roles", c["origin"])
        self.assertIn(GOLDMAN, c["origin"])

    def test_fundcraft_official_workable(self):
        c=self.by_name["fundcraft"]
        self.assertEqual(c["careers_url"], FUNCRAFT)
        self.assertEqual(c["ats"], [{"kind":"workable","slug":"fundcraft"}])
        self.assertIn("fundcraft.lu/careers/", c["origin"])

    def test_obwaldner_follows_official_employer_iframe(self):
        c=self.by_name["Obwaldner Kantonalbank"]
        self.assertEqual(c["careers_url"], OKB)
        self.assertFalse(c.get("ats"))
        self.assertIn("okb.ch", c["origin"])

    def test_morgan_branded_official_eightfold_without_fake_ats(self):
        c=self.by_name["Morgan Stanley"]
        self.assertEqual(c["careers_url"], MORGAN)
        self.assertFalse(c.get("ats"))

    def test_no_change_to_user_job_admission_filters(self):
        import yaml
        p = yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertTrue(p["strict_quality_gate"])
        self.assertEqual(p["remote_scope"],"Spain")
        state=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]),306)


if __name__ == "__main__":
    unittest.main()
