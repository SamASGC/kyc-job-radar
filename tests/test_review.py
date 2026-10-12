from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone

from job_radar.review import build_review_page, review_candidates


class ReviewPageTests(unittest.TestCase):
    def test_old_closed_or_presented_cannot_reappear(self):
        now=datetime.now(timezone.utc).isoformat()
        records=[
            {"company":"ExamplePay", "title":"AML Analyst",
             "url":"https://jobs.ashbyhq.com/examplepay/job123",
             "location":"Spain - Remote", "posted_at":now, "geography_verified":True,
             "reason":"page_200_but_no_visible_apply_action"},
            {"company":"ClosedPay", "title":"KYB Analyst",
             "url":"https://jobs.ashbyhq.com/closedpay/job123",
             "location":"Spain", "posted_at":now, "geography_verified":True,
             "reason":"explicitly_closed"},
            {"company":"OldPay", "title":"CDD Analyst",
             "url":"https://jobs.ashbyhq.com/oldpay/job123",
             "location":"Spain", "posted_at":"2025-03-01", "geography_verified":True,
             "reason":"original_publication_missing_or_older_than_96h"},
            {"company":"SalesPay", "title":"Sales Representative",
             "url":"https://jobs.ashbyhq.com/salespay/job123",
             "location":"Spain", "posted_at":"", "geography_verified":True,
             "reason":"page_200_but_no_visible_apply_action"},
            {"company":"ShownPay", "title":"AML Investigator",
             "url":"https://jobs.ashbyhq.com/shownpay/job123",
             "location":"Spain", "posted_at":now, "geography_verified":True,
             "reason":"page_200_but_no_visible_apply_action"},
        ]
        seen={"old": {"company":"ShownPay", "title":"AML Investigator"}}
        result=review_candidates(records,seen)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["company"],"ExamplePay")

    def test_london_jobs_never_enter_pending_review(self):
        now=datetime.now(timezone.utc).isoformat()
        rows=[
            {"company":"BadFit", "title":"AML Analyst",
             "url":"https://jobs.ashbyhq.com/badfit/123",
             "location":"London United Kingdom", "posted_at":now,
             "geography_verified":False,
             "reason":"page_200_but_no_visible_apply_action"},
        ]
        self.assertEqual(review_candidates(rows),[])

    def test_unverified_labels_not_misrepresented_as_official_alerts(self):
        rows=[{
            "company":"Example <Pay>", "title":"AML & Due Diligence Analyst",
            "url":"https://jobs.ashbyhq.com/examplepay/job123",
            "location":"Spain", "posted_at":"", "geography_verified":True,
            "reason":"page_200_but_no_visible_apply_action",
        }]
        with tempfile.TemporaryDirectory() as temp:
            path=temp+"/review.html"
            self.assertEqual(build_review_page(rows,{},path),1)
            text=open(path,encoding="utf-8").read()
            self.assertIn("NO SON OFERTAS VERIFICADAS NI ALERTAS",text)
            self.assertIn("Example &lt;Pay&gt;",text)
            self.assertNotIn("<Pay>",text)


if __name__ == "__main__":
    unittest.main()
