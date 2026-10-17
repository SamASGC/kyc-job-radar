"""Verified Checkout.com direct Ashby restoration and 500-employer no-repeat policy."""
import json
import unittest
from pathlib import Path
from datetime import datetime,timezone
from job_radar.v2_quality import passes_strict_gate
from job_radar.models import Job

ROOT=Path(__file__).resolve().parents[1]

class CheckoutSourceV325(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows=[]
        for p in ("config/companies.json","config/extra_companies.json"):
            rows+=json.loads((ROOT/p).read_text(encoding="utf-8"))
        cls.rows=rows
        cls.checkout=next(x for x in rows if x["name"]=="Checkout.com")

    def test_exact_500_employers_at_least_188_ats_no_duplicate_name(self):
        self.assertEqual(len(self.rows),500)
        self.assertEqual(len({x["name"].casefold() for x in self.rows}),500)
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.rows),188)

    def test_checkout_public_ashby_dated_job_board_attributable_to_employer(self):
        x=self.checkout
        self.assertEqual(x["ats"],[{"kind":"ashby","slug":"checkout.com"}])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("39046502253",x["ats_evidence"])
        self.assertIn("169 distinct",x["ats_evidence"])

    def test_retains_exact_policy_and_anti_repeat_history(self):
        import yaml
        p=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(p["strict_quality_gate"])
        self.assertTrue(p["exclude_management_roles"])
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertEqual(p["remote_scope"],"Spain")
        self.assertEqual(p["minimum_score"],62)
        old=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(old["seen"]),309)
        j=Job(source="Ashby:checkout.com",source_kind="official ATS",
             company="Checkout.com",sector="Payments",
             title="Analyst I, Transaction Monitoring and Screening",
             location="Ebene",description="Merchant monitoring and investigations",
             apply_url="https://jobs.ashbyhq.com/checkout.com/68277152-a89a-4b2e-a678-a45d81a09667",
             posted_at="2026-10-09T07:49:57.932+00:00",
             external_id="68277152-a89a-4b2e-a678-a45d81a09667").finalize()
        self.assertFalse(passes_strict_gate(j,now=datetime(2026,10,17,15,50,tzinfo=timezone.utc),
               known_languages={"Spanish":"Native","English":"Professional","French":"Advanced"}))
if __name__=="__main__": unittest.main()
