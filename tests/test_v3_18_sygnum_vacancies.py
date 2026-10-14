"""Regression coverage for job-selector URLs and public Sygnum recruitment pages."""
import json
import unittest
from pathlib import Path
from job_radar.models import canonical_url
from job_radar.sources.sygnum_salesforce import parse_sygnum_vacancies

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://sygnumpeopleportal.my.salesforce-sites.com/recruit/fRecruit__ApplyJobList"
DETAIL = "https://sygnumpeopleportal.my.salesforce-sites.com/recruit/fRecruit__ApplyJob"

HTML = """<html><body><table><tbody>
<tr><td><a href="/recruit/fRecruit__ApplyJob?vacancyNo=VN192&utm_source=abc">(Senior) Application Security Engineer</a></td><td>Switzerland</td><td>Zurich</td><td>Permanent</td><td></td><td>Partial Home Office</td></tr>
<tr><td><a href="/recruit/fRecruit__ApplyJob?vacancyNo=VN287">Credit & Lending Intern</a></td><td>Switzerland</td><td>Zurich</td><td>Internship</td><td>6 months</td><td>Partial Home Office</td></tr>
<tr><td><a href="https://evil.example/recruit/fRecruit__ApplyJob?vacancyNo=VN999">Fake bank KYC analyst</a></td></tr>
<tr><td><a href="/recruit/fRecruit__ApplyJob">Apply</a></td></tr>
<tr><td><a href="/recruit/fRecruit__ApplyJob?vacancyNo=bad">Invalid</a></td></tr>
</tbody></table></body></html>"""


class SygnumOfficialListTests(unittest.TestCase):
    def test_job_selectors_survive_but_tracking_is_removed(self):
        a=canonical_url(DETAIL+"?vacancyNo=VN192&utm_source=ad")
        b=canonical_url(DETAIL+"?vacancyNo=VN287")
        self.assertEqual(a,DETAIL+"?vacancyNo=VN192")
        self.assertEqual(b,DETAIL+"?vacancyNo=VN287")
        self.assertNotEqual(a,b)

    def test_distinct_public_job_rows_with_locations(self):
        jobs=parse_sygnum_vacancies(HTML,BASE,{"name":"Sygnum Bank","sector":"Banca"})
        self.assertEqual(len(jobs),2)
        self.assertEqual({x.external_id for x in jobs},{"VN192","VN287"})
        self.assertEqual({x.title for x in jobs},{
            "(Senior) Application Security Engineer","Credit & Lending Intern"
        })
        self.assertEqual(len({x.fingerprint for x in jobs}),2)
        self.assertTrue(all("Switzerland" in x.location for x in jobs))
        self.assertTrue(all("Zurich" in x.location for x in jobs))
        self.assertTrue(all(x.source_kind=="official career page" for x in jobs))
        self.assertTrue(all(not x.posted_at for x in jobs))
        self.assertTrue(all("vacancyNo=" in x.apply_url for x in jobs))

    def test_invalid_domain_has_no_jobs(self):
        jobs=parse_sygnum_vacancies(HTML,"https://evil.example/recruit/fRecruit__ApplyJobList",{"name":"Sygnum Bank"})
        self.assertEqual(jobs,[])

    def test_exact_500_and_unmodified_182_explicit_ats(self):
        rows=[]
        for p in ("config/companies.json","config/extra_companies.json"):
            rows+=json.loads((ROOT/p).read_text(encoding="utf-8"))
        self.assertEqual(len(rows),500)
        self.assertEqual(len({x["name"].casefold() for x in rows}),500)
        self.assertEqual(sum(bool(x.get("ats")) for x in rows),182)
        by={x["name"]:x for x in rows}
        self.assertEqual(by["Sygnum Bank"]["careers_url"],BASE)
        self.assertEqual(by["C24 Bank"]["careers_url"],
            "https://c24-recruiting.powerappsportals.com/de-DE/vacancies/")
        self.assertFalse(by["Sygnum Bank"].get("ats"))
        self.assertFalse(by["C24 Bank"].get("ats"))
        self.assertIn("JavaScript-only vacancy table",by["C24 Bank"]["origin"])

    def test_policy_never_fabricates_original_posting(self):
        from job_radar.v2_quality import original_posted_at
        self.assertIsNone(original_posted_at(""))
        import yaml
        policy=yaml.safe_load((ROOT/"config/profile.yaml").read_text(encoding="utf-8"))
        self.assertEqual(policy["max_post_age_hours"],96)
        self.assertTrue(policy["strict_quality_gate"])
        self.assertEqual(policy["remote_scope"],"Spain")
        data=json.loads((ROOT/"data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["seen"]),306)


class SygnumDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_generic_dispatch_never_turns_untrusted_links_into_jobs(self):
        from job_radar.sources.generic import fetch_generic
        class R:
            url=BASE
            text=HTML
            def raise_for_status(self): pass
        class H:
            async def get(self,url):return R()
        jobs,targets,final=await fetch_generic(H(),{
            "name":"Sygnum Bank","careers_url":BASE,"sector":"Banca"
        })
        self.assertEqual(len(jobs),2)
        self.assertEqual(targets,[])
        self.assertEqual(final,BASE)



class EmployerHealthTruthfulnessTests(unittest.TestCase):
    def test_direct_metrics_exclude_rotating_and_distinguish_empty(self):
        from job_radar.source_inventory import summarize_source_coverage
        employers=[
            {"name":"A","careers_url":"https://a.example/jobs"},
            {"name":"B","careers_url":"https://b.example/jobs"},
            {"name":"C","careers_url":"https://c.example/jobs"},
            {"name":"D","careers_url":"https://d.example/jobs"},
            {"name":"Rotating firm","careers_url":"https://rotating.example/jobs"},
        ]
        health=[
            {"company":"A","ok":True,"jobs":7},
            {"company":"B","ok":False,"jobs":0,"error":"HTTP 403"},
            {"company":"C","ok":True,"jobs":0},
            {"company":"Rotating firm","ok":True,"jobs":400},
        ]
        x=summarize_source_coverage(employers,health,
            direct_company_names={"a","b","c","d"})
        self.assertEqual(x["direct_configured"],4)
        self.assertEqual(x["direct_with_records"],1)
        self.assertEqual(x["direct_errors"],1)
        self.assertEqual(x["direct_reachable_zero"],1)
        self.assertEqual(x["direct_not_checked"],1)
        self.assertEqual(x["with_jobs"],2)  # Global includes the rotating firm

if __name__=="__main__":
    unittest.main()
