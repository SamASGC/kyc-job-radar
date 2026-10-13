"""v3.5: 12 verified employer careers pages, 5 repaired official URLs, 4 declared ATS feeds."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
NEW = {
    "PostFinance": "https://jobs.postfinance.ch/go/?locale=en_US",
    "Raiffeisen Switzerland": "https://jobs.raiffeisen.ch/",
    "Universal Investment": "https://www.universal-investment.com/en/corporate/career/open-positions/",
    "Langham Hall": "https://careers.langhamhall.com/",
    "Citco Group": "https://fa-euxc-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1",
    "HedgeServ": "https://hedgeserv.wd1.myworkdayjobs.com/HedgeServ",
    "Carne Group": "https://carnepeopleportal.my.salesforce-sites.com/recruit",
    "FundRock": "https://www.fundrock.com/careers-at-fundrock/",
    "Degroof Petercam": "https://www.degroofpetercam.com/en-be/jobs-finance",
    "Harmonic Fund Services": "https://harmonicfundservices.com/careers/",
    "Banco Sabadell": "https://www.sabadellcareers.com/",
    "BPS (SUISSE)": "https://www.bps-suisse.ch/de/jobs-bei-bps-suisse.php"
}
REPAIRED = {
    "Alma": "https://job-boards.greenhouse.io/alma31",
    "Billie": "https://www.billie.io/en/jobs",
    "Lucinity": "https://lucinity.com/open-positions",
    "Nexi": "https://fa-ewwx-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1",
    "Mangopay": "https://career.mangopay.com/jobs"
}
ATS = {
    "Alma": {"kind": "greenhouse", "slug": "alma31"},
    "Nexi": {"kind": "oracle_hcm", "site": "CX_1", "language": "en", "url": REPAIRED["Nexi"]},
    "Citco Group": {"kind": "oracle_hcm", "site": "CX_1", "language": "en", "url": NEW["Citco Group"]},
    "HedgeServ": {"kind": "workday", "url": NEW["HedgeServ"]},
}

class FinancialSourcesV35Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.companies = []
        for file in ("config/companies.json", "config/extra_companies.json"):
            cls.companies.extend(json.loads((ROOT/file).read_text(encoding="utf-8")))
        cls.by_name = {r["name"].casefold():r for r in cls.companies}

    def test_at_least_474_unique_and_156_explicit_ats(self):
        self.assertGreaterEqual(len(self.companies), 474)
        self.assertEqual(len(self.by_name), len(self.companies))
        self.assertGreaterEqual(sum(bool(r.get("ats")) for r in self.companies), 156)

    def test_new_12_are_official_named_employer_portals(self):
        self.assertEqual(len(NEW), 12)
        for name,url in NEW.items():
            with self.subTest(name=name):
                c=self.by_name[name.casefold()]
                self.assertEqual(c["careers_url"],url)
                self.assertEqual(urlsplit(url).scheme,"https")
                self.assertTrue(c["enabled"])
                self.assertTrue(c["specialism"])
                self.assertIn(url,c["origin"])
                if name == "Raiffeisen Switzerland":
                    # v3.16: the public first-party portal exposes a provider
                    # medium whose employer identity and requisitions were checked.
                    self.assertEqual(c["verification_level"], "official_ats_live_probe_passed")
                    self.assertEqual(c.get("ats", []), [{"kind": "prospective", "medium_id": 1950}])
                    self.assertIn("/medium/1950", c["origin"])
                else:
                    self.assertEqual(c["verification_level"],
                        "official_ats_pending_live_smoke" if name in ATS else "official_careers_url_not_necessarily_api")
                    self.assertEqual(c.get("ats", []), [ATS[name]] if name in ATS else [])

    def test_five_failed_legacy_sources_have_real_recruitment_links(self):
        self.assertEqual(len(REPAIRED), 5)
        for name,url in REPAIRED.items():
            with self.subTest(name=name):
                c=self.by_name[name.casefold()]
                self.assertEqual(c["careers_url"],url)
                self.assertIn(url,c["origin"])
                self.assertEqual(c.get("ats",[]),[ATS[name]] if name in ATS else [])

    def test_does_not_equate_source_configuration_to_confirmed_vacancies(self):
        from job_radar.v2_quality import original_posted_at
        self.assertIsNone(original_posted_at("Posted 2 days ago"))
        self.assertIsNone(original_posted_at(""))

if __name__ == "__main__":
    unittest.main()
