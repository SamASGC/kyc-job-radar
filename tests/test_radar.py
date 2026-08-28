from __future__ import annotations

import copy
import unittest

from job_radar.models import Job, canonical_url
from job_radar.matching import score_job, parse_age_days
from job_radar.discovery import generic_job_links
from job_radar.scanner import update_state_with_jobs
from job_radar.sources.personio import parse_personio_job_page


PROFILE = {
    "minimum_score": 62,
    "max_post_age_days": 14,
    "stale_after_hours": 72,
    "onsite_hybrid_countries": ["Spain", "Luxembourg", "Switzerland"],
    "remote_scope": "Europe",
}

COMPANIES = [{"name": "TestPay", "sector": "Payments", "aliases": []}]


def strong_job(location: str, title: str = "Senior KYC KYB Analyst") -> Job:
    return Job(
        source="test", source_kind="official ATS", company="TestPay", sector="Payments",
        title=title, location=location,
        description=("Corporate KYB CDD onboarding UBO beneficial ownership complex ownership merchant high risk EDD "
                     "sanctions PEP adverse media. 3 years experience. Transaction monitoring exposure."),
        apply_url="https://example.com/job",
        remote_hint="Remote" if "remote" in location.lower() else "",
    ).finalize()


class RadarTests(unittest.TestCase):
    def test_tracking_query_is_removed(self):
        self.assertEqual(canonical_url("https://jobs.example.com/a/123?utm_source=x#apply"), "https://jobs.example.com/a/123")

    def test_strong_luxembourg_kyb_role_is_accepted(self):
        scored, ok = score_job(strong_job("Luxembourg", "KYB Analyst"), PROFILE, known_company=True)
        self.assertTrue(ok)
        self.assertGreaterEqual(scored.score, 75)
        self.assertIn("transaction monitoring", [x.lower() for x in scored.skills_to_buy])

    def test_spain_hybrid_including_barcelona_is_accepted(self):
        for location in ("Madrid, Spain - Hybrid", "Barcelona, Spain - Hybrid"):
            _, ok = score_job(strong_job(location), PROFILE, known_company=True)
            self.assertTrue(ok, location)

    def test_switzerland_onsite_is_accepted(self):
        _, ok = score_job(strong_job("Zug, Switzerland - On-site"), PROFILE, known_company=True)
        self.assertTrue(ok)

    def test_other_europe_hybrid_is_rejected(self):
        _, ok = score_job(strong_job("Berlin, Germany - Hybrid"), PROFILE, known_company=True)
        self.assertFalse(ok)

    def test_remote_anywhere_in_europe_is_accepted(self):
        for location in ("Germany - Remote", "Malta (Remote)", "Europe - Remote", "Remote EMEA", "Remote Global"):
            _, ok = score_job(strong_job(location), PROFILE, known_company=True)
            self.assertTrue(ok, location)

    def test_non_europe_remote_is_rejected(self):
        for location in ("India - Remote", "Canada - Remote", "South Africa - Remote"):
            _, ok = score_job(strong_job(location), PROFILE, known_company=True)
            self.assertFalse(ok, location)

    def test_peratera_like_role_is_high_fit(self):
        j = Job(
            source="Personio:peratera", source_kind="official ATS", company="Peratera", sector="Payments",
            title="Compliance Analyst (Onboarding & Transaction Monitoring)", location="Remote Global",
            description=("3-4 years KYC KYB onboarding financial crime compliance. End-to-end KYB corporate customers, UBOs, "
                         "complex ownership, customer risk assessments, EDD, PEP sanctions adverse media, periodic reviews, "
                         "transaction monitoring alerts and investigations. EMI payments fintech FX."),
            apply_url="https://peratera.jobs.personio.com/job/2767047", remote_hint="Remote",
        ).finalize()
        scored, ok = score_job(j, PROFILE, known_company=True)
        self.assertTrue(ok)
        self.assertGreaterEqual(scored.score, 90)
        self.assertIn("transaction monitoring", [x.lower() for x in scored.skills_to_buy])

    def test_personio_public_page_fallback_parses_jsonld(self):
        html = '''<html><head><script type="application/ld+json">{
          "@context":"https://schema.org","@type":"JobPosting",
          "title":"Compliance Analyst (Onboarding & Transaction Monitoring)",
          "description":"<p>KYB CDD UBO transaction monitoring</p>",
          "jobLocationType":"TELECOMMUTE",
          "applicantLocationRequirements":{"@type":"Country","name":"Europe"},
          "datePosted":"2026-08-27"
        }</script></head><body><h1>Fallback</h1></body></html>'''
        c={"name":"Peratera","sector":"Payments"}
        j=parse_personio_job_page(html,"https://peratera.jobs.personio.com/job/2767047",c,"peratera")
        self.assertEqual(j.title,"Compliance Analyst (Onboarding & Transaction Monitoring)")
        self.assertIn("Europe",j.location)
        self.assertEqual(j.remote_hint,"Remote")
        self.assertEqual(j.external_id,"2767047")

    def test_irrelevant_engineering_job_is_excluded(self):
        j = Job(source="test", source_kind="official ATS", company="TestPay", sector="Payments",
                title="Software Engineer", location="Madrid, Spain", description="Backend payments platform",
                apply_url="https://example.com/3").finalize()
        _, ok = score_job(j, PROFILE, known_company=True)
        self.assertFalse(ok)

    def test_unix_timestamp_posted_at_is_supported(self):
        age = parse_age_days(1787853327)
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 0)

    def test_sardine_glossary_is_not_a_job(self):
        html = '<a href="https://www.sardine.ai/learn">Fraud and AML glossary</a>'
        self.assertEqual(generic_job_links(html, "https://www.sardine.ai/careers"), [])
        j = Job(source="Career page:Sardine", source_kind="official career page", company="Sardine", sector="Fintech",
                title="Fraud and AML glossary", location="Remote", description="AML fraud KYC transaction monitoring",
                apply_url="https://www.sardine.ai/learn").finalize()
        _, ok = score_job(j, PROFILE, known_company=True)
        self.assertFalse(ok)

    def test_generic_real_compliance_job_link_is_kept(self):
        html = '<a href="/careers/jobs/compliance-analyst">Compliance Analyst</a>'
        links = generic_job_links(html, "https://example.com/careers")
        self.assertEqual(len(links), 1)
        self.assertIn("compliance-analyst", links[0]["url"])


    def test_london_hybrid_payabl_like_role_is_rejected(self):
        j = Job(
            source="Workable:payabl", source_kind="official ATS", company="payabl.", sector="Payments",
            title="AML Officer (Maternity Cover)", location="London, United Kingdom",
            description=("Hybrid role. 5+ years relevant AML Financial Crime experience. Client onboarding KYC CDD EDD, "
                         "transaction monitoring, sanctions screening and SAR preparation. Previous experience working "
                         "within a UK AML and FCA-regulated environment is required."),
            apply_url="https://example.com/payabl-aml", remote_hint="Hybrid",
        ).finalize()
        scored, ok = score_job(j, PROFILE, known_company=True)
        self.assertFalse(ok)
        self.assertLess(scored.score, 80)

    def test_old_out_of_scope_job_is_purged_immediately(self):
        base = {"version": 1, "seen": {}, "jobs": {}, "discovery": {}, "stats": {}, "last_scan": ""}
        j = Job(
            source="Workable:payabl", source_kind="official ATS", company="TestPay", sector="Payments",
            title="AML Officer", location="London, United Kingdom - Hybrid",
            description="5+ years AML KYC CDD EDD transaction monitoring sanctions SAR. FCA regulated experience required.",
            apply_url="https://example.com/payabl-old", remote_hint="Hybrid",
        ).finalize()
        d = j.to_dict(); d["first_seen"] = "2026-08-27T00:00:00+00:00"
        base["jobs"][j.fingerprint] = d
        base["seen"][j.fingerprint] = {"first_seen": d["first_seen"], "company": j.company, "title": j.title, "location": j.location}
        state, stats = update_state_with_jobs(copy.deepcopy(base), [], COMPANIES, PROFILE)
        self.assertNotIn(j.fingerprint, state["jobs"])
        self.assertIn(j.fingerprint, state["seen"])
        self.assertTrue(stats["semantic_changed"])

    def test_five_year_requirement_is_materially_penalized(self):
        j = strong_job("Madrid, Spain - Hybrid", "KYC KYB Analyst")
        j.description = ("Corporate KYB CDD onboarding UBO beneficial ownership complex ownership merchant high risk EDD "
                         "sanctions PEP adverse media. 5+ years experience required. Transaction monitoring exposure.")
        j.fingerprint = ""; j.finalize()
        scored, ok = score_job(j, PROFILE, known_company=True)
        self.assertTrue(ok)
        self.assertLessEqual(scored.score, 80)

    def test_same_offer_does_not_change_state_on_second_scan(self):
        base = {"version": 1, "seen": {}, "jobs": {}, "discovery": {}, "stats": {}, "last_scan": ""}
        j1 = strong_job("Luxembourg", "KYB Analyst")
        j1.apply_url="https://example.com/4"; j1.fingerprint=""; j1.finalize()
        state1, stats1 = update_state_with_jobs(copy.deepcopy(base), [j1], COMPANIES, PROFILE)
        self.assertTrue(stats1["semantic_changed"])
        first_updated = state1["dataset_updated_at"]
        j2 = strong_job("Luxembourg", "KYB Analyst")
        j2.apply_url="https://example.com/4?utm_source=again"; j2.fingerprint=""; j2.finalize()
        state2, stats2 = update_state_with_jobs(copy.deepcopy(state1), [j2], COMPANIES, PROFILE)
        self.assertFalse(stats2["semantic_changed"])
        self.assertEqual(first_updated, state2["dataset_updated_at"])
        self.assertEqual(len(state2["seen"]), 1)
        self.assertEqual(len(state2["jobs"]), 1)


if __name__ == "__main__":
    unittest.main()
