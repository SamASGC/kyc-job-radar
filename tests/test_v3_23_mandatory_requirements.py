"""Regressions from actual Luminor October 2026 false-positive candidate.

The official job demanded 5-7 years of Compliance Assurance and one of
Latvian/Lithuanian/Estonian. The old scorer read a separate *benefit*
('after 1 year at the company') as 1 year of required experience, and the
language gate did not recognize 'What We Expect' qualification bullets.
"""
import copy
import unittest
from datetime import datetime, timezone
from job_radar.models import Job
from job_radar.experience_requirements import required_experience_years, hard_experience_gap
from job_radar.v2_quality import unmet_mandatory_languages, passes_strict_gate
from job_radar.scanner import update_state_with_jobs

KNOWN = {"Spanish": "Native", "English": "Professional", "French": "Advanced"}
PROFILE = {
    "strict_quality_gate": True,
    "exclude_management_roles": True,
    "minimum_score": 62,
    "max_post_age_hours": 96,
    "max_post_age_days": 4,
    "stale_after_hours": 24,
    "remote_scope": "Spain",
    "onsite_hybrid_countries": ["Spain", "Switzerland", "Luxembourg", "Lithuania", "Estonia"],
    "profile_summary": {"languages": KNOWN},
}

REAL_REQUIREMENTS = (
    "<h4>What We Expect:</h4><ul>"
    "<li><p>Higher education in Internal Audit, Law, Economics, Business Management, Finance, or related field</p></li>"
    "<li><p>Experience of at least 5-7 years in compliance assurance activities</p></li>"
    "<li><p>Advanced English language proficiency in spoken and written communication and excellent Latvian, Lithuanian or Estonian language skills</p></li>"
    "<li><p>Preferred certifications in Internal Audit, Sanctions and/or AML area</p></li>"
    "</ul>"
    "<h4>Why You Will Love Working Here</h4><ul>"
    "<li><p>More vacation is available to employees who have been in the company for 1 year</p></li>"
    "<li><p>Flexible working hours, Hybrid work</p></li></ul>"
)

def job(description=REAL_REQUIREMENTS, title="Control Expert (Compliance)"):
    return Job(
        source="Career page:Luminor", source_kind="official career page",
        company="Luminor", sector="Banca", title=title,
        location="Vilnius, LT - Hybrid",
        description=description,
        external_id="https://luminorbank.teamtailor.com/jobs/8549351-control-expert-compliance",
        apply_url="https://luminorbank.teamtailor.com/jobs/8549351-control-expert-compliance",
        posted_at=datetime.now(timezone.utc).isoformat(),
    ).finalize()

class MandatoryRequirementRegression(unittest.TestCase):
    def test_real_luminor_years_ignore_employee_benefit(self):
        self.assertEqual(required_experience_years(REAL_REQUIREMENTS), 5)
        self.assertTrue(hard_experience_gap(REAL_REQUIREMENTS))

    def test_real_luminor_lithuanian_latvian_estonian_are_mandatory(self):
        self.assertEqual(
            unmet_mandatory_languages(job(), KNOWN),
            ["estonian", "latvian", "lithuanian"],
        )
        self.assertFalse(passes_strict_gate(job(), known_languages=KNOWN))

    def test_real_luminor_rejected_by_actual_production_matcher(self):
        import radar
        j, accepted=radar._score_job_with_must_have_gaps(job(), PROFILE, True)
        self.assertEqual(j.company,"Luminor")
        self.assertFalse(accepted)

    def test_removes_existing_dashboard_false_positive_preserving_lifetime_ledger(self):
        import radar
        j=job()
        old=j.to_dict()
        old["first_seen"]="2026-10-15T07:39:44+00:00"
        seen={j.fingerprint: {
            "company": j.company, "title": j.title, "source": j.source,
            "external_id": j.external_id, "first_seen": old["first_seen"]
        }}
        state={"jobs": {j.fingerprint: old}, "seen":copy.deepcopy(seen),
               "discovery":{}, "stats":{}, "strict_v2_baseline":"2026-10-01T00:00:00+00:00"}
        updated,stats=update_state_with_jobs(
            state,[],[{"name":"Luminor","sector":"Banca"}],PROFILE
        )
        self.assertNotIn(j.fingerprint, updated["jobs"])
        self.assertEqual(updated["seen"],seen)
        self.assertEqual(stats["new_this_scan"],0)

    def test_valid_three_years_and_supported_languages_remain_eligible(self):
        valid=(
            "<h4>Requirements</h4><ul>"
            "<li>At least 3 years of corporate KYB / CDD experience</li>"
            "<li>Fluent French or German language skills</li>"
            "<li>Spanish and English proficiency</li></ul>"
            "<h4>Benefits</h4><ul><li>After 6 years at our company, extra vacation.</li></ul>"
        )
        self.assertEqual(required_experience_years(valid),3)
        self.assertFalse(hard_experience_gap(valid))
        self.assertEqual(unmet_mandatory_languages(job(valid),KNOWN),[])
        self.assertTrue(passes_strict_gate(job(valid),known_languages=KNOWN))

    def test_optional_local_language_or_five_years_is_not_mandatory(self):
        desc=(
            "<h4>What We Expect</h4><ul>"
            "<li>At least 3 years of KYB review experience</li>"
            "<li>German language is preferred and a plus, not required</li>"
            "<li>5 years of sanctions investigations experience is desirable</li>"
            "</ul>"
        )
        self.assertEqual(required_experience_years(desc),3)
        self.assertEqual(unmet_mandatory_languages(job(desc),KNOWN),[])

    def test_required_six_years_is_out_of_scope(self):
        desc="<h4>Requirements</h4><ul><li>6+ years of AML experience</li></ul>"
        self.assertEqual(required_experience_years(desc),6)
        self.assertFalse(passes_strict_gate(job(desc),known_languages=KNOWN))

    def test_language_mentions_in_company_benefits_are_not_requirements(self):
        desc=(
            "<h4>What You Will Do</h4><li>Support German clients with compliance</li>"
            "<h4>Why Work Here</h4><li>Optional Lithuanian language training</li>"
        )
        self.assertEqual(unmet_mandatory_languages(job(desc),KNOWN),[])

if __name__=="__main__":
    unittest.main()
