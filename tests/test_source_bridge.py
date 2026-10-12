from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta

from job_radar.models import Job
from job_radar.source_bridge import ats_target_from_url, discover_aggregator_ats


def lead(company, url, title="KYB Analyst", *, kind="aggregator"):
    return Job(
        source="Test Feed", source_kind=kind,
        company=company, sector="Payments", title=title,
        location="Spain - Remote", description="KYB UBO due diligence",
        apply_url=url, posted_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    ).finalize()


class ATSBridgeTests(unittest.TestCase):
    def test_recognize_only_real_official_ats_job_patterns(self):
        valid = {
            "https://job-boards.greenhouse.io/fictionalfintech/jobs/12345": ("greenhouse", "fictionalfintech"),
            "https://job-boards.eu.greenhouse.io/fictionalfintech/jobs/12345": ("greenhouse", "fictionalfintech"),
            "https://jobs.lever.co/fictionalfintech/123abc": ("lever", "fictionalfintech"),
            "https://jobs.eu.lever.co/fictionalfintech/123abc": ("lever_eu", "fictionalfintech"),
            "https://jobs.ashbyhq.com/fictionalfintech/123abc": ("ashby", "fictionalfintech"),
            "https://apply.workable.com/fictionalfintech/j/123abc": ("workable", "fictionalfintech"),
            "https://fictionalfintech.jobs.personio.com/job/12345": ("personio", "fictionalfintech"),
            "https://fictionalfintech.recruitee.com/o/kyb-analyst": ("recruitee", "fictionalfintech"),
            "https://jobs.smartrecruiters.com/fictionalfintech/12345": ("smartrecruiters", "fictionalfintech"),
        }
        for url, (kind, slug) in valid.items():
            with self.subTest(url=url):
                self.assertEqual(ats_target_from_url(url), {"kind": kind, "slug": slug})
        for url in ("https://fake.ashbyhq.com/payments/1234",
                    "https://jobs.ashbyhq.com/company",
                    "https://example.com/open?url=https://jobs.ashbyhq.com/fictionalfintech/j",
                    "http://jobs.lever.co/fictionalfintech/1234",
                    "https://job-boards.greenhouse.io/company",
                    "https://evil.com/",
                    ""):
            self.assertIsNone(ats_target_from_url(url), url)

    def test_dedup_unknown_ats_boards_while_ignoring_known(self):
        url = "https://jobs.ashbyhq.com/fictionalfintech/job1234"
        items = [
            lead("KnownPay", "https://jobs.ashbyhq.com/knownpay/job123"),
            lead("NewFintech", url),
            lead("NewFintech", "https://jobs.ashbyhq.com/fictionalfintech/job567"),
            lead("No ATS", "https://unknown.example.com/careers/abc"),
            lead("AnotherFintech", "https://jobs.lever.co/anotherfintech/job123"),
        ]
        found = discover_aggregator_ats(items, {"KnownPay"})
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0][0]["name"], "NewFintech")
        self.assertEqual(found[0][1], {"kind": "ashby", "slug": "fictionalfintech"})
        self.assertEqual(found[1][1], {"kind": "lever", "slug": "anotherfintech"})

    def test_no_aggregator_result_treated_as_verified_listing(self):
        self.assertFalse(discover_aggregator_ats([
            lead("NewFintech", "https://jobs.lever.co/test/job123", kind="official ATS")
        ], set()))


if __name__ == "__main__":
    unittest.main()
