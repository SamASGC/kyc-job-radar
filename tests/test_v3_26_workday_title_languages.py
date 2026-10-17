"""Real Western Union Workday job-title mandatory-language regressions, Oct 2026.

Seven candidate jobs reappeared after real Workday CXS original dates were
read. 'Italian-speaking ... AML' was wrongly accepted although user has
EN/FR/ES only. Do not throw out 'Spanish OR German' or French-speaking roles.
"""
import unittest
from datetime import datetime,timedelta,timezone
from job_radar.models import Job
from job_radar.v2_quality import unmet_mandatory_languages, passes_strict_gate

KNOWN={"Spanish":"Native","English":"Working proficiency","French":"Advanced"}


def job(title: str, description: str = "AML monitoring and due diligence"):
    return Job(
        source="Workday:westernunion/WesternUnionJobs",source_kind="official ATS",
        company="Western Union",sector="Payments",
        title=title,location="LTU - Vilnius",
        description=description,
        apply_url="https://westernunion.wd5.myworkdayjobs.com/WesternUnionJobs/job/LTU---Vilnius/AML-Specialist_JR0132000",
        external_id="/job/LTU---Vilnius/AML-Specialist_JR0132000",
        posted_at=(datetime.now(timezone.utc)-timedelta(hours=5)).isoformat(),
    ).finalize()


class JobTitleLanguageHardStop(unittest.TestCase):
    def test_italian_only_specialist_is_not_user_eligible(self):
        j=job("Italian speaking Specialist, Anti Money Laundering Compliance (Consumer Monitoring and Investigation)",
              "Fluency in English and Italian languages.")
        self.assertEqual(unmet_mandatory_languages(j,KNOWN),["italian"])
        self.assertFalse(passes_strict_gate(j,known_languages=KNOWN))

    def test_french_speaking_specialist_remains_in_scope(self):
        j=job("French speaking Specialist, Anti Money Laundering Compliance (Consumer Monitoring and Investigation)",
              "Fluency in English and French languages. Higher education or equivalent experience preferable.")
        self.assertEqual(unmet_mandatory_languages(j,KNOWN),[])
        self.assertTrue(passes_strict_gate(j,known_languages=KNOWN))

    def test_spanish_or_german_multilingual_specialist_remains_in_scope(self):
        for title in (
            "Specialist, AML Compliance (German or Spanish, Portuguese, Italian Speaker)",
            "Specialist, AML Compliance (Spanish or German, Portuguese, Italian Speaker)"
        ):
            with self.subTest(title=title):
                j=job(title, "Fluency in English and Spanish or German, Portuguese, Italian language.")
                self.assertEqual(unmet_mandatory_languages(j,KNOWN),[])
                self.assertTrue(passes_strict_gate(j,known_languages=KNOWN))

    def test_unsupported_foreign_language_has_clear_hard_stop(self):
        for term in ("Italian-speaking", "German speaking", "Japanese speaker",
                     "Korean language", "Fluent Mandarin", "Bilingual German"):
            with self.subTest(term=term):
                j=job(f"{term} AML/KYC Analyst")
                self.assertNotEqual(unmet_mandatory_languages(j,KNOWN),[])

    def test_multiple_mandatory_languages_and_geo_mentions(self):
        self.assertEqual(unmet_mandatory_languages(
            job("German and Spanish speaking AML Analyst"),KNOWN),["german"])
        self.assertEqual(unmet_mandatory_languages(
            job("Compliance Analyst - German Market", "Risk-based periodic due diligence"),KNOWN),[])

if __name__=="__main__":unittest.main()
