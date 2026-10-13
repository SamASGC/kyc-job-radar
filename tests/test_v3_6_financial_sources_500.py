"""v3.6: 500 distinct direct financial employers; careers URLs are not API certifications."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
NEW_EMPLOYERS = {
    "Lightyear": "https://careers.lightyear.com/",
    "Leonteq": "https://www.leonteq.com/about-us/careers/open-positions?language_id=1",
    "Cecabank": "https://www.cecabank.es/trabaja-con-nosotros/",
    "BancaStato": "https://carriere.bancastato.ch/jobs.php?lan=it",
    "Kutxabank": "https://www.kutxabanktalent.com/es/",
    "Finbee": "https://www.finbee.lt/karjera/",
    "Saldo Bank": "https://www.saldo.com/lt-lt/career/",
    "Bellevue Group": "https://www.bellevue.ch/all-en/all/about-us/contact-us/career",
    "CBH Compagnie Bancaire Helvétique": "https://cbhbank.com/en/about-us/careers/",
    "Reichmuth & Co Privatbankiers": "https://www.reichmuthco.ch/en/karriere/senior-portfolio-manager/",
    "ODDO BHF": "https://www.oddo-bhf.com/discover-our-jobs/",
    "European Investment Bank": "https://www.eib.org/en/about/careers/index",
    "European Stability Mechanism": "https://www.esm.europa.eu/careers/vacancies",
    "FIS Global": "https://careers.fisglobal.com/us/en",
    "Temenos": "https://www.temenos.com/about-us/careers/",
    "Banco Cetelem": "https://www.cetelem.es/sobre-cetelem/unete-a-nosotros",
    "Coop Pank": "https://www.cooppank.ee/coop-pank/tule-toole",
    "Luxembourg Stock Exchange": "https://www.luxse.com/about-us/careers",
    "European Investment Fund": "https://www.eif.org/work-with-us/careers?lang=-en",
    "Maerki Baumann": "https://www.maerki-baumann.ch/de/unsere-bank/stellenangebote",
    "Banco Pichincha España": "https://www.bancopichincha.es/unete-a-nuestro-equipo",
    "JPMorgan Chase": "https://careers.jpmorgan.com/global/en/chase",
    "Morgan Stanley": "https://www.morganstanley.com/careers/career-opportunities-search",
    "Goldman Sachs": "https://www.goldmansachs.com/careers",
    "Franklin Templeton": "https://careers.franklintempleton.com/us/en",
    "Invesco": "https://invesco.wd1.myworkdayjobs.com/IVZ"
}
ATS_PROVIDER = {"kind": "workday", "url": "https://invesco.wd1.myworkdayjobs.com/IVZ"}


class SourceExpansionV36Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = []
        for path in ("config/companies.json", "config/extra_companies.json"):
            cls.rows.extend(json.loads((ROOT / path).read_text(encoding="utf-8")))
        cls.by_name = {row["name"].casefold(): row for row in cls.rows}

    def test_exact_500_distinct_employers_and_157_ats(self):
        self.assertEqual(len(cls_rows := self.rows), 500)
        self.assertEqual(len(self.by_name), len(cls_rows), "Duplicate employer names")
        self.assertTrue(all(r.get("enabled", True) for r in cls_rows))
        self.assertEqual(sum(bool(r.get("ats")) for r in cls_rows), 157)

    def test_26_employer_controlled_careers_sources(self):
        self.assertEqual(len(NEW_EMPLOYERS), 26)
        for name, url in NEW_EMPLOYERS.items():
            with self.subTest(company=name):
                row = self.by_name[name.casefold()]
                self.assertEqual(row["careers_url"], url)
                p = urlsplit(url)
                self.assertEqual(p.scheme, "https")
                self.assertTrue(p.hostname)
                self.assertIn(url, row["origin"])
                self.assertTrue(row["specialism"])
                self.assertTrue(row["enabled"])
                self.assertEqual(row["priority"], "P1")
                if name != "Invesco":
                    self.assertFalse(row.get("ats"), "Do not invent ATS feeds")
                    self.assertEqual(row["verification_level"],
                                     "official_careers_url_not_necessarily_api")
                else:
                    self.assertEqual(row.get("ats"), [ATS_PROVIDER])
                    self.assertEqual(row["verification_level"],
                                     "official_ats_pending_live_smoke")

    def test_existing_96h_and_seen_state_remain_in_place(self):
        import yaml
        profile = yaml.safe_load((ROOT / "config/profile.yaml").read_text(encoding="utf-8"))
        self.assertTrue(profile["strict_quality_gate"])
        self.assertEqual(profile["max_post_age_hours"], 96)
        self.assertEqual(profile["remote_scope"], "Spain")
        state = json.loads((ROOT / "data/state.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(state["seen"]), 306)


if __name__ == "__main__":
    unittest.main()
