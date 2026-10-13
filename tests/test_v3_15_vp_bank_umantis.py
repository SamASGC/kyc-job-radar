"""Umantis parser only accepts actual first-party VP Bank vacancies and dated rows."""
import unittest

from job_radar.sources.vp_bank_umantis import parse_vp_bank_umantis_page

URL="https://recruitingapp-2813.umantis.com/Jobs/All?CompanyID=All&Reset=G&lang=eng"
COMPANY={"name":"VP Bank Group","sector":"Banca"}
HTML="""<html><table class="tableaslist">
<tr class="tableaslist_contentrow1"><td>
  <span class="tableaslist_text">VP Bank (Luxembourg) SA</span>
  <span class="tableaslist_text">| Online since: 10/07/2026</span>
  <span class="tableaslist_subtitle"><a class="HSTableLinkSubTitle"
    href="/Vacancies/2324/Description/2">CDD Analyst</a></span>
  <span>Luxembourg | Unlimited</span>
</td></tr>
<tr class="tableaslist_contentrow2"><td>
  <span class="tableaslist_text">VP Bank (Schweiz) AG</span>
  <span class="tableaslist_text">| Online since: 08/25/2026</span>
  <span><a class="HSTableLinkSubTitle"
    href="/Vacancies/2312/Description/1">AML Investigator</a></span>
  <span>Zurich | Full time</span>
</td></tr>
<tr class="tableaslist_contentrow1"><td>
  <span class="tableaslist_text">VP Bank Ltd Singapore Branch</span>
  <span><a class="HSTableLinkSubTitle"
    href="/Vacancies/3001/Description/2">Singapore Operations Specialist</a></span>
</td></tr>
<tr><td><a href="/Vacancies/Register/CheckLogin/9999">Job alerts</a></td></tr>
<tr><td><a class="HSTableLinkSubTitle" href="https://evil.invalid/Vacancies/2324/Description/2">Fraud link</a></td></tr>
</table></html>"""


class VPBankLiveRowParserTests(unittest.TestCase):
    def test_real_vacancies_only_and_per_row_original_dates(self):
        jobs=parse_vp_bank_umantis_page(HTML,URL,COMPANY)
        self.assertEqual(len(jobs),3,[(j.title,j.apply_url) for j in jobs])
        self.assertEqual([j.title for j in jobs],[
           "CDD Analyst","AML Investigator","Singapore Operations Specialist"
        ])
        self.assertEqual([j.posted_at for j in jobs],[
           "2026-10-07","2026-08-25",""
        ])
        self.assertEqual([j.location for j in jobs],[
           "Luxembourg","Zurich, Switzerland","Singapore"
        ])
        self.assertTrue(all(j.source_kind=="official career page" for j in jobs))
        self.assertEqual(len({j.fingerprint for j in jobs}),3)

    def test_real_individual_role_urls_not_search_or_registration(self):
        jobs=parse_vp_bank_umantis_page(HTML,URL,COMPANY)
        self.assertEqual(jobs[0].apply_url,
             "https://recruitingapp-2813.umantis.com/Vacancies/2324/Description/2")
        self.assertEqual(jobs[1].apply_url,
             "https://recruitingapp-2813.umantis.com/Vacancies/2312/Description/1")
        self.assertTrue(all("CheckLogin" not in j.apply_url for j in jobs))

    def test_untrusted_foreign_portal_not_attributed_to_vp_bank(self):
        self.assertEqual(parse_vp_bank_umantis_page(HTML,
           "https://another-bank.example/Jobs/All", COMPANY),[])

    def test_invalid_us_online_date_is_not_fabricated(self):
        html=HTML.replace("10/07/2026","30/30/2026")
        jobs=parse_vp_bank_umantis_page(html,URL,COMPANY)
        self.assertEqual(jobs[0].posted_at,"")

if __name__=="__main__":
    unittest.main()
