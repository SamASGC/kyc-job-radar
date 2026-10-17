"""Avoid declaring local Luxembourg funds regulatory experience the user lacks.

The original Oct-15 Apex Group Munsbach requisition specifies prior AML/KYC
experience in Luxembourg fund administration as a *required skill*; generic
corporate merchant KYB is transferable but does not satisfy that must-have.
"""
import unittest
from job_radar.fit_adjustments import _required_luxembourg_funds_experience_gap, apply_fit_adjustments
from job_radar.models import Job

PROFILE={"jurisdiction_gaps":["Maltese AML/CFT / PMLFTR / FIAU","Luxembourg funds AML/KYC"],"minimum_score":62}

def job(description):
    j=Job(source="Workday:theapexgroup/apexgroupcareers",source_kind="official ATS",
        company="Apex Group",sector="Investment Services",title="Client KYC Officer",
        location="Luxembourg",apply_url="https://example.com/jobs/1",description=description)
    j.score=85
    return j.finalize()


class LocalIndustryQualificationTests(unittest.TestCase):
    def test_apex_group_actual_luxembourg_fund_requirement_is_hard_gap(self):
        desc=(
          "<p>Skills Required</p><p>Apprenticeship in the financial industry or a university degree</p>"
          "<p>Relevant experience in the Luxembourg AML/KYC area in the Luxemburg Fund industry</p>"
          "<p>Good knowledge of AML/KYC requirements and regulatory framework</p>"
        )
        j=job(desc)
        self.assertTrue(_required_luxembourg_funds_experience_gap(j,PROFILE))
        _,ok=apply_fit_adjustments(j,PROFILE,True)
        self.assertFalse(ok)
        self.assertIn("experiencia AML/KYC previa en fondos luxemburgueses",j.score_reason)

    def test_luxembourg_job_address_does_not_trigger_fund_hard_gap(self):
        j=job("<p>Analyze corporate client KYC, CDD, ownership and adverse media"
              " for financial services clients in Luxembourg</p>")
        self.assertFalse(_required_luxembourg_funds_experience_gap(j,PROFILE))
        _,ok=apply_fit_adjustments(j,PROFILE,True)
        self.assertTrue(ok)

    def test_fund_experience_that_is_merely_preferred_is_not_hard_gap(self):
        j=job("<p>Previous experience in Luxembourg investment fund industry"
              " is preferred but not required. 3 years of corporate KYB experience.</p>")
        self.assertFalse(_required_luxembourg_funds_experience_gap(j,PROFILE))

    def test_gap_only_applies_when_in_profile(self):
        j=job("<p>Relevant experience in the Luxembourg AML/KYC area in the Luxemburg Fund industry</p>")
        self.assertFalse(_required_luxembourg_funds_experience_gap(j,{"jurisdiction_gaps":[]}))
if __name__=="__main__":unittest.main()
