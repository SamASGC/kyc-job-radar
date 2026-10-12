from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

import radar
from job_radar.models import Job
from job_radar.v2_quality import (
    original_posted_at, within_new_window, location_allowed,
    official_active_listing, passes_strict_gate, previously_presented,
)
from job_radar.scanner import update_state_with_jobs


def job(*, location="Spain - Remote", posted_at=None, source_kind="official ATS",
        external_id="123", title="KYB Analyst", company="TestPay"):
    return Job(
        source="Ashby:test", source_kind=source_kind, company=company,
        sector="Payments", title=title, location=location,
        description=(
            "Corporate KYB and KYC, high-risk CDD, EDD, beneficial ownership, "
            "UBO, onboarding, sanctions, complex merchant investigations. "
            "Requires 2 years in regulated payments."
        ), apply_url="https://jobs.ashbyhq.com/test/123",
        external_id=external_id, posted_at=posted_at or datetime.now(timezone.utc).isoformat(),
        remote_hint="Remote" if "remote" in location.lower() else "",
    ).finalize()


STRICT = {
    "strict_quality_gate": True, "max_post_age_hours": 96, "max_post_age_days": 4,
    "minimum_score": 50, "onsite_hybrid_countries":
    ["Spain", "Luxembourg", "Switzerland", "Estonia", "Lithuania"],
    "remote_scope": "Spain",
}


class V2AdmissionTests(unittest.TestCase):
    def test_real_absolute_dates(self):
        now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        self.assertTrue(within_new_window("2026-10-09T12:00:00Z", now=now))
        self.assertTrue(within_new_window("2026-10-08T12:00:00Z", now=now))
        self.assertFalse(within_new_window("2026-10-08T11:59:59Z", now=now))
        self.assertFalse(within_new_window("", now=now))
        self.assertFalse(within_new_window("Posted today", now=now))
        self.assertFalse(within_new_window("10 days ago", now=now))
        self.assertFalse(within_new_window("2026-10-14", now=now))
        self.assertIsNotNone(original_posted_at(int(now.timestamp() * 1000)))

    def test_remote_is_spain_only(self):
        for allowed in ("Spain - Remote", "Canary Islands, Remote", "Remote - Malta, Spain, Poland"):
            self.assertTrue(location_allowed(job(location=allowed)), allowed)
        for rejected in ("Germany - Remote", "Remote EMEA", "Remote Global", "Europe - Remote", "Barcelona - Hybrid"):
            self.assertFalse(location_allowed(job(location=rejected)), rejected)

    def test_spain_remote_is_rejected_when_canary_islands_excluded(self):
        excluded = job(location="Spain - Remote")
        excluded.description += " Employees may work from Spain, excluding Canary Islands."
        self.assertFalse(location_allowed(excluded))
        mainland = job(location="Spain - Remote")
        mainland.description += " This position is mainland Spain only."
        self.assertFalse(location_allowed(mainland))

    def test_ats_work_style_precedes_employer_generic_benefits(self):
        from job_radar.matching import detect_mode
        remote = job(location="Spain - Remote")
        remote.description = (
            "Our company provides hybrid work flexibility. This vacancy is "
            "fully remote from Spain."
        )
        self.assertEqual(detect_mode(remote), "Remoto")
        self.assertTrue(location_allowed(remote))
        onsite = job(location="Madrid Spain - On-site")
        onsite.description = "Support remote customers and collaborate with remote teams."
        self.assertEqual(detect_mode(onsite), "Presencial")
        hybrid = job(location="Vilnius Lithuania - Hybrid")
        hybrid.description = "The company runs fully remote teams too."
        self.assertEqual(detect_mode(hybrid), "Híbrido")
        self.assertTrue(location_allowed(hybrid))

    def test_hybrid_relocation_scope(self):
        for allowed in ("Tallinn Estonia - Hybrid", "Vilnius Lithuania - Hybrid",
                        "Luxembourg - Hybrid", "Zurich Switzerland - On-site",
                        "Madrid Spain - Hybrid"):
            self.assertTrue(location_allowed(job(location=allowed)), allowed)
        for rejected in ("Barcelona Spain - Hybrid", "Berlin Germany - Hybrid", "Malta - Hybrid"):
            self.assertFalse(location_allowed(job(location=rejected)), rejected)

    def test_real_employer_job_specific_career_pages_are_eligible(self):
        from job_radar.models import canonical_url
        self.assertEqual(
            canonical_url(
                "https://employer.example/careers/?gh_jid=8675309&utm_source=linkedin"
            ),
            "https://employer.example/careers?gh_jid=8675309",
        )
        page_job = job(source_kind="official career page")
        page_job.apply_url = canonical_url(
            "https://employer.example/careers?gh_jid=8675309&utm_campaign=advert"
        )
        self.assertTrue(official_active_listing(page_job))
        page_job.apply_url = "https://employer.example/careers"
        self.assertFalse(official_active_listing(page_job))
        page_job.apply_url = "https://employer.example/careers/jobs/analyst-123"
        self.assertTrue(official_active_listing(page_job))
        self.assertFalse(official_active_listing(job(source_kind="aggregator")))

    def test_only_current_official_ats(self):
        self.assertTrue(official_active_listing(job()))
        self.assertFalse(official_active_listing(job(source_kind="aggregator")))
        j = job()
        j.apply_url = "https://example.com/careers"
        self.assertFalse(official_active_listing(j))

    def test_old_closed_and_unknown_not_reported(self):
        self.assertFalse(passes_strict_gate(job(posted_at="2026-09-12")))
        self.assertFalse(passes_strict_gate(job(source_kind="aggregator")))
        self.assertFalse(passes_strict_gate(job(location="Remote EMEA")))
        self.assertFalse(passes_strict_gate(job(posted_at="posted today")))
        self.assertTrue(passes_strict_gate(job()))

    def test_distinct_ats_requisitions_have_distinct_fingerprints(self):
        a = job(company="TestPay", title="KYB Analyst", external_id="123")
        b = job(company="TestPay", title="KYB Analyst", external_id="456")
        self.assertNotEqual(a.fingerprint, b.fingerprint)
        repost = job(company="TestPay", title="KYB Analyst - French", external_id="123")
        self.assertEqual(a.fingerprint, repost.fingerprint)

    def test_already_presented_never_realerted(self):
        j = job(title="Senior KYB Analyst", external_id="128")
        old = {"first_seen": "2026-10-08", "company": "TestPay",
               "title": "Senior KYB Analyst", "location": "Lithuania"}
        self.assertTrue(previously_presented(j, {"old": old}))
        self.assertFalse(previously_presented(j, {"old": {**old, "external_id": "129"}}))
        self.assertTrue(previously_presented(j, {"old": {**old, "external_id": "128"}}))

    def test_strict_scoring_overrides_high_fit(self):
        old = job(posted_at=(datetime.now(timezone.utc) - timedelta(days=8)).isoformat())
        _, ok = radar._score_job_with_must_have_gaps(old, STRICT, known_company=True)
        self.assertFalse(ok)
        recent = job()
        _, ok = radar._score_job_with_must_have_gaps(recent, STRICT, known_company=True)
        self.assertTrue(ok)

    def test_acquired_company_redirects_canonical_ats_owner(self):
        from job_radar.scanner import declared_ats_owners
        companies = [
            {"name": "Equals Money", "sector": "Payments",
             "ats": [{"kind": "recruitee", "slug": "equalsmoney"}]},
            {"name": "Railsr", "sector": "Payments"},
        ]
        owners = declared_ats_owners(companies)
        self.assertEqual(owners[("recruitee", "equalsmoney")]["name"], "Equals Money")
        j = job(company="Railsr", title="Regulatory Compliance Analyst")
        j.source = "Recruitee:equalsmoney"
        j.source_kind = "official ATS"
        j.external_id = "eq123"
        j.fingerprint = ""
        j.finalize()
        state, _ = update_state_with_jobs(
            {"seen": {}, "jobs": {}, "discovery": {}, "stats": {}},
            [j], companies,
            {"minimum_score": 0, "max_post_age_days": 4,
             "onsite_hybrid_countries": ["Spain"], "remote_scope": "Europe"},
        )
        for rec in state["jobs"].values():
            self.assertEqual(rec["company"], "Equals Money")

    def test_existing_seen_ledger_survives_migration(self):
        seen = {"legacy-id": {"company": "TestPay", "title": "KYB Analyst", "location": "Spain"}}
        base = {"seen": copy.deepcopy(seen), "jobs": {}, "discovery": {}, "stats": {}}
        state, stats = update_state_with_jobs(base, [job()], [{"name": "TestPay", "sector": "Payments"}], STRICT)
        self.assertEqual(state["seen"], seen)
        self.assertEqual(state["jobs"], {})
        self.assertEqual(stats["new_this_scan"], 0)



class V2LiveATSChecks(unittest.IsolatedAsyncioTestCase):
    async def test_original_date_recovered_from_matching_official_schema(self):
        from job_radar.v2_quality import verify_application_page
        from datetime import datetime, timezone
        latest = datetime.now(timezone.utc).isoformat()
        html = ('<html><script type="application/ld+json">'
                '{"@context":"https://schema.org","@type":"JobPosting",'
                '"title":"KYB Analyst","datePosted":"' + latest + '"}'
                '</script><h1>KYB Analyst</h1><button>Apply now</button></html>')
        class Response:
            status_code = 200
            text = html
        class Http:
            async def get(self, url):
                return Response()
        j = job()
        j.posted_at = ""
        self.assertTrue(await verify_application_page(Http(), j))
        self.assertEqual(j.posted_at, latest)

    async def test_europe_remote_with_structured_spain_requirements_passes(self):
        from job_radar.v2_quality import verify_application_page, could_verify_spain_from_job_page
        latest = datetime.now(timezone.utc).isoformat()
        class HTTP:
            async def get(self, url):
                class Response:
                    status_code = 200
                p=Response()
                p.text = ('<html><script type="application/ld+json">'
                          '{"@type":"JobPosting","title":"KYB Analyst",'
                          '"jobLocationType":"TELECOMMUTE",'
                          '"applicantLocationRequirements":[{"@type":"Country","name":"Spain"}],'
                          '"datePosted":"' + latest + '"}</script>'
                          '<h1>KYB Analyst</h1><button>Apply now</button></html>')
                return p
        j = job(location="Remote EMEA")
        j.posted_at = ""
        self.assertTrue(could_verify_spain_from_job_page(j))
        self.assertTrue(await verify_application_page(HTTP(), j))
        self.assertTrue(location_allowed(j))

    async def test_no_spain_structured_requirements_stays_excluded(self):
        from job_radar.v2_quality import verify_application_page, location_allowed
        latest = datetime.now(timezone.utc).isoformat()
        class HTTP:
            async def get(self, url):
                class Response:
                    status_code=200
                p=Response()
                p.text=('<script type="application/ld+json">'
                        '{"@type":"JobPosting","title":"KYB Analyst",'
                        '"applicantLocationRequirements":{"name":"Germany"},'
                        '"datePosted":"' + latest + '"}</script>'
                        '<button>Apply now</button>')
                return p
        j=job(location="Remote EMEA")
        self.assertTrue(await verify_application_page(HTTP(),j))
        self.assertFalse(location_allowed(j))

    async def test_wrong_job_date_or_closed_form_does_not_pass(self):
        from job_radar.v2_quality import verify_application_page
        latest = datetime.now(timezone.utc).isoformat()
        class Http:
            def __init__(self, page):
                self.page = page
            async def get(self, url):
                class Response:
                    status_code = 200
                r = Response()
                r.text = self.page
                return r
        old_date = "2026-01-01T00:00:00Z"
        j = job()
        j.posted_at = ""
        wrong = ('<script type="application/ld+json">'
                 '{"@type":"JobPosting","title":"Software Engineer",'
                 '"datePosted":"' + latest + '"}</script><button>Apply now</button>')
        self.assertFalse(await verify_application_page(Http(wrong), j))
        old = ('<script type="application/ld+json">'
               '{"@type":"JobPosting","title":"KYB Analyst",'
               '"datePosted":"' + old_date + '"}</script><button>Apply now</button>')
        self.assertFalse(await verify_application_page(Http(old), job()))
        closed = '<p>No longer accepting applications</p><button>Apply now</button>'
        self.assertFalse(await verify_application_page(Http(closed), job()))


if __name__ == "__main__":
    unittest.main()
