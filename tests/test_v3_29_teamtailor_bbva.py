"""Live-probed Mangopay Teamtailor schema dates and bounded BBVA Workday search."""
import json
import unittest
from datetime import datetime,timedelta,timezone
from html import escape
from pathlib import Path
from urllib.parse import urljoin

from job_radar.sources.teamtailor import parse_teamtailor_job_page, fetch_teamtailor
from job_radar.sources.workday import fetch_workday
from job_radar.v2_quality import verify_application_page, within_new_window

ROOT=Path(__file__).resolve().parents[1]
ORG={"name":"Mangopay","sector":"Payments"}
INDEX="https://career.mangopay.com/jobs"
URL=INDEX+"/8445278-test-risk-officer"


def date(days=2):
    return (datetime.now(timezone.utc)-timedelta(days=days)).replace(microsecond=0).isoformat()


def job_html(*, original=None,modified=None,company="Mangopay",
             same_as="https://career.mangopay.com",apply=True, include_schema=True,
             city="Luxembourg",title="AML/KYC Analyst"):
    original=original if original is not None else date()
    modified=modified if modified is not None else date(days=0)
    obj={"@context":"http://schema.org/","@type":"JobPosting",
         "title":title,"datePosted":original,
         "hiringOrganization":{"@type":"Organization","name":company,"sameAs":same_as},
         "jobLocation":[{"@type":"Place","address":{"addressLocality":city,
                                                       "addressCountry":"LU"}}],
         "description":"&lt;p&gt;Corporate customer due diligence and KYC checks. 2 years relevant experience.&lt;/p&gt;"}
    schema=f'<script type="application/ld+json">{json.dumps(obj)}</script>' if include_schema else ""
    return (f'<html><head><meta property="article:published_time" content="{original}">'
            f'<meta property="article:modified_time" content="{modified}">{schema}</head>'
            '<body><h1>'+title+'</h1>'+('Apply for this job' if apply else 'Vacancy closed')+'</body></html>')


class Response:
    def __init__(self,url,text,status_code=200):
        self.url=url
        self.text=text
        self.status_code=status_code
    def raise_for_status(self):
        if self.status_code>=400:raise RuntimeError(f"HTTP {self.status_code}")


class Http:
    def __init__(self,html):
        self.html=html;self.requests=[]
    async def get(self,url,**kwargs):
        self.requests.append(url)
        if url==INDEX:
            return Response(url, '<a href="/jobs/8445278-test-risk-officer">KYC</a>'
                                '<a href="/jobs/8445278-test-risk-officer">Duplicate</a>'
                                '<a href="https://evil.test/jobs/1123-fake">Fake</a>'
                                '<a href="/jobs">Generic</a>')
        return Response(url,self.html)


class MangopayTeamtailorTests(unittest.IsolatedAsyncioTestCase):
    def test_exact_original_publication_not_last_edit(self):
        stale=date(days=24);today=date(days=0)
        j=parse_teamtailor_job_page(job_html(original=stale,modified=today),URL,ORG)
        self.assertEqual(j.posted_at,stale)
        self.assertFalse(within_new_window(j.posted_at))
        self.assertEqual(j.external_id,"8445278")
        self.assertIn("2 years relevant experience",j.description)
        self.assertEqual(j.location,"Luxembourg, LU")

    def test_missing_or_divergent_original_publication_cannot_alert(self):
        x=job_html(original=date(days=8))
        x=x.replace('property="article:published_time" content="'+date(days=8)+'"',
                    'property="article:published_time" content="'+date(days=0)+'"')
        j=parse_teamtailor_job_page(x,URL,ORG)
        self.assertEqual(j.posted_at,"")
        y=job_html(include_schema=False)
        self.assertIsNone(parse_teamtailor_job_page(y,URL,ORG))

    def test_wrong_employer_or_job_url_is_rejected(self):
        invalid=[
            ("https://career.mangopay.com.evil.test/jobs/8445278-test-risk-officer",job_html()),
            ("https://career.mangopay.com/jobs",job_html()),
            ("https://career.mangopay.com/jobs/8445278-test-risk-officer?tracking=1",job_html()),
            (URL,job_html(company="Another Employer")),
            (URL,job_html(same_as="https://teamtailor.evil.test")),
        ]
        for url,page in invalid:
            with self.subTest(url=url,company=page[:60]):
                self.assertIsNone(parse_teamtailor_job_page(page,url,ORG))

    async def test_recover_individual_real_applicants_no_cross_site_or_duplicate(self):
        h=Http(job_html())
        jobs=await fetch_teamtailor(h,ORG,INDEX)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0].source,"Teamtailor:career.mangopay.com")
        self.assertEqual(h.requests,[INDEX,URL])
        self.assertTrue(await verify_application_page(h,jobs[0]))
        self.assertEqual(jobs[0].verification_reason,"official_live_page_with_apply_action")

    async def test_no_applicant_cta_and_stale_date_deny_alert(self):
        for page in (job_html(apply=False),job_html(original=date(days=15))):
            with self.subTest(page=page[-60:]):
                h=Http(page)
                jobs=await fetch_teamtailor(h,ORG,INDEX)
                self.assertEqual(len(jobs),1)
                self.assertFalse(await verify_application_page(h,jobs[0]))

    async def test_unverified_teamtailor_hostname_fails_closed(self):
        with self.assertRaises(ValueError):
            await fetch_teamtailor(Http(job_html()),ORG,"https://evil.test/jobs")
        with self.assertRaises(ValueError):
            await fetch_teamtailor(Http(job_html()),{"name":"Other Firm"},"https://career.mangopay.com/jobs")


class WorkdaySearchStub:
    def __init__(self):self.terms=[]
    async def post(self,url,**kwargs):
        term=kwargs["json"]["searchText"];self.terms.append(term)
        row={"title":"AML Compliance Analyst" if term=="aml" else "Compliance Officer",
             "locationsText":"Madrid, Spain",
             "externalPath":"/job/Madrid/"+("Shared_JR1" if term=="aml" else "Shared_JR1"),
             "postedOn":"Posted Yesterday"}
        if term=="kyc":
            row["externalPath"]="/job/Madrid/KYC_JR2";row["title"]="KYC Specialist"
        return StubJson({"jobPostings":[row],"total":1})
    async def get(self,url):
        return StubJson({},status_code=404)

class StubJson:
    def __init__(self,d,status_code=200):self.d=d;self.status_code=status_code
    def json(self):return self.d
    def raise_for_status(self):raise ValueError("HTTP "+str(self.status_code))


class BBVATargetedSearch(unittest.IsolatedAsyncioTestCase):
    async def test_overlapping_reqs_dedup_and_no_relative_dates(self):
        h=WorkdaySearchStub()
        jobs=await fetch_workday(h,{"name":"BBVA","sector":"Banking"},
                                 "https://bbva.wd3.myworkdayjobs.com/BBVA",
                                 search_terms=["aml","compliance","kyc"])
        self.assertEqual(len(jobs),2)
        self.assertEqual(h.terms,["aml","compliance","kyc"])
        self.assertTrue(all(j.posted_at=="" for j in jobs))
        self.assertEqual({j.external_id for j in jobs},
                         {"/job/Madrid/Shared_JR1","/job/Madrid/KYC_JR2"})

    def test_both_configured_sources_and_500_firm_identity(self):
        firms=[]
        for p in ("config/companies.json","config/extra_companies.json"):
            firms+=json.loads((ROOT/p).read_text(encoding="utf-8"))
        self.assertEqual(len(firms),500)
        self.assertEqual(len({x["name"] for x in firms}),500)
        self.assertGreaterEqual(sum(bool(c.get("ats")) for c in firms),196)
        index={x["name"]:x for x in firms}
        self.assertEqual(index["Mangopay"]["ats"],
                         [{"kind":"teamtailor","url":INDEX}])
        self.assertEqual(index["BBVA"]["ats"][0]["kind"],"workday")
        self.assertIn("compliance",index["BBVA"]["ats"][0]["search_terms"])

if __name__=="__main__":unittest.main()
