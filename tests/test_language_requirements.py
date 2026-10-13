"""Regression coverage for language hard stops and permanent alert deduplication."""
import copy
import unittest
from datetime import datetime, timezone

from job_radar.models import Job
from job_radar.scanner import update_state_with_jobs
from job_radar.v2_quality import unmet_mandatory_languages, passes_strict_gate


KNOWN = {"Spanish": "Native", "English": "Professional", "French": "Advanced"}
PROFILE = {
    "strict_quality_gate": True, "max_post_age_hours": 96,
    "minimum_score": 0, "stale_after_hours": 24,
    "profile_summary": {"languages": KNOWN},
}


def sample(description):
    return Job(
        source="Teamtailor:luminorbank", source_kind="official ATS",
        company="Luminor", sector="Banca",
        title="Risk Specialist (Transaction Monitoring)",
        location="Vilnius Lithuania - Hybrid",
        description=description,
        apply_url="https://luminorbank.teamtailor.com/jobs/8537846-risk-specialist-transaction-monitoring",
        posted_at=datetime.now(timezone.utc).isoformat(),
        external_id="8537846",
    ).finalize()


class MandatoryLanguageTests(unittest.TestCase):
    def test_luminor_actual_wording_is_a_hard_stop(self):
        j = sample("<p>Fluent Lithuanian and English is required in spoken and written communication.</p>")
        self.assertEqual(unmet_mandatory_languages(j, KNOWN), ["lithuanian"])
        self.assertFalse(passes_strict_gate(j, known_languages=KNOWN))
        import radar  # Import AFTER native_apply test modules are discovered.
        scored, accepted = radar._score_job_with_must_have_gaps(j, PROFILE, True)
        self.assertFalse(accepted)

    def test_english_french_spanish_already_covered(self):
        j = sample("Fluent English and French is required in spoken and written communication.")
        self.assertEqual(unmet_mandatory_languages(j, KNOWN), [])

    def test_other_local_language_and_alternative(self):
        self.assertEqual(unmet_mandatory_languages(
            sample("You must be fluent in Estonian."), KNOWN), ["estonian"])
        self.assertEqual(unmet_mandatory_languages(
            sample("German or French is required."), KNOWN), [])
        self.assertEqual(unmet_mandatory_languages(
            sample("Fluency in German and French is mandatory."), KNOWN), ["german"])
        self.assertEqual(unmet_mandatory_languages(
            sample("German C1 language level required."), KNOWN), ["german"])

    def test_optional_or_nonlinguistic_mentions_do_not_block(self):
        for text in (
            "German is preferred and a plus, not required.",
            "Experience with German clients is required.",
            "Lithuanian market experience is required.",
            "German language knowledge is advantageous.",
            "Lithuanian is not required for this role.",
            "German is optional; English is required.",
        ):
            with self.subTest(text=text):
                self.assertEqual(unmet_mandatory_languages(sample(text), KNOWN), [])

    def test_verified_job_page_language_text_can_block(self):
        j = sample("Analyze AML alerts, escalate suspicious activity.")
        self.assertTrue(passes_strict_gate(j, known_languages=KNOWN))
        j._verified_page_text = "Fluent Lithuanian and English is required."
        self.assertFalse(passes_strict_gate(j, known_languages=KNOWN))
        self.assertNotIn("_verified_page_text", j.to_dict())

    def test_no_profile_languages_does_not_invent_assumptions(self):
        j = sample("Lithuanian is required.")
        self.assertEqual(unmet_mandatory_languages(j, None), [])
        self.assertTrue(passes_strict_gate(j))

    def test_current_bad_match_removed_without_erasing_seen(self):
        j = sample("Fluent Lithuanian and English is required in spoken and written communication.")
        existing = j.to_dict()
        existing["first_seen"] = "2026-10-13T14:12:35+00:00"
        ledger = {j.fingerprint: {
            "company": j.company, "title": j.title,
            "external_id": j.external_id, "source": j.source,
            "first_seen": existing["first_seen"],
        }}
        import radar  # Ensure production scoring is installed before state revalidation.
        state = {"jobs": {j.fingerprint: existing}, "seen": copy.deepcopy(ledger),
                 "discovery": {}, "stats": {}, "strict_v2_baseline": "2026-10-12"}
        updated, stats = update_state_with_jobs(
            state, [j], [{"name": "Luminor", "sector": "Banca"}], PROFILE
        )
        self.assertEqual(updated["jobs"], {})
        self.assertEqual(updated["seen"], ledger)
        self.assertEqual(stats["seen_forever"], 1)
        self.assertEqual(stats["new_this_scan"], 0)


if __name__ == "__main__":
    unittest.main()
