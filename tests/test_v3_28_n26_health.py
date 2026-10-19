"""V3.28 live-probed official N26 API and direct-source outage reliability."""
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import AsyncMock,patch

from job_radar.models import Job
from job_radar.native_apply import native_application_evidence
from job_radar.v2_quality import verify_application_page
from job_radar.scanner import fetch_company
from job_radar.source_inventory import summarize_source_coverage

def n26_job(id="8201437",url=None,board="n26",company="N26",date=None):
    return Job(
        source=f"Greenhouse:{board}",source_kind="official ATS",
        company=company,sector="Banking",title="AFC Analyst - French Market",
        location="Madrid, Spain - Hybrid",
        description="AML/KYC client monitoring reviews",
        apply_url=url or f"https://n26.com/en-eu/careers/positions/{id}?gh_jid={id}",
        external_id=id,
        posted_at=date or (datetime.now(timezone.utc)-timedelta(hours=5)).isoformat()
    ).finalize()

class Response:
    def __init__(self,data=None,status=200,text="<html><h1>Job details</h1></html>"):
        self.status_code=status;self._data=data;self.text=text
    def json(self):return self._data

class Http:
    def __init__(self,detail=None,page=None):
        self.detail=detail or {"id":8201437,"title":"AFC Analyst - French Market","questions":[{"label":"CV"}]}
        self.page=page or Response()
        self.calls=[]
    async def get(self,url):
        self.calls.append(url)
        return Response(self.detail) if "boards-api.greenhouse.io" in url else self.page

class N26BrandedExactApply(unittest.IsolatedAsyncioTestCase):
    async def test_verified_first_party_n26_id_title_and_live_questions(self):
        j=n26_job()
        h=Http()
        self.assertTrue(await native_application_evidence(h,j))
        self.assertTrue(await verify_application_page(h,j))
        self.assertEqual(j.verification_reason,"native_ats_application_confirmed")
        self.assertIn("/v1/boards/n26/jobs/8201437?questions=true",h.calls[-1])

    async def test_fake_domain_board_job_and_query_rejected(self):
        candidates=[
            n26_job(url="https://n26.com.evil.test/en-eu/careers/positions/8201437?gh_jid=8201437"),
            n26_job(url="https://n26.com/en-eu/careers/positions/999?gh_jid=8201437"),
            n26_job(url="https://n26.com/en-eu/careers/positions/8201437?gh_jid=999"),
            n26_job(url="https://n26.com/en-eu/careers/positions/8201437"),
            n26_job(board="embed"),
            n26_job(company="Coinbase"),
        ]
        for j in candidates:
            with self.subTest(url=j.apply_url,source=j.source,company=j.company):
                self.assertFalse(await native_application_evidence(Http(),j))

    async def test_wrong_live_provider_record_or_old_date_is_never_eligible(self):
        for data in (
            {"id":999,"title":"AFC Analyst - French Market","questions":[{"label":"CV"}]},
            {"id":8201437,"title":"Unrelated role","questions":[{"label":"CV"}]},
            {"id":8201437,"title":"AFC Analyst - French Market"},
        ):
            with self.subTest(data=data):
                self.assertFalse(await native_application_evidence(Http(detail=data),n26_job()))
        j=n26_job(date=(datetime.now(timezone.utc)-timedelta(days=6)).isoformat())
        self.assertFalse(await verify_application_page(Http(),j))
        self.assertEqual(j.verification_reason,"original_publication_missing_or_older_than_96h")

    async def test_closed_page_remains_closed_even_if_provider_says_live(self):
        j=n26_job()
        page=Response(text="<p>This job is no longer available</p>")
        self.assertFalse(await verify_application_page(Http(page=page),j))
        self.assertEqual(j.verification_reason,"explicitly_closed")


class DirectAvailabilityDiagnostics(unittest.IsolatedAsyncioTestCase):
    async def test_healthy_empty_ats_not_labeled_outage_due_to_fallback_403(self):
        c={"name":"NomuPay","ats":[{"kind":"personio","slug":"nomupay"}],
           "careers_url":"https://nomupay.jobs.personio.com/"}
        with patch("job_radar.scanner.fetch_target",new=AsyncMock(return_value=[])), \
             patch("job_radar.scanner.fetch_generic",new=AsyncMock(side_effect=RuntimeError("HTTP403"))):
            jobs,h=await fetch_company(None,c,{"discovery":{}})
        self.assertEqual(jobs,[])
        self.assertTrue(h["ok"])
        self.assertTrue(h["ats_reachable"])
        self.assertTrue(h["degraded"])
        self.assertIn("HTTP403",h["error"])
        summary=summarize_source_coverage([c],[h])
        self.assertEqual(summary["direct_errors"],0)
        self.assertEqual(summary["direct_reachable_zero"],1)
        self.assertEqual(summary["direct_degraded"],1)
        self.assertIn("HTTP403",summary["sources"][0]["warning"])

    async def test_genuine_provider_404_with_blocked_fallback_is_down(self):
        c={"name":"BrokenBoard","ats":[{"kind":"breezy","slug":"broken"}],
           "careers_url":"https://employer.invalid/careers"}
        with patch("job_radar.scanner.fetch_target",new=AsyncMock(side_effect=RuntimeError("404"))), \
             patch("job_radar.scanner.fetch_generic",new=AsyncMock(side_effect=RuntimeError("403"))):
            jobs,h=await fetch_company(None,c,{"discovery":{}})
        self.assertFalse(h["ok"])
        self.assertFalse(h.get("degraded",False))
        self.assertIn("404",h["error"])
        self.assertEqual(summarize_source_coverage([c],[h])["direct_errors"],1)

    async def test_404_ats_but_reachable_fallback_is_degraded_not_hard_down(self):
        c={"name":"PayDo","ats":[{"kind":"greenhouse","slug":"paydo"}],
           "careers_url":"https://paydo.com/career/"}
        with patch("job_radar.scanner.fetch_target",new=AsyncMock(side_effect=RuntimeError("404"))), \
             patch("job_radar.scanner.fetch_generic",new=AsyncMock(return_value=([],[],"https://paydo.com/career/"))):
            jobs,h=await fetch_company(None,c,{"discovery":{}})
        self.assertTrue(h["ok"])
        self.assertTrue(h["careers_reachable"])
        self.assertTrue(h["degraded"])
        self.assertEqual(h["jobs"],0)

if __name__=="__main__":unittest.main()
