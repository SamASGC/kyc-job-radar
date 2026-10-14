"""v3.17: test page-2 recovery and IQ-EQ company ownership without fake timestamps."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT=Path(__file__).resolve().parents[1]
IQEQ="https://jobs.smartrecruiters.com/IQEQ"

class IQEQProviderV317(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=[]
        for f in ("config/companies.json","config/extra_companies.json"):
            cls.rows+=json.loads((ROOT/f).read_text(encoding="utf-8"))
        cls.by={x["name"]:x for x in cls.rows}

    def test_500_unique_182_configured_feeds(self):
        self.assertEqual(len(self.rows),500)
        self.assertEqual(len({x["name"].casefold() for x in self.rows}),500)
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.rows),182)

    def test_iqeq_belongs_to_company_not_semiconductor_iqe(self):
        c=self.by["IQ-EQ"]
        self.assertEqual(c["ats"],[{"kind":"smartrecruiters","slug":"iqeq"}])
        self.assertEqual(c["careers_url"],IQEQ)
        self.assertEqual(c["verification_level"],"official_ats_live_probe_passed")
        self.assertIn("iqeq.com/careers/vacancies/",c["origin"])
        self.assertIn("SmartRecruiters",c["origin"])

    def test_original_96h_and_seen_ledger(self):
        from job_radar.v2_quality import original_posted_at
        self.assertIsNone(original_posted_at("Posted Today"))
        import yaml
        cfg=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(cfg["strict_quality_gate"])
        self.assertEqual(cfg["max_post_age_hours"],96)
        self.assertEqual(cfg["remote_scope"],"Spain")
        state=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]),306)

class IQEQPages(unittest.IsolatedAsyncioTestCase):
    async def test_second_page_recovers_jobs_but_filters_other_companies(self):
        from job_radar.sources.smartrecruiters import fetch_smartrecruiters
        def post(i,company="IQ-EQ",ident="IQEQ"):
            return {"id":str(i),"name":"KYC Analyst","releasedDate":"2026-10-13T12:31:00Z",
                    "company":{"name":company,"identifier":ident},
                    "location":{"city":"Luxembourg","country":"lu"}}
        first=[post(i) for i in range(100)]
        second=[post(i) for i in range(100,125)]+[post(5000,"IQE","IQE")]
        class Response:
            status_code=200
            def __init__(self,data):self.payload=data
            def raise_for_status(self):pass
            def json(self):return self.payload
        class HTTP:
            def __init__(self):self.pages=[];self.details=[]
            async def get(self,url):
                if "/postings?" in url:
                    off=int(parse_qs(urlsplit(url).query).get("offset",["0"])[0])
                    self.pages.append(off)
                    return Response({"totalFound":126,"content":first if off==0 else second})
                ident=url.rsplit("/",1)[-1]
                self.details.append(ident)
                return Response({"name":"KYC Analyst","releasedDate":"2026-10-13T12:31:00Z",
                    "jobAdUrl":f"{IQEQ}/{ident}-kyc-analyst",
                    "location":{"city":"Luxembourg","country":"lu"}})
        http=HTTP()
        rows=await fetch_smartrecruiters(http,{"name":"IQ-EQ","sector":"Fintech"},"iqeq")
        self.assertEqual(http.pages,[0,100])
        self.assertEqual(len(rows),125)
        self.assertEqual(len(http.details),125)
        self.assertEqual(len({r.external_id for r in rows}),125)
        self.assertTrue(all(r.company=="IQ-EQ" and r.source_kind=="official ATS" for r in rows))
        self.assertTrue(all(r.posted_at=="2026-10-13T12:31:00Z" for r in rows))
        self.assertTrue(all("jobs.smartrecruiters.com/IQEQ/" in r.apply_url for r in rows))
        self.assertNotIn("5000",{r.external_id for r in rows})

    async def test_repeated_first_page_terminates_without_duplicates(self):
        from job_radar.sources.smartrecruiters import fetch_smartrecruiters
        first=[{"id":str(i),"name":"Compliance Analyst",
                "company":{"identifier":"IQEQ"},
                "releasedDate":"2026-10-13T12:00:00Z",
                "applyUrl":f"{IQEQ}/{i}-compliance-analyst"} for i in range(100)]
        class Response:
            status_code=200
            def raise_for_status(self):pass
            def json(self):return {"content":first}
        class Http:
            def __init__(self):self.pages=0
            async def get(self,url):
                if "/postings?" in url:self.pages+=1
                return Response()
        h=Http()
        rows=await fetch_smartrecruiters(h,{"name":"IQ-EQ","sector":"Fintech"},"iqeq")
        self.assertEqual(len(rows),100)
        self.assertEqual(h.pages,2)

if __name__=="__main__":
    unittest.main()
