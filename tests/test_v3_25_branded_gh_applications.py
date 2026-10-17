"""V3.25: real-probed 2026-10-17 employer-branded Greenhouse candidates.

Greenhouse public job detail {id,title,questions} is job-specific evidence.
First-party URL patterns were observed live for SumUp and Stripe in
workflow run 39046282355. A different ID, company or missing proof fails.
"""
import unittest
from datetime import datetime, timedelta, timezone

from job_radar.models import Job
from job_radar.native_apply import native_application_evidence
from job_radar.v2_quality import verify_application_page


class Response:
    status_code=200
    text="<html><h1>Job description</h1><div id='app'></div></html>"
    def __init__(self, data=None, text=None):
        self.data=data
        if text is not None:
            self.text=text
    def json(self):
        return self.data

class Http:
    def __init__(self, detail, page=None):
        self.detail=detail
        self.page=page or Response()
        self.urls=[]
    async def get(self, url):
        self.urls.append(url)
        return Response(self.detail) if "boards-api.greenhouse.io/" in url else self.page

def job(company, id_, url, *, title="Compliance Analyst", hours=4, board=None):
    j=Job(source="Greenhouse:"+ (board or company.lower()),
        source_kind="official ATS",company=company, sector="Payments",
        title=title,location="Madrid, Spain - Hybrid",
        description="Corporate AML and KYB risk assessments",
        apply_url=url, external_id=str(id_),
        posted_at=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat())
    return j.finalize()


class BrandedGreenhouseTests(unittest.IsolatedAsyncioTestCase):
    async def test_sumup_employer_hosted_job_verified_with_exact_id_and_title(self):
        j=job("SumUp","8745286002",
              "https://sumup.com/careers/positions/8745286002?gh_jid=8745286002",
              title="Backend Engineer - Merchant Risk Intelligence")
        h=Http({"id":8745286002,"title":j.title,"questions":[{"label":"Resume"}]})
        self.assertTrue(await verify_application_page(h,j))
        self.assertEqual(j.verification_reason,"native_ats_application_confirmed")
        self.assertEqual(len(h.urls),2)
        self.assertEqual(h.urls[-1],
            "https://boards-api.greenhouse.io/v1/boards/sumup/jobs/8745286002?questions=true")

    async def test_stripe_employer_hosted_job_verified_when_id_title_match(self):
        j=job("Stripe","8181024","https://stripe.com/jobs/search?gh_jid=8181024",
              title="Account Executive Product - Fraud & Risk ")
        h=Http({"id":8181024,"title":j.title,"questions":[{"label":"First name"}]})
        self.assertTrue(await verify_application_page(h,j))
        self.assertEqual(j.verification_reason,"native_ats_application_confirmed")

    async def test_ebury_standard_greenhouse_eu_url_kept(self):
        j=job("Ebury","4997066101",
              "https://job-boards.eu.greenhouse.io/ebury/jobs/4997066101",
              title="Compliance Officer & DMLRO")
        h=Http({"id":4997066101,"title":j.title,"questions":[]})
        self.assertTrue(await verify_application_page(h,j))

    async def test_no_brand_squatting_or_wrong_id_can_be_verified(self):
        invalid=[
            ("SumUp","sumup","https://sumup.com.evil.test/careers/positions/123?gh_jid=123"),
            ("SumUp","sumup","https://sumup.com/careers/positions/999?gh_jid=123"),
            ("SumUp","sumup","https://sumup.com/careers/positions/123?gh_jid=999"),
            ("SumUp","sumup","https://sumup.com/careers/positions/123"),
            ("Stripe","stripe","https://stripe.com/jobs/search"),
            ("Stripe","stripe","https://stripe.com/jobs/search?gh_jid=999"),
            ("Stripe","stripe","https://stripe.com/jobs/other?gh_jid=123"),
            ("Other Bank","stripe","https://stripe.com/jobs/search?gh_jid=123"),
            ("Stripe","otherboard","https://stripe.com/jobs/search?gh_jid=123"),
            ("Ebury","ebury","https://job-boards.eu.greenhouse.io/otherbank/jobs/123"),
            ("Ebury","ebury","https://job-boards.eu.greenhouse.io/ebury"),
        ]
        for company,board,url in invalid:
            with self.subTest(url=url,company=company,board=board):
                j=job(company,"123",url,board=board)
                self.assertFalse(await native_application_evidence(
                    Http({"id":123,"title":j.title,"questions":[{"label":"Resume"}]}),j))

    async def test_wrong_job_record_and_missing_form_never_pass(self):
        j=job("Stripe","123","https://stripe.com/jobs/search?gh_jid=123")
        for detail in (
            {"id":123,"title":"Unrelated Software Engineer","questions":[{"label":"Resume"}]},
            {"id":999,"title":"Compliance Analyst","questions":[{"label":"Resume"}]},
            {"id":123,"title":"Compliance Analyst"},
        ):
            with self.subTest(detail=detail):
                self.assertFalse(await native_application_evidence(Http(detail),j))

    async def test_old_and_explicitly_closed_are_still_rejected(self):
        url="https://stripe.com/jobs/search?gh_jid=123"
        detail={"id":123,"title":"Compliance Analyst","questions":[{"label":"Resume"}]}
        j=job("Stripe","123",url,hours=110)
        self.assertFalse(await verify_application_page(Http(detail),j))
        self.assertEqual(j.verification_reason,"original_publication_missing_or_older_than_96h")
        recent=job("Stripe","123",url)
        self.assertFalse(await verify_application_page(Http(
            detail,page=Response(text="<p>No longer accepting applications</p>")
        ),recent))
        self.assertEqual(recent.verification_reason,"explicitly_closed")

if __name__=="__main__": unittest.main()
