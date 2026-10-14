"""Reject people-management vacancies without suppressing specialist SMEs.

Regression: an Alter Domus AML/KYC Associate Manager vacancy temporarily
passed a score threshold despite requiring responsibility for junior staff.
Keep the lifetime seen ID while retracting that role from the dashboard.
"""
import unittest
from pathlib import Path
import yaml
from job_radar.models import Job
from job_radar.matching import excluded_management_role, score_job
from job_radar.scanner import update_state_with_jobs

ROOT=Path(__file__).resolve().parents[1]
PROFILE=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))

def role(title, desc):
    return Job(
        source="Career page:Alter Domus",source_kind="official career page",
        company="Alter Domus",sector="Fintech",title=title,
        location="Vilnius, Lithuania - Hybrid",
        description=desc,
        apply_url="https://careers.alterdomus.com/en/job/vilnius/aml-kyc-associate-manager/38735/45905310976",
        external_id="45905310976",posted_at="2026-10-13",
    ).finalize()

class IndividualContributorPolicy(unittest.TestCase):
    def test_management_exclusion_enabled(self):
        self.assertTrue(PROFILE["exclude_management_roles"])
        self.assertEqual(PROFILE["max_post_age_hours"],96)
        self.assertTrue(PROFILE["strict_quality_gate"])
        self.assertEqual(PROFILE["remote_scope"],"Spain")

    def test_real_manager_role_is_rejected_even_with_high_kyc_fit(self):
        job=role("AML/KYC Associate Manager",
           "You will support AML/KYC regulatory requirements and high risk UBO "
           "CDD/EDD review, taking responsibility for the work, development "
           "and performance of a group of junior colleagues. "
           "Coordinate daily team workflow and ensure deadlines. "
           "At least three years financial services experience.")
        self.assertTrue(excluded_management_role(job, PROFILE))
        self.assertFalse(score_job(job,PROFILE,known_company=True)[1])

    def test_top_leadership_and_explicit_line_management(self):
        for title in ("Head of Financial Crime","Compliance Director",
                      "MLRO","Chief Risk Officer","AML Team Leader",
                      "KYC Operations Manager","VP Sanctions"):
            with self.subTest(title=title):
                self.assertTrue(excluded_management_role(role(title,"AML KYC team."),PROFILE))
        self.assertTrue(excluded_management_role(
            role("Senior AML Specialist","Responsible for direct reports and staff performance reviews."),PROFILE))

    def test_keep_individual_contributor_with_mentoring_and_case_management(self):
        for title,description in (
            ("Senior KYC Specialist","Mentor junior analysts with complex UBO cases."),
            ("Financial Crime Investigator","Manage AML case queues and risk investigations independently."),
            ("Compliance SME","Coach new hires on policies, collaborate with the Head of Compliance."),
        ):
            with self.subTest(title=title):
                self.assertFalse(excluded_management_role(role(title,description),PROFILE))

    def test_ledger_preserved_when_prior_false_positive_is_retracted(self):
        job=role("AML/KYC Associate Manager",
            "Taking responsibility for the work, development and performance "
            "of junior colleagues, high-risk KYB and UBO review.")
        fp=job.fingerprint
        state={
            "strict_v2_baseline":"2026-10-01T12:00:00+00:00",
            "jobs":{fp:job.to_dict()},
            "seen":{fp:{"company":job.company,"title":job.title,
                "source":job.source,"external_id":job.external_id,
                "first_seen":"2026-10-14T00:47:55+00:00"}},
        }
        result,stats=update_state_with_jobs(state,[],
            [{"name":"Alter Domus","sector":"Fintech"}],PROFILE)
        self.assertEqual(result["jobs"],{})
        self.assertIn(fp,result["seen"])
        self.assertEqual(stats["new_this_scan"],0)
        self.assertEqual(stats["seen_forever"],1)

if __name__=="__main__":
    unittest.main()
