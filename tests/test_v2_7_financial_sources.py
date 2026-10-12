"""v2.7: financial expansion with exact ATS identities and no invented URLs."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
NEW_ATS = {
    "Convera": ("greenhouse", "convera"),
    "Permira": ("greenhouse", "permiraexternalprivate"),
    "Telcoin": ("greenhouse", "telcoin"),
    "Bybit": ("greenhouse", "bybit"),
    "Dotfile": ("ashby", "dotfile"),
    "Merge Money": ("ashby", "mergemoney"),
    "TaxBit": ("greenhouse", "taxbit"),
    "INFINIT": ("lever", "infinit"),
    "Factor": ("lever", "factor"),
    "Allfunds": ("workday", None),
    "Fin (Payments)": ("ashby", "fin"),
    "Thera": ("ashby", "thera"),
    "Astra Payments": ("ashby", "astra"),
    "Latitude Global": ("ashby", "latitude-global"),
}
NEW_CORPORATE = {
    "ING Bank", "Standard Chartered", "Danske Bank", "KBC Bank",
    "Intesa Sanpaolo", "Commerzbank", "Bank of America",
    "Bank of Ireland", "Rabobank", "Société Générale",
    "NatWest Group", "Bankinter",
}


class FinancialV27Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = (json.loads((ROOT/"config/companies.json").read_text()) +
                    json.loads((ROOT/"config/extra_companies.json").read_text()))
        cls.lookup = {r["name"]: r for r in cls.rows}

    def test_310_unique_employers(self):
        self.assertGreaterEqual(len(self.rows), 310)
        self.assertEqual(len(self.lookup), len(self.rows))

    def test_14_explicit_ats_evidenced(self):
        for company, (kind, slug) in NEW_ATS.items():
            with self.subTest(company=company):
                c = self.lookup[company]
                self.assertEqual(c["verification_level"], "explicit_ats_pending_live_smoke")
                self.assertEqual(len(c["ats"]), 1)
                self.assertTrue(c["enabled"])
                self.assertEqual(c["ats"][0]["kind"], kind)
                self.assertEqual(urlsplit(c["careers_url"]).scheme, "https")
                self.assertIn("Official ATS", c["origin"])
                evidence = c["origin"].split(": ", 1)[1]
                self.assertEqual(urlsplit(evidence).scheme, "https")
                if slug:
                    self.assertEqual(c["ats"][0]["slug"], slug)
                    self.assertEqual(
                        urlsplit(c["careers_url"]).path.strip("/").casefold(),
                        slug.casefold(),
                    )
                else:
                    self.assertEqual(c["ats"][0]["url"], c["careers_url"])
                    self.assertIn("myworkdayjobs.com", c["careers_url"])

    def test_12_official_career_sites_do_not_masquerade_as_ats(self):
        for company in NEW_CORPORATE:
            with self.subTest(company=company):
                c = self.lookup[company]
                self.assertFalse(c.get("ats"))
                self.assertEqual(c["verification_level"],
                                 "official_careers_url_not_necessarily_api")
                self.assertTrue(c["careers_url"].startswith("https://"))
                self.assertIn(c["careers_url"], c["origin"])


if __name__ == "__main__":
    unittest.main()
