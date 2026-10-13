"""Public Swiss-bank recruiting source must be scoped to employer and original posts."""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from job_radar.sources.prospective import _parse, fetch_prospective

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,10,13,20,0,tzinfo=timezone.utc)
RAI={"name":"Raiffeisen Switzerland","sector":"Banca"}
BEKB={"name":"Berner Kantonalbank","sector":"Banca"}


def job(id="101", url="https://raiffeisen.wd3.myworkdayjobs.com/jobs-raiffeisen/job/Zurich/AML_Specialist_R000123/apply",
        start="2026-10-12T08:00:00Z", end="2026-11-01T00:00:00Z", lang="Deutsch"):
    return {"id":id,"title":"AML/KYC Specialist","start_date":start,
      "end_date":end,"last_modification_timestamp":"2026-10-13T18:00:00Z",
      "szas":{"sza_apply_link":url,"sza_location.country":"Schweiz",
        "sza_location.city":"Zürich","sza_requirements":f"Fluent {lang} required",
        "sza_tasks":"<p>Client onboarding and AML investigations</p>"}}


class ProspectiveBankV316Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.employers=[]
        for path in ("config/companies.json","config/extra_companies.json"):
            cls.employers+=json.loads((ROOT/path).read_text(encoding="utf-8"))
        cls.by={r["name"]:r for r in cls.employers}

    def test_500_unique_employers_181_configured_employer_ats(self):
        self.assertEqual(len(self.employers),500)
        self.assertEqual(len({r["name"].casefold() for r in self.employers}),500)
        self.assertGreaterEqual(sum(bool(r.get("ats")) for r in self.employers),181)
        for name,mid in (("Raiffeisen Switzerland",1950),("Berner Kantonalbank",1509)):
            with self.subTest(name=name):
                row=self.by[name]
                self.assertEqual(row["ats"],[{"kind":"prospective","medium_id":mid}])
                self.assertEqual(row["verification_level"],"official_ats_live_probe_passed")
                self.assertIn(f"/medium/{mid}",row["origin"])
                self.assertTrue(row["enabled"])

    def test_original_date_not_modified_or_discovered_at(self):
        r=_parse(job(),RAI,1950,NOW)
        self.assertIsNotNone(r)
        self.assertEqual(r.posted_at,"2026-10-12T08:00:00Z")
        self.assertEqual(r.location,"Zürich, Switzerland")
        self.assertIn("Fluent Deutsch required",r.description)
        self.assertIn("Client onboarding",r.description)
        self.assertEqual(r.source_kind,"official ATS")
        self.assertEqual(r.external_id,"1950:101")

    def test_empty_original_start_date_is_not_invented(self):
        r=_parse(job(start=""),RAI,1950,NOW)
        self.assertEqual(r.posted_at,"")
        from job_radar.v2_quality import within_new_window
        self.assertFalse(within_new_window(r.posted_at,96,now=NOW))

    def test_expired_job_skipped_even_when_original_date_recent(self):
        self.assertIsNone(_parse(job(end="2026-10-12T00:00:00Z"),RAI,1950,NOW))

    def test_mailto_offsite_and_general_careers_links_not_trusted(self):
        self.assertIsNone(_parse(job(url="mailto:hr@raiffeisen.ch"),RAI,1950,NOW))
        self.assertIsNone(_parse(job(url="https://fake-ats.invalid/job/123"),RAI,1950,NOW))
        self.assertIsNone(_parse(job(url="http://raiffeisen.wd3.myworkdayjobs.com/jobs/x"),RAI,1950,NOW))
        self.assertIsNone(_parse(job(id="non-numeric"),RAI,1950,NOW))

    def test_berner_cantonal_bank_applications(self):
        link="https://bekb.abacuscity.ch/de/jobform_1_2891/AML-Analyst"
        r=_parse(job(url=link),BEKB,1509,NOW)
        self.assertIsNotNone(r)
        self.assertEqual(r.apply_url,link)
        self.assertEqual(r.external_id,"1509:101")
        self.assertIsNone(_parse(job(url=link),RAI,1950,NOW))

    def test_strict_no_fake_96h_or_mandatory_german(self):
        from job_radar.v2_quality import original_posted_at,unmet_mandatory_languages
        self.assertIsNone(original_posted_at("Posted Today"))
        row=_parse(job(lang="German"),RAI,1950,NOW)
        self.assertIn("german",unmet_mandatory_languages(row,{"English","French","Spanish"}))
        import yaml
        cfg=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(cfg["strict_quality_gate"])
        self.assertEqual(cfg["max_post_age_hours"],96)
        self.assertEqual(cfg["remote_scope"],"Spain")
        state=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]),306)


class ProspectivePaginationV316Tests(unittest.IsolatedAsyncioTestCase):
    async def test_no_cross_employer_feeds(self):
        class Dummy:
            async def get(self,url):
                raise AssertionError("must not call network for wrong bank medium")
        with self.assertRaises(ValueError):
            await fetch_prospective(Dummy(),RAI,1509)

    async def test_pagination_exact_employer_total_and_untrusted_removed(self):
        class Response:
            def __init__(self, url):
                off=int(url.split("offset=")[1].split("&")[0])
                self.data={"medium_id":"1950","total":53,
                    "jobs":[job(id=str(i)) for i in range(off, min(off+50,53))]}
            def raise_for_status(self):pass
            def json(self):return self.data
        class Http:
            def __init__(self):self.calls=[]
            async def get(self,url):
                self.calls.append(url);return Response(url)
        h=Http()
        rows=await fetch_prospective(h,RAI,1950)
        self.assertEqual(len(rows),53)
        self.assertEqual(len(h.calls),2)
        self.assertEqual(len({x.external_id for x in rows}),53)

    async def test_500_pages_never_mixed_or_misreported(self):
        class Response:
            def raise_for_status(self):pass
            def json(self):return {"medium_id":"1509","total":0,"jobs":[]}
        class Http:
            async def get(self,url):return Response()
        self.assertEqual(await fetch_prospective(Http(),BEKB,1509),[])

    async def test_foreign_medium_rejected_even_with_https(self):
        class Response:
            def raise_for_status(self):pass
            def json(self):return {"medium_id":"9999","jobs":[job()],"total":1}
        class Http:
            async def get(self,url):return Response()
        with self.assertRaisesRegex(ValueError,"different employer"):
            await fetch_prospective(Http(),RAI,1950)


if __name__=="__main__":
    unittest.main()
