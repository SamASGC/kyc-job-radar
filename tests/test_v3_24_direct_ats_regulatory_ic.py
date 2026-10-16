"""v3.24: three PROBED official ATS sources and precision-safe regulatory IC discovery.

Actual source endpoint checked by GitHub Actions run 38954205567
(2026-10-16): SumUp 335, Stripe 731, Ebury 143 original requisitions.
These are raw jobs, NOT jobs verified as timely or suitable for the user.
"""
import json
import unittest
from pathlib import Path
from datetime import datetime, timezone
import radar
from job_radar.models import Job
from job_radar.precision import qualifies_regulatory_ic

ROOT=Path(__file__).resolve().parents[1]
PROFILE={"minimum_score":62,"max_post_age_days":4,"max_post_age_hours":96,
         "stale_after_hours":24,"strict_quality_gate":False,
         "exclude_management_roles":True,
         "remote_scope":"Spain","onsite_hybrid_countries":["Spain","Luxembourg","Switzerland","Estonia","Lithuania"],
         "profile_summary":{"languages":{"Spanish":"Native","English":"Professional","French":"Advanced"}}}

class DirectATSRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        companies=[]
        for p in ("config/companies.json","config/extra_companies.json"):
            companies+=json.loads((ROOT/p).read_text(encoding="utf-8"))
        cls.by_name={x["name"]:x for x in companies}
        cls.companies=companies

    def test_500_employers_and_at_least_187_configured_ats(self):
        self.assertEqual(len(self.companies),500)
        self.assertEqual(len(set(self.by_name)),500)
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.companies),187)

    def test_exact_three_identity_verified_greenhouse_feeds(self):
        for name,slug in (("SumUp","sumup"),("Stripe","stripe"),("Ebury","ebury")):
            with self.subTest(name=name):
                row=self.by_name[name]
                self.assertEqual(row["ats"],[{"kind":"greenhouse","slug":slug}])
                self.assertEqual(row["verification_level"],"official_ats_live_probe_passed")
                self.assertIn("38954205567",row["ats_evidence"])

    def test_no_changes_to_hard_policy(self):
        import yaml
        p=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertTrue(p["strict_quality_gate"])
        self.assertTrue(p["exclude_management_roles"])
        self.assertEqual(p["remote_scope"],"Spain")
        self.assertEqual(p["minimum_score"],62)


class RegulatoryICDiscovery(unittest.TestCase):
    def test_suitable_regulatory_monitoring_is_recognized(self):
        title="Regulatory Compliance Analyst"
        text=("Assist the banking division with regulatory compliance reviews, "
              "compliance monitoring and control testing activities, regulatory reporting "
              "and operational risk assessment, 2 years of experience, "
              "stakeholder engagement and internal controls.")
        self.assertTrue(qualifies_regulatory_ic(title,text))
        j=Job(source="Greenhouse:example",source_kind="official ATS",company="Test Bank",sector="Banca",
              title=title,location="Madrid, Spain - Hybrid",description=text,
              posted_at=datetime.now(timezone.utc).isoformat(),apply_url="https://example.com/jobs/123").finalize()
        scored,ok=radar._score_job_with_must_have_gaps(j,PROFILE,known_company=True)
        self.assertIn("technical regulatory compliance",scored.score_reason)
        # Qualifications establish a relevant professional area, not a free pass:
        self.assertTrue(ok)
        self.assertGreaterEqual(scored.score,62)

    def test_nonfinancial_or_empty_boilerplate_is_not_technical_compliance(self):
        for title,desc in (
            ("Compliance Analyst","Coordinate GDPR notices and security policy reporting."),
            ("Compliance Specialist","Work at a bank handling general staff attendance and meetings."),
            ("Data Analyst","Perform control testing, compliance monitoring and regulatory reporting for banks."),
            ("Compliance Analyst","Financial services business: manage calendars and booking schedules."),
        ):
            with self.subTest(title=title,description=desc):
                self.assertFalse(qualifies_regulatory_ic(title,desc))

    def test_technical_compliance_manager_still_hard_excluded(self):
        j=Job(source="Greenhouse:example",source_kind="official ATS",
              company="Test Bank",sector="Banca",title="Regulatory Compliance Manager",
              location="Madrid, Spain - Hybrid", description=(
              "Lead compliance monitoring, control testing and risk assessment across banking "
              "and financial services; manage staff, direct reports and performance reviews."),
              posted_at=datetime.now(timezone.utc).isoformat(),
              apply_url="https://example.com/jobs/manager").finalize()
        _,accepted=radar._score_job_with_must_have_gaps(j,PROFILE,known_company=True)
        self.assertFalse(accepted)

if __name__ == "__main__":
    unittest.main()
