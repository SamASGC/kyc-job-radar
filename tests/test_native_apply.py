from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from job_radar.models import Job
from job_radar.native_apply import native_application_evidence
from job_radar.scanner import fetch_target
from job_radar.v2_quality import verify_application_page


class Response:
    def __init__(self, data=None, text="<html><h1>Job details</h1><div id='root'></div></html>",
                 status_code=200):
        self.data = data
        self.text = text
        self.status_code = status_code

    def json(self):
        return self.data


class StubHttp:
    def __init__(self, ats_data, page=None, ats_status=200):
        self.ats_data = ats_data
        self.page = page or Response()
        self.ats_status = ats_status
        self.urls = []

    async def get(self, url, **kwargs):
        self.urls.append(url)
        if url.startswith(("https://boards-api.greenhouse.io/",
                           "https://api.lever.co/", "https://api.eu.lever.co/",
                           "https://api.ashbyhq.com/")):
            return Response(self.ats_data, status_code=self.ats_status)
        return self.page


def make_job(family="Greenhouse", *, age_hours=2):
    url = {
        "Greenhouse": "https://job-boards.greenhouse.io/payco/jobs/123",
        "Lever": "https://jobs.lever.co/payco/123",
        "Ashby": "https://jobs.ashbyhq.com/payco/123",
    }[family]
    return Job(
        source=f"{family}:payco", source_kind="official ATS",
        company="Payco", sector="Payments", title="KYB Analyst",
        location="Spain - Remote", description="Corporate KYB investigations",
        apply_url=url, external_id="123",
        posted_at=(datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat(),
    ).finalize()


class NativeApplyChecks(unittest.IsolatedAsyncioTestCase):
    async def test_greenhouse_job_specific_questions_resolve_js_only_page(self):
        http = StubHttp({"id": 123, "title": "KYB Analyst", "questions": [
            {"label": "Resume", "fields": [{"type": "input_file"}]},
        ]})
        j = make_job("Greenhouse")
        self.assertTrue(await verify_application_page(http, j))
        self.assertEqual(j.verification_reason, "native_ats_application_confirmed")
        self.assertEqual(len(http.urls), 2)
        self.assertIn("jobs/123?questions=true", http.urls[1])

    async def test_greenhouse_wrong_requisition_or_no_form_is_not_confirmed(self):
        for data in (
            {"id": 999, "title": "KYB Analyst", "questions": []},
            {"id": 123, "title": "Software Engineer", "questions": []},
            {"id": 123, "title": "KYB Analyst"},
        ):
            with self.subTest(data=data):
                j = make_job()
                self.assertFalse(await verify_application_page(StubHttp(data), j))
                self.assertEqual(j.verification_reason,
                                 "page_200_but_no_visible_apply_action")

    async def test_lever_exact_public_posting_and_apply_url(self):
        data = {"id": "123", "text": "KYB Analyst",
                "applyUrl": "https://jobs.lever.co/payco/123/apply"}
        http = StubHttp(data)
        j = make_job("Lever")
        self.assertTrue(await verify_application_page(http, j))
        self.assertEqual(j.verification_reason, "native_ats_application_confirmed")
        self.assertIn("/v0/postings/payco/123", http.urls[-1])

    async def test_lever_mismatched_apply_link_cannot_cross_company(self):
        data = {"id": "123", "text": "KYB Analyst",
                "applyUrl": "https://jobs.lever.co/anotherbank/123/apply"}
        self.assertFalse(await native_application_evidence(StubHttp(data), make_job("Lever")))

    async def test_ashby_listed_posting_with_real_apply_url(self):
        data = {"jobs": [{"id": "123", "title": "KYB Analyst",
                          "isListed": True,
                          "applyUrl": "https://jobs.ashbyhq.com/payco/123/application"}]}
        self.assertTrue(await verify_application_page(StubHttp(data), make_job("Ashby")))

    async def test_ashby_unlisted_or_mismatched_board_fails(self):
        for row in (
            {"id": "123", "title": "KYB Analyst", "isListed": False,
             "applyUrl": "https://jobs.ashbyhq.com/payco/123/application"},
            {"id": "123", "title": "KYB Analyst", "isListed": True,
             "applyUrl": "https://jobs.ashbyhq.com/another/123/application"},
        ):
            with self.subTest(row=row):
                self.assertFalse(await native_application_evidence(
                    StubHttp({"jobs": [row]}), make_job("Ashby")
                ))

    async def test_old_job_and_explicit_closed_page_never_override(self):
        data = {"id": 123, "title": "KYB Analyst", "questions": []}
        old = make_job(age_hours=120)
        self.assertFalse(await verify_application_page(StubHttp(data), old))
        self.assertEqual(old.verification_reason,
                         "original_publication_missing_or_older_than_96h")
        closed = make_job()
        http = StubHttp(data, page=Response(text="<p>No longer accepting applications</p>"))
        self.assertFalse(await verify_application_page(http, closed))
        self.assertEqual(closed.verification_reason, "explicitly_closed")
        self.assertEqual(len(http.urls), 1)

    async def test_unknown_ats_and_provider_error_do_not_pass(self):
        j = make_job()
        j.source = "Career page:payco"
        self.assertFalse(await verify_application_page(
            StubHttp({"id": 123, "title": "KYB Analyst", "questions": []}), j
        ))
        j = make_job()
        self.assertFalse(await verify_application_page(
            StubHttp({}, ats_status=404), j
        ))

    async def test_cookie_login_and_newsletter_forms_are_not_apply_proof(self):
        bogus_pages = [
            "<form id='cookie-consent'><input name='cookie-choice'>"
            "<button type='submit'>Accept cookies</button></form>",
            "<form action='/login' method='post'><input type='email' name='email'>"
            "<input type='password' name='password'><button>Sign in</button></form>",
            "<form action='/subscribe' method='post'><input type='email' name='email'>"
            "<button>Subscribe</button></form>",
            "<form action='/apply/123'><input type='email' name='email'>"
            "<input name='first_name'></form>",
        ]
        for fragment in bogus_pages:
            with self.subTest(fragment=fragment):
                j = make_job()
                page = Response(text="<html><h1>KYB Analyst</h1>" + fragment + "</html>")
                # No matching applicant questions from the employer's public
                # ATS API; a generic form cannot substitute for an application.
                http = StubHttp({"id": 123, "title": "KYB Analyst"}, page=page)
                self.assertFalse(await verify_application_page(http, j))
                self.assertEqual(j.verification_reason,
                                 "page_200_but_no_visible_apply_action")

    async def test_applicant_specific_form_with_submit_is_evidence(self):
        samples = [
            "<form method='post' action='/apply/123'>"
            "<input name='first_name'><input type='email' name='email'>"
            "<button type='submit'>Send</button></form>",
            "<form method='post'>"
            "<input type='file' name='resume'><button type='submit'>Send</button></form>",
        ]
        for fragment in samples:
            with self.subTest(fragment=fragment):
                j = make_job()
                page = Response(text="<html><h1>KYB Analyst</h1>" + fragment + "</html>")
                http = StubHttp({}, page=page, ats_status=404)
                self.assertTrue(await verify_application_page(http, j))
                self.assertEqual(j.verification_reason,
                                 "official_live_page_with_apply_action")
                self.assertEqual(len(http.urls), 1)

    async def test_oracle_configured_adapter_reachable_from_dispatcher(self):
        company = {"name": "Amex", "careers_url": "https://example.org/careers"}
        target = {"kind": "oracle_hcm", "url": "https://example.org/careers",
                  "site": "CX_1"}
        with patch("job_radar.scanner.fetch_oracle_hcm",
                   new_callable=AsyncMock, return_value=[]) as mocked:
            result = await fetch_target(None, company, target)
            self.assertEqual(result, [])
            mocked.assert_awaited_once_with(None, company, target)


if __name__ == "__main__":
    unittest.main()
