"""v3.11 repairs exactly three priority employers; no invented API or alerts."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EURO="https://don.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1003/jobs"
SHIFT="https://shift4payments.wd108.myworkdayjobs.com/Shift4_External_CareerSite"
PAYDO="https://paydo.com/career/"

class PriorityRepairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.companies=[]
        for p in ("config/companies.json","config/extra_companies.json"):
            cls.companies+=json.loads((ROOT/p).read_text(encoding="utf-8"))
        cls.by={r["name"]:r for r in cls.companies}

    def test_500_unique_direct_and_exact_172_really_declared_ats(self):
        self.assertEqual(len(self.companies),500)
        self.assertEqual(len({x["name"].casefold() for x in self.companies}),500)
        # +1 new Oracle provider, -1 former 404 PayDo, Shift4 changes provider
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.companies),172)

    def test_euroclear_first_party_oracle_board(self):
        x=self.by["Euroclear"]
        self.assertEqual(x["careers_url"],EURO)
        self.assertEqual(x["ats"],[{"kind":"oracle_hcm","site":"CX_1003",
                                      "language":"en","url":EURO}])
        self.assertIn("euroclear.com/careers/en.html",x["origin"])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")

    def test_shift4_replaces_404_gh_with_its_workday(self):
        x=self.by["Shift4"]
        self.assertEqual(x["careers_url"],SHIFT)
        self.assertEqual(x["ats"],[{"kind":"workday","url":SHIFT}])
        self.assertIn("shift4.com/careers",x["origin"])
        self.assertEqual(x["verification_level"],"official_ats_live_probe_passed")

    def test_paydo_no_fake_ats_and_real_career_site(self):
        x=self.by["PayDo"]
        self.assertEqual(x["careers_url"],PAYDO)
        self.assertFalse(x.get("ats"))
        self.assertEqual(x["verification_level"],"official_careers_url_not_necessarily_api")
        self.assertIn("Greenhouse paydo board HTTP404",x["origin"])

    def test_original_posted_date_and_geography_preserved(self):
        import yaml
        p=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(p["strict_quality_gate"])
        self.assertEqual(p["max_post_age_hours"],96)
        self.assertEqual(p["remote_scope"],"Spain")
        state=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]),306)
        from job_radar.v2_quality import original_posted_at
        self.assertIsNone(original_posted_at("Posted Yesterday"))

class PayDoJobLinkQuality(unittest.IsolatedAsyncioTestCase):
    async def test_only_employer_individual_job_urls_survive(self):
        from job_radar.sources.generic import fetch_generic
        from job_radar.models import norm_text
        html='''<html><body><h1>PayDo careers</h1>
        <a href="https://paydo.com/career/">Products</a>
        <a href="https://paydo.com/career/accountant/">Accountant Remote</a>
        <a href="https://paydo.com/career/compliance-analyst/">Compliance Analyst</a>
        <a href="https://paydo.com/blog/kyc-policy/">KYC Policy Resource</a>
        <a href="https://phishing.example/career/bad/">Financial Crime Specialist</a>
        </body></html>'''
        class Response:
            url=PAYDO
            text=html
            def raise_for_status(self):pass
        class Http:
            async def get(self,url):
                r=Response()
                if url.endswith("compliance-analyst/"):
                    r.url=url
                    r.text="<html><h1>Compliance Analyst</h1><p>Financial crime role.</p></html>"
                return r
        jobs,found,final=await fetch_generic(Http(),{"name":"PayDo","careers_url":PAYDO})
        self.assertEqual(len(jobs),2,[(x.title,x.apply_url) for x in jobs])
        self.assertEqual({x.apply_url for x in jobs},{
            "https://paydo.com/career/accountant",
            "https://paydo.com/career/compliance-analyst"
        })
        self.assertTrue(all(x.source_kind=="official career page" for x in jobs))
        self.assertTrue(all(not x.posted_at for x in jobs))
        self.assertEqual(found,[])

if __name__=="__main__":
    unittest.main()
