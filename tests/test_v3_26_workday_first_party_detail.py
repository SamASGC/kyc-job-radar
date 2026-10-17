"""Regression for 2026-10-17 *real* first-party PayPal/Entrust/NT/Worldpay CXS.

Live trace: Github Actions 39065161854 + 39065230044.
All four provide startDate (actual absolute posting date), canApply and
posted flags, jobPostingId, exact title, full jobDescription on the CXS detail.
The list's Posted Yesterday / absent postedOn must not generate fake dates.
"""
import unittest
from datetime import datetime, timedelta, timezone

from job_radar.models import Job
from job_radar.sources.workday import fetch_workday, possibly_recent_workday_listing
from job_radar.workday_detail import (
    workday_board, workday_detail_endpoint, workday_exact_job,
    workday_original_date, native_workday_application_evidence,
)
from job_radar.v2_quality import verify_application_page, within_new_window


BASE="https://ntrs.wd1.myworkdayjobs.com/northerntrust"
EXT="/job/Luxembourg/AML-Consultant--Compliance_R154518"
URL=BASE+EXT
TITLE="AML Consultant, Compliance"
TODAY=datetime.now(timezone.utc).date().isoformat()


def workday_job(*, date=TODAY, url=URL, source="Workday:ntrs/northerntrust", external_id=EXT):
    return Job(
        source=source,source_kind="official ATS",
        company="Northern Trust",sector="Banking",title=TITLE,
        location="Luxembourg - Hybrid",
        description="Conduct AML due diligence reviews",
        apply_url=url,external_id=external_id,posted_at=date,
    ).finalize()


def detail(*, title=TITLE, posting_id="AML-Consultant--Compliance_R154518",
           start=TODAY, posted=True, can_apply=True):
    return {"jobPostingInfo":{
        "id":"a1bc3d45f6000000",
        "title":title,"jobPostingId":posting_id,"jobReqId":"R154518",
        "startDate":start,"posted":posted,"canApply":can_apply,
        "jobDescription":"<h3>Requirements</h3><ul><li>3 years of corporate AML, KYC, EDD and periodic review experience</li></ul>",
        "location":"Luxembourg",
    }}


class Response:
    def __init__(self, data, status=200, body="<html><h1>AML Consultant, Compliance</h1><div id='app'></div></html>"):
        self.status_code=status;self.data=data;self.text=body
    def json(self):return self.data
    def raise_for_status(self):
        if self.status_code>=400:raise RuntimeError(f"HTTP {self.status_code}")


class Stub:
    def __init__(self, *, obj=None, listings=None):
        self.detail=obj if obj is not None else detail()
        self.listings=listings if listings is not None else [{
            "title":TITLE,"locationsText":"Luxembourg - Hybrid",
            "externalPath":EXT,"postedOn":"Posted Yesterday",
        }]
        self.requests=[]
    async def post(self,url,**kwargs):
        self.requests.append(("POST",url,kwargs))
        return Response({"jobPostings":self.listings,"total":len(self.listings)})
    async def get(self,url,**kwargs):
        self.requests.append(("GET",url,kwargs))
        if "/wday/cxs/" in url:return Response(self.detail)
        return Response({},body="<html><h1>AML Consultant, Compliance</h1><div id='app'></div></html>")


class WorkdayDetailIntegrity(unittest.IsolatedAsyncioTestCase):
    def test_only_workday_owned_board_and_exact_requisition(self):
        self.assertEqual(
            workday_board("https://paypal.wd1.myworkdayjobs.com/en-US/jobs")[:3],
            ("paypal.wd1.myworkdayjobs.com","paypal","jobs"),
        )
        self.assertIsNotNone(workday_board(BASE))
        for url in (
            "https://paypal.wd1.myworkdayjobs.com.evil.test/en-US/jobs",
            "http://paypal.wd1.myworkdayjobs.com/en-US/jobs",
            "https://evil.test@ntrs.wd1.myworkdayjobs.com/northerntrust",
            "https://paypal.wd1.myworkdayjobs.com/en-US/jobs/job/xx",
        ):
            with self.subTest(url=url):
                self.assertIsNone(workday_board(url))
        self.assertEqual(workday_detail_endpoint(workday_job()),
                         "https://ntrs.wd1.myworkdayjobs.com/wday/cxs/ntrs/northerntrust"+EXT)
        for bad in (
            workday_job(url="https://ntrs.wd1.myworkdayjobs.com.evil.test/northerntrust"+EXT),
            workday_job(url=BASE+"/job/Luxembourg/WRONG_R154518"),
            workday_job(source="Workday:other/northerntrust"),
            workday_job(external_id="/job/../../evil.test"),
            workday_job(source="Workday:ntrs/other"),
        ):
            self.assertIsNone(workday_detail_endpoint(bad))

    def test_relative_list_date_alone_is_never_verified(self):
        self.assertTrue(possibly_recent_workday_listing("Posted Yesterday"))
        self.assertTrue(possibly_recent_workday_listing("Posted 3 Days Ago"))
        self.assertFalse(possibly_recent_workday_listing("Posted 16 Days Ago"))
        self.assertFalse(possibly_recent_workday_listing("Posted 30+ Days Ago"))
        self.assertTrue(possibly_recent_workday_listing(""))
        self.assertFalse(within_new_window("Posted Yesterday"))
        self.assertFalse(within_new_window("Posted Today"))

    def test_exact_full_job_identity_date_and_flags(self):
        job=workday_job()
        info=detail()["jobPostingInfo"]
        self.assertTrue(workday_exact_job(info,job))
        self.assertEqual(workday_original_date(info,job),TODAY)
        self.assertFalse(workday_exact_job(detail(title="Unrelated")["jobPostingInfo"],job))
        self.assertFalse(workday_exact_job(detail(posting_id="WRONG_R154518")["jobPostingInfo"],job))
        self.assertEqual(workday_original_date(detail(start="Posted Today")["jobPostingInfo"],job),"")

    async def test_enriches_full_requirements_from_real_cxs_date(self):
        h=Stub()
        jobs=await fetch_workday(h,{"name":"Northern Trust","sector":"Banking"},BASE)
        self.assertEqual(len(jobs),1)
        j=jobs[0]
        self.assertEqual(j.posted_at,TODAY)
        self.assertIn("3 years of corporate AML",j.description)
        self.assertEqual(j.apply_url,URL)
        self.assertEqual(j.external_id,EXT)
        self.assertEqual(len([q for q in h.requests if q[0]=="GET"]),1)
        self.assertTrue(await verify_application_page(h,j))
        self.assertEqual(j.verification_reason,"native_ats_application_confirmed")

    async def test_not_posted_cannot_apply_wrong_title_or_old_is_rejected(self):
        for data in (
            detail(posted=False),detail(can_apply=False),
            detail(title="Other job"),detail(posting_id="Other_R154518"),
        ):
            with self.subTest(data=data):
                self.assertFalse(await native_workday_application_evidence(Stub(obj=data),workday_job()))
        old=(datetime.now(timezone.utc)-timedelta(days=12)).date().isoformat()
        self.assertFalse(await native_workday_application_evidence(Stub(),workday_job(date=old)))
        self.assertFalse(await verify_application_page(Stub(obj=detail(start=old)),workday_job(date=old)))

    async def test_unknown_original_date_and_failed_detail_do_not_generate_alert(self):
        j=workday_job(date="")
        self.assertFalse(await verify_application_page(Stub(),j))
        self.assertEqual(j.verification_reason,"original_publication_missing_or_older_than_96h")
        missing=Stub(obj={"error":"no exact requisition"})
        jobs=await fetch_workday(missing,{"name":"Northern Trust","sector":"Banking"},BASE)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0].posted_at,"")

    async def test_old_job_without_full_details_is_never_renewed_by_list_relative_date(self):
        old=(datetime.now(timezone.utc)-timedelta(days=20)).date().isoformat()
        h=Stub(obj=detail(start=old))
        jobs=await fetch_workday(h,{"name":"Northern Trust","sector":"Banking"},BASE)
        self.assertEqual(jobs[0].posted_at,old)
        self.assertFalse(await verify_application_page(h,jobs[0]))
        self.assertEqual(jobs[0].verification_reason,"original_publication_missing_or_older_than_96h")


if __name__=="__main__":unittest.main()
