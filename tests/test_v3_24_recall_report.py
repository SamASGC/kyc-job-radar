"""Non-alert read-only recall report cannot present uncertain jobs as verified."""
import json
import tempfile
import unittest
from pathlib import Path
from job_radar.recall_report import select_recall_examples, build_recall_report

class RecallReportTests(unittest.TestCase):
    def test_only_relevant_geo_compatible_verified_urls_get_sampled(self):
        audit={"original_date_missing":2,
          "rejected_examples":[
             {"company":"Example Bank","title":"Compliance Monitoring Analyst","location":"Madrid, Spain - Hybrid",
              "url":"https://example.com/jobs/123","geography_verified":True,"reason":"original_publication_missing_or_older_than_96h","posted_at":""},
             {"company":"Wrong","title":"Software Engineer","location":"Madrid, Spain",
              "url":"https://example.com/jobs/888","geography_verified":True,"reason":"unknown"},
             {"company":"Wrong","title":"AML Analyst","location":"London - Hybrid",
              "url":"https://example.com/jobs/999","geography_verified":False,"reason":"unknown"},
             {"company":"Wrong","title":"AML Analyst","location":"Madrid - Hybrid",
              "url":"javascript:alert('hello')","geography_verified":True,"reason":"unknown"},
          ]}
        rows=select_recall_examples(audit)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["company"],"Example Bank")
        self.assertFalse(rows[0]["original_date_proven"])

    def test_html_and_json_are_read_only_and_escaped(self):
        audit={"raw_total":300,"official_apply_page_verified":1,
               "verified_score_rejected":1,
               "verified_score_rejects":[{"company":"Bank <Audit>","title":"Compliance Analyst",
                 "location":"Madrid & remote", "url":"https://example.com/job?x=1&y=2",
                 "posted_at":"","geography_verified":True,"reason":"<script>","score":48}]}
        with tempfile.TemporaryDirectory() as td:
            report=build_recall_report(audit,out_dir=td)
            body=(Path(td)/"recall.html").read_text(encoding="utf-8")
            data=json.loads((Path(td)/"recall.json").read_text(encoding="utf-8"))
            self.assertEqual(report["funnel"]["raw_total"],300)
            self.assertEqual(data["funnel"]["verified_score_rejected"],1)
            self.assertIn("NO SON OFERTAS VERIFICADAS NI ALERTAS",body)
            self.assertIn("&lt;Audit&gt;",body)
            self.assertNotIn("<script>",body)
            self.assertIn("https://example.com/job?x=1&amp;y=2",body)
            self.assertEqual(len(data["examples"]),1)
            self.assertFalse(data["examples"][0]["original_date_proven"])

    def test_duplicate_report_links_collapsed(self):
        row={"company":"Bank","title":"KYB Analyst","location":"Vilnius Lithuania",
             "url":"https://official.example/jobs/1","posted_at":"",
             "geography_verified":True,"reason":"unverifiable"}
        a={"rejected_examples":[row,row.copy()]}
        self.assertEqual(len(select_recall_examples(a)),1)

if __name__=="__main__":unittest.main()
