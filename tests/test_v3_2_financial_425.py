"""v3.2 - expansion to 425 distinct direct banking and financial crime employers."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ATS = {
    "Numeus": "numus",
    "WhiteTech": "whitetech",
    "RootstockLabs": "rootstocklabsltd",
    "Dialectic": "dialecticch",
    "Capstone Investment Advisors": "capstoneinvestmentadvisors",
    "Vestwell": "vestwell",
    "ATLAS SP": "atlassp",
}
PORTALS = {
    "Zuger Kantonalbank", "Schwyzer Kantonalbank",
    "Basler Kantonalbank", "Glarner Kantonalbank",
    "Appenzeller Kantonalbank", "acrevis Bank",
    "Nidwaldner Kantonalbank", "Advanzia Bank",
    "Hypothekarbank Lenzburg", "Migros Bank", "Bank Avera",
    "Inbank", "Bigbank", "Holm Bank", "Urbo Bank", "Paysera",
    "Spuerkeess", "Banque Raiffeisen Luxembourg",
}


class V32DirectEmployersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.companies = (
            json.loads((ROOT/"config/companies.json").read_text()) +
            json.loads((ROOT/"config/extra_companies.json").read_text())
        )
        cls.names = {c["name"].casefold(): c for c in cls.companies}

    def test_425_distinct_direct_employers_and_151_explicit_ats(self):
        self.assertGreaterEqual(len(self.companies), 425)
        self.assertEqual(len(self.names), len(self.companies))
        self.assertGreaterEqual(
            sum(bool(c.get("ats")) for c in self.companies), 151
        )

    def test_seven_attributable_greenhouse_boards(self):
        self.assertEqual(len(ATS), 7)
        for name, slug in ATS.items():
            with self.subTest(name=name):
                c = self.names[name.casefold()]
                self.assertTrue(c["enabled"])
                self.assertEqual(c["ats"], [{"kind": "greenhouse", "slug": slug}])
                self.assertEqual(c["verification_level"],
                                 "official_ats_pending_live_health")
                self.assertIn(c["sector"], {"Fintech", "Banca", "Payments"})
                board = urlsplit(c["careers_url"])
                evidence = urlsplit(c["origin"].split(": ", 1)[1])
                self.assertEqual(board.hostname, "job-boards.greenhouse.io")
                self.assertEqual(evidence.hostname, board.hostname)
                self.assertEqual(board.path.strip("/"), slug)
                self.assertEqual(evidence.path.strip("/").split("/")[0], slug)

    def test_18_verified_first_party_career_sites_are_not_apis(self):
        self.assertEqual(len(PORTALS), 18)
        self.assertTrue(set(ATS).isdisjoint(PORTALS))
        for name in PORTALS:
            with self.subTest(name=name):
                c = self.names[name.casefold()]
                self.assertTrue(c["enabled"])
                self.assertEqual(
                    c["verification_level"],
                    "official_careers_url_not_necessarily_api",
                )
                self.assertFalse(c.get("ats"))
                self.assertTrue(c["careers_url"].startswith("https://"))
                self.assertIn(c["careers_url"], c["origin"])
                self.assertIn(c["sector"], {"Banca", "Payments"})


if __name__ == "__main__":
    unittest.main()
