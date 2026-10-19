"""v3.27: direct source integrity & nested Wise SmartRecruiters requisitions."""
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, parse_qs
from job_radar.sources.smartrecruiters import fetch_smartrecruiters
from job_radar.production_guard import check_release
from job_radar.v2_quality import original_posted_at

NOW=datetime.now(timezone.utc)
def iso(days=0):return (NOW-timedelta(days=days)).isoformat()

class Response:
    status_code=200
    def __init__(self,data): self.data=data
    def json(self): return self.data
    def raise_for_status(self): pass

class Http:
    def __init__(self,rows,details):
        self.rows=rows;self.details=details;self.detail_calls=[]
    async def get(self,url):
        if "/postings/" in url:
            jid=url.split("/postings/",1)[1]
            self.detail_calls.append(jid)
            return Response(self.details[jid])
        query=parse_qs(urlsplit(url).query)
        offset=int(query.get("offset",["0"])[0])
        return Response({"content":self.rows[offset:offset+100],"totalFound":len(self.rows)})

def row(jid,name,date=None,country="es"):
    return {"id":str(jid),"name":name,
            "releasedDate":date or iso(),
            "company":{"identifier":"Wise","name":"Wise"},
            "location":{"city":"Madrid","country":country,"fullLocation":"Madrid, Spain"}}

def detail(jid,name,active=True):
    return {"id":str(jid),"name":name,"releasedDate":iso(),
            "company":{"identifier":"Wise"},
            "location":{"city":"Madrid","country":"es","remote":False},
            "active":active,"visibility":"PUBLIC",
            "applyUrl":f"https://jobs.smartrecruiters.com/Wise/{jid}-analyst",
            "jobAd":{"sections":{
               "jobDescription":{"text":"<p>Review complex corporate customers</p>"},
               "qualifications":{"text":"<ul><li>2 years of AML/KYC expertise; English required</li></ul>"},
            }}}

class WiseATSParserTests(unittest.IsolatedAsyncioTestCase):
    async def test_nested_sections_preserve_actual_requirements(self):
        h=Http([row("111","AML KYC Analyst")],{"111":detail("111","AML KYC Analyst")})
        found=await fetch_smartrecruiters(h,{"name":"Wise","sector":"Payments"},"Wise")
        self.assertEqual(len(found),1)
        self.assertIn("Review complex corporate customers",found[0].description)
        self.assertIn("2 years of AML/KYC expertise",found[0].description)
        self.assertEqual(found[0].external_id,"111")
        self.assertIsNotNone(original_posted_at(found[0].posted_at))

    async def test_dont_publish_closed_or_private_job_details(self):
        h=Http([row("1","KYC Analyst")],{"1":detail("1","KYC Analyst",active=False)})
        self.assertEqual(await fetch_smartrecruiters(h,{"name":"Wise"},"Wise"),[])

    async def test_large_board_enriches_only_current_relevant_jobs(self):
        old=[row(i,f"Sales Executive {i}",iso(35),"hu") for i in range(181)]
        target=row("recent","AML/KYC Analyst",iso(),"es")
        data=old+[target]
        h=Http(data,{"recent":detail("recent","AML/KYC Analyst")})
        found=await fetch_smartrecruiters(h,{"name":"Wise"},"Wise")
        self.assertEqual(len(found),1)
        self.assertEqual(found[0].external_id,"recent")
        self.assertEqual(h.detail_calls,["recent"])

class IntegrityGuardTests(unittest.TestCase):
    def setUp(self):
        self.firms=[{"name":"Qonto","ats":[{"kind":"lever","slug":"qonto"}]},
                    {"name":"Wise","ats":[{"kind":"smartrecruiters","slug":"Wise"}]}]
        self.sources={"sources":[{"company":f["name"],"origin_class":"direct"} for f in self.firms],
                      "direct_configured":2,"ats_explicit":2,"direct_not_checked":0,
                      "direct_with_records":2,"direct_errors":0,"direct_reachable_zero":0}
        self.job={"apply_url":"https://jobs.lever.co/qonto/1","apply_verified_at":iso(),"posted_at":iso()}
        self.state={"seen":{"old":{},"new":{}},"jobs":{"new":self.job}}
        self.prior={"seen":{"old":{}}}
        self.kw={"expected_direct":2,"min_ats":2,"min_with_records":1,"max_direct_errors":1}
    def test_valid_two_employers_pass(self):
        r=check_release(self.firms,self.sources,self.state,self.prior,**self.kw)
        self.assertTrue(r["passed"])
    def test_lost_historical_fingerprint_rejects_release(self):
        self.state["seen"].pop("old")
        with self.assertRaisesRegex(ValueError,"lost"):
            check_release(self.firms,self.sources,self.state,self.prior,**self.kw)
    def test_catastrophic_coverage_cannot_deploy(self):
        self.sources.update(direct_with_records=0,direct_errors=2)
        with self.assertRaises(ValueError):
            check_release(self.firms,self.sources,self.state,self.prior,**self.kw)
    def test_broken_applicant_url_or_date_cannot_deploy(self):
        self.job["apply_url"]="http://example.com/apply"
        self.job["posted_at"]="Posted Yesterday"
        with self.assertRaises(ValueError):
            check_release(self.firms,self.sources,self.state,self.prior,**self.kw)
    def test_ats_connector_disappeared_cannot_deploy(self):
        self.firms[1].pop("ats")
        with self.assertRaisesRegex(ValueError,"ATS source"):
            check_release(self.firms,self.sources,self.state,self.prior,**self.kw)
if __name__=="__main__":unittest.main()
