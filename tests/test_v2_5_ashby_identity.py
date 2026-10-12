"""Ashby public APIs often omit id: exact jobUrl is the fallback identity."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from job_radar.models import Job
from job_radar.native_apply import native_application_evidence
from job_radar.sources.ashby import _public_posting_id, fetch_ashby
from job_radar.v2_quality import verify_application_page


class Resp:
    def __init__(self, data=None, text="<html><div id='app'></div></html>"):
        self._data = data
        self.text = text
        self.status_code = 200

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class Http:
    def __init__(self, data):
        self.data = data
        self.urls = []

    async def get(self, url):
        self.urls.append(url)
        if "api.ashbyhq.com" in url:
            return Resp(self.data)
        return Resp()


class PublicAshbyIdentityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.url = "https://jobs.ashbyhq.com/apron/d01a6c72-4a00-4000-b000-000000000001"
        self.apply = self.url + "/application"
        self.item = {
            "title": "KYB Analyst", "location": "Spain - Remote",
            "descriptionPlain": "AML corporate KYC EDD",
            "publishedAt": datetime.now(timezone.utc).isoformat(),
            "isListed": True, "jobUrl": self.url, "applyUrl": self.apply,
        }

    async def test_extract_id_from_provider_job_url_without_id(self):
        self.assertEqual(
            _public_posting_id(self.item, "apron"),
            "d01a6c72-4a00-4000-b000-000000000001",
        )
        http = Http({"jobs": [self.item]})
        jobs = await fetch_ashby(http, {"name": "Apron", "sector": "Payments"}, "apron")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].external_id, _public_posting_id(self.item, "apron"))
        self.assertTrue(await verify_application_page(http, jobs[0]))
        self.assertEqual(jobs[0].verification_reason, "native_ats_application_confirmed")

    async def test_other_job_url_cannot_borrow_same_title_application(self):
        j = Job(
            source="Ashby:apron", source_kind="official ATS",
            company="Apron", sector="Payments", title="KYB Analyst",
            location="Spain - Remote", description="AML investigations",
            apply_url=self.url, external_id=_public_posting_id(self.item,"apron"),
            posted_at=datetime.now(timezone.utc).isoformat(),
        ).finalize()
        malicious = {**self.item, "jobUrl":
                     "https://jobs.ashbyhq.com/apron/ffffffff-ffff-ffff-ffff-ffffffffffff"}
        self.assertFalse(await native_application_evidence(
            Http({"jobs": [malicious]}), j
        ))

    async def test_spoofed_hostname_or_another_board_gives_no_requisition_id(self):
        for url in (
            "https://fake.example/apron/d01a6c72",
            "https://jobs.ashbyhq.com/other/d01a6c72",
            "http://jobs.ashbyhq.com/apron/d01a6c72",
            "https://jobs.ashbyhq.com/apron/apply",
        ):
            with self.subTest(url=url):
                self.assertEqual(_public_posting_id({"jobUrl": url}, "apron"), "")

    async def test_explicit_mismatch_id_rejected_even_with_correct_url(self):
        j = Job(
            source="Ashby:apron", source_kind="official ATS", company="Apron",
            sector="Payments", title="KYB Analyst", location="Spain - Remote",
            description="AML", apply_url=self.url, external_id=_public_posting_id(self.item,"apron"),
            posted_at=datetime.now(timezone.utc).isoformat(),
        ).finalize()
        different = {**self.item, "id": "not-this-job"}
        self.assertFalse(await native_application_evidence(
            Http({"jobs": [different]}), j
        ))


if __name__ == "__main__":
    unittest.main()
