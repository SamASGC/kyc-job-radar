"""Confirmed financial-sector direct-source batch and Workday localized URLs."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from job_radar.models import Job
from job_radar.native_apply import native_application_evidence
from job_radar.sources.workday import fetch_workday


EXPECTED = {
    "Flagright", "Notabene", "Merkle Science", "Regnology", "Julius Baer",
    "Union Bancaire Privée", "Banque de Luxembourg", "Partners Group",
    "Edmond de Rothschild", "Sift", "Resistant AI", "CUBE", "Tazapay",
    "Riskified", "BNP Paribas", "Amundi", "Apex Group",
}
NATIVE = {
    "Flagright": "ashby", "Notabene": "ashby",
    "Merkle Science": "lever", "Regnology": "personio",
    "Julius Baer": "workday",
}


class FinancialSourceBatchTests(unittest.TestCase):
    def test_250_unique_direct_employers_with_documented_targets(self):
        root = Path(__file__).resolve().parents[1]
        companies = []
        for path in ("config/companies.json", "config/extra_companies.json"):
            companies.extend(json.loads((root / path).read_text(encoding="utf-8")))
        names = [str(c["name"]).casefold() for c in companies]
        self.assertGreaterEqual(len(names), 250)
        self.assertEqual(len(names), len(set(names)), "Employer duplicated across source files")
        by_name = {c["name"]: c for c in companies}
        self.assertTrue(EXPECTED.issubset(by_name))
        for name in EXPECTED:
            c = by_name[name]
            self.assertTrue(c["careers_url"].startswith("https://"), name)
            self.assertTrue(c.get("enabled"), name)
            self.assertTrue(c.get("specialism"), name)
            if name in NATIVE:
                self.assertEqual(c["ats"][0]["kind"], NATIVE[name])
                self.assertEqual(c["verification_level"], "official_ats_board_link_verified")
            elif name == "Riskified":
                # v3.9: its official employer-owned Greenhouse board is proven live.
                self.assertEqual(c.get("ats"), [{"kind":"greenhouse","slug":"riskified"}])
                self.assertEqual(c["verification_level"], "official_ats_live_probe_passed")
                self.assertIn("riskified", c["origin"].casefold())
            else:
                self.assertNotIn("ats", c)
                self.assertEqual(c["verification_level"],
                                 "official_careers_url_not_necessarily_api")


class _Response:
    status_code = 200

    def json(self):
        return {"jobPostings": [
            {"title": "Financial Crime Analyst", "locationsText": "Switzerland",
             "externalPath": "/job/Zurich/Financial-Crime-Analyst_123",
             "postedOn": "2026-10-12"},
        ]}


class _Http:
    def __init__(self):
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response()


class WorkdayLocalizedBoardTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_julius_baer_locale_url_uses_real_site(self):
        url = "https://juliusbaer.wd3.myworkdayjobs.com/en-US/External"
        http = _Http()
        jobs = await fetch_workday(http, {"name": "Julius Baer", "sector": "Banca"}, url)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(
            http.calls[0][0],
            "https://juliusbaer.wd3.myworkdayjobs.com/wday/cxs/juliusbaer/External/jobs",
        )
        self.assertEqual(
            jobs[0].apply_url,
            "https://juliusbaer.wd3.myworkdayjobs.com/en-US/External/job/Zurich/Financial-Crime-Analyst_123",
        )

    async def test_original_workday_url_without_locale_still_works(self):
        http = _Http()
        await fetch_workday(
            http, {"name": "Corpay", "sector": "Payments"},
            "https://corpay.wd103.myworkdayjobs.com/Ext_001",
        )
        self.assertEqual(http.calls[0][0],
                         "https://corpay.wd103.myworkdayjobs.com/wday/cxs/corpay/Ext_001/jobs")

    async def test_dotted_ashby_board_requires_matching_company_application(self):
        j = Job(source="Ashby:flagright.com",source_kind="official ATS",
                company="Flagright",sector="Fintech",title="AML Analyst",
                location="Spain - Remote",description="AML",
                apply_url="https://jobs.ashbyhq.com/flagright.com/req-123",
                external_id="req-123",posted_at="2026-10-12").finalize()
        class Response:
            status_code = 200
            def json(self):
                return {"jobs":[{"id":"req-123","title":"AML Analyst",
                                 "isListed":True,
                                 "applyUrl":"https://jobs.ashbyhq.com/flagright.com/req-123/application"}]}
        class H:
            async def get(self, url, **kwargs):
                return Response()
        self.assertTrue(await native_application_evidence(H(), j))


if __name__ == "__main__":
    unittest.main()
