"""V3.3: distinguish 450 direct employers from active ATS and real alerts."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIRECT_PORTALS = {
    "Berner Kantonalbank", "Schaffhauser Kantonalbank", "Urner Kantonalbank",
    "Obwaldner Kantonalbank", "Banque Piguet Galland", "Banque Heritage",
    "Cembra Money Bank", "Bank WIR", "SME Bank Lithuania", "Mano Bank",
    "Swiss Life Asset Managers", "Foyer Group", "Kaiser Partner Privatbank",
    "Banque de Commerce et de Placements", "Bordier & Cie", "Delen Private Bank Luxembourg",
    "Baloise Luxembourg", "fundcraft", "Moonfare", "Candriam",
    "Lazard", "Swiss Prime Site Solutions", "Eurazeo", "Banco Santander",
}
ATS_NAME = "NextEnergy Group"


class BankingV33Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.employers = (
            json.loads((ROOT / "config/companies.json").read_text(encoding="utf-8"))
            + json.loads((ROOT / "config/extra_companies.json").read_text(encoding="utf-8"))
        )
        cls.by_name = {x["name"].casefold(): x for x in cls.employers}

    def test_450_unique_employers_and_152_configured_ats(self):
        self.assertGreaterEqual(len(self.employers), 450)
        self.assertEqual(len(self.by_name), len(self.employers))
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.employers), 152)

    def test_24_first_party_sites_must_not_masquerade_as_verified_ats(self):
        self.assertEqual(len(DIRECT_PORTALS), 24)
        for name in DIRECT_PORTALS:
            with self.subTest(company=name):
                x = self.by_name[name.casefold()]
                self.assertTrue(x["enabled"])
                self.assertEqual(x["verification_level"], "official_careers_url_not_necessarily_api")
                self.assertFalse(x.get("ats"))
                self.assertEqual(urlsplit(x["careers_url"]).scheme, "https")
                self.assertIn(x["careers_url"], x["origin"])

    def test_official_greenhouse_board_identity(self):
        x = self.by_name[ATS_NAME.casefold()]
        self.assertEqual(x["ats"], [{"kind": "greenhouse", "slug": "nextenergygroup"}])
        self.assertEqual(x["careers_url"], "https://job-boards.greenhouse.io/nextenergygroup")
        self.assertEqual(x["verification_level"], "official_ats_pending_live_smoke")
        self.assertEqual(len(DIRECT_PORTALS) + 1, 25)

    def test_source_coverage_not_evidence_of_admitted_jobs(self):
        from job_radar.v2_quality import original_posted_at
        self.assertIsNone(original_posted_at("Posted 2 Days Ago"))
        self.assertIsNone(original_posted_at(""))
        self.assertIsNone(original_posted_at("updated yesterday"))


if __name__ == "__main__":
    unittest.main()
