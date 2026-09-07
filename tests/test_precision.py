from __future__ import annotations

import unittest

import radar
from job_radar.models import Job
from job_radar.precision import contains_term, contains_any


PROFILE = {
    "minimum_score": 62,
    "max_post_age_days": 14,
    "stale_after_hours": 72,
    "onsite_hybrid_countries": ["Spain", "Luxembourg", "Switzerland", "Estonia", "Czechia", "Malta"],
    "remote_scope": "Europe",
    "hands_on_gaps": [
        "Transaction Monitoring", "AML investigations", "SAR/STR drafting",
        "Regulatory reporting", "Sanctions investigations", "Source of Funds (SoF)", "Source of Wealth (SoW)",
    ],
    "jurisdiction_gaps": [],
}


class PrecisionTests(unittest.TestCase):
    def test_short_acronyms_need_real_token_boundaries(self):
        self.assertFalse(contains_term("seamless customer support", "aml"))
        self.assertFalse(contains_term("embedded finance platform", "edd"))
        self.assertFalse(contains_any("strong strategic support", ["sar", "str"]))
        self.assertTrue(contains_term("perform AML investigations", "aml"))
        self.assertTrue(contains_term("complete EDD reviews", "edd"))
        self.assertTrue(contains_term("draft STR reports", "str"))

    def test_marqeta_production_support_engineer_is_rejected(self):
        j = Job(
            source="Ashby:marqeta",
            source_kind="official ATS",
            company="Marqeta",
            sector="Payments",
            title="Production Support Engineer II - UK",
            location="United Kingdom - Remote",
            description=(
                "As a Production Support Engineer at Marqeta, ensure seamless operation of our embedded finance products. "
                "Provide technical support, diagnose root causes, work with Engineering, monitor transaction volume, "
                "use Linux, SQL, APIs, Python and logging tools. 2-3 years Technical Support experience."
            ),
            apply_url="https://example.com/marqeta-support",
            remote_hint="Remote",
        ).finalize()
        scored, ok = radar._score_job_with_must_have_gaps(j, PROFILE, known_company=True)
        self.assertFalse(ok)
        self.assertNotIn("SAR/STR drafting", scored.skills_to_buy or [])

    def test_generic_title_with_real_kyc_jd_can_still_pass(self):
        j = Job(
            source="test",
            source_kind="official ATS",
            company="Test Bank",
            sector="Banca",
            title="Client Review Analyst",
            location="Luxembourg",
            description=(
                "RESPONSIBILITIES: Perform customer due diligence, EDD, UBO verification, PEP and sanctions screening, "
                "adverse media reviews and periodic reviews. REQUIREMENTS: 2 years of KYC/CDD experience."
            ),
            apply_url="https://example.com/client-review",
        ).finalize()
        _, ok = radar._score_job_with_must_have_gaps(j, PROFILE, known_company=True)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
