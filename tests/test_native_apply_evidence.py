"""Regression cases for conservative ATS-native application verification."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from job_radar.models import Job
from job_radar.v2_quality import (
    _native_application_url, verify_application_page,
)


class Response:
    def __init__(self, url: str, text: str, status_code: int = 200):
        self.url = url
        self.text = text
        self.status_code = status_code


class Http:
    def __init__(self, overrides=None):
        self.overrides = overrides or {}
        self.visited = []

    async def get(self, url):
        self.visited.append(url)
        return self.overrides.get(url, Response(
            url, '<main id="root"><h1>Financial Crime Analyst</h1></main>'
        ))


def job(source="Lever:paytm", age_hours=1, apply_url=None, native=None):
    base = "https://jobs.lever.co/paytm/abc123"
    return Job(
        source=source, source_kind="official ATS", company="Paytm",
        sector="Payments", title="Financial Crime Analyst",
        location="Luxembourg", description="CDD EDD AML investigations",
        apply_url=apply_url or base, external_id="abc123",
        posted_at=(datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat(),
        application_api_url=(
            "https://jobs.lever.co/paytm/abc123/apply" if native is None else native
        ),
    ).finalize()


class NativeApplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_job_plus_exact_native_apply_route_with_no_static_cta(self):
        j = job()
        http = Http()
        self.assertTrue(await verify_application_page(http, j))
        self.assertEqual(
            j.verification_reason, "official_ats_native_application_route_verified"
        )
        self.assertEqual(len(http.visited), 2)

    async def test_native_link_cannot_jump_to_other_requisition_or_employer(self):
        for target in (
            "https://jobs.lever.co/paytm/another-id/apply",
            "https://jobs.lever.co/another-employer/abc123/apply",
            "https://attacker.example/paytm/abc123/apply",
            "http://jobs.lever.co/paytm/abc123/apply",
            "https://jobs.lever.co/paytm/apply",
        ):
            with self.subTest(target=target):
                j = job(native=target)
                self.assertEqual(_native_application_url(j), "")
                self.assertFalse(await verify_application_page(Http(), j))

    async def test_redirect_to_generic_careers_or_closed_apply_route_fails(self):
        j = job()
        url = j.application_api_url
        for response in (
            Response("https://jobs.lever.co/paytm", "Apply now"),
            Response(url, "<p>Applications are closed.</p>"),
            Response(url, "Temporary error", 503),
        ):
            with self.subTest(response=response.text):
                self.assertFalse(await verify_application_page(
                    Http({url: response}), j
                ))

    async def test_html_search_login_and_newsletter_forms_are_not_evidence(self):
        j = job(native="")
        html = (
            '<form action="/search"><input name="q"></form>'
            '<form action="/subscribe"><input type="email" name="email"></form>'
        )
        self.assertFalse(await verify_application_page(
            Http({j.apply_url: Response(j.apply_url, html)}), j
        ))
        self.assertEqual(j.verification_reason, "page_200_but_no_verified_apply_action")

    async def test_actual_resume_application_form_is_evidence(self):
        j = job(native="")
        html = ('<form action="/jobs/abc123/submit">'
                '<input type="email" name="email">'
                '<input type="file" name="cv"></form>')
        self.assertTrue(await verify_application_page(
            Http({j.apply_url: Response(j.apply_url, html)}), j
        ))

    async def test_aria_and_localized_apply_control(self):
        j = job(native="")
        html = '<button aria-label="Postuler maintenant"></button>'
        self.assertTrue(await verify_application_page(
            Http({j.apply_url: Response(j.apply_url, html)}), j
        ))

    async def test_old_original_date_cannot_be_rescued_by_native_route(self):
        j = job(age_hours=120)
        self.assertFalse(await verify_application_page(Http(), j))
        self.assertEqual(
            j.verification_reason, "original_publication_missing_or_older_than_96h"
        )

    async def test_serialization_keeps_provider_link_without_dedupe_change(self):
        j = job()
        rec = j.to_dict()
        restored = Job.from_dict(rec)
        self.assertEqual(j.fingerprint, restored.fingerprint)
        self.assertEqual(j.application_api_url, restored.application_api_url)


if __name__ == "__main__":
    unittest.main()
