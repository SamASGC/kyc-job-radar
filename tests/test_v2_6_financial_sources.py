"""Quality checks for new bank, asset-servicer and FinCrime sources."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ADDED_ATS = {
    "Capco": ("greenhouse", "capco"),
    "Carta": ("greenhouse", "carta"),
    "Aztec Group": ("workday", None),
    "Arendt": ("workday", None),
    "AiPrise": ("ashby", "aiprise"),
    "Sayari": ("greenhouse", "sayari"),
    "IMC Trading": ("greenhouse", "imc"),
    "Flow Traders": ("greenhouse", "flowtraders"),
    "BNY": ("oracle_hcm", None),
}
ADDED_SITES = {
    "Mirabaud Group", "J. Safra Sarasin", "Banque Cantonale Vaudoise",
    "Zürcher Kantonalbank", "Maples Group", "Ocorian", "Waystone",
    "Euroclear", "Deutsche Börse / Clearstream", "Citi", "JTC Group",
    "FNZ", "SS&C Technologies", "Fidelity International",
    "Rothschild & Co", "BlackRock",
}


class FinancialSourcesV26Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = (json.loads((ROOT / "config/companies.json").read_text()) +
                    json.loads((ROOT / "config/extra_companies.json").read_text()))
        cls.by_name = {r["name"]: r for r in cls.rows}

    def test_284_unique_direct_employers(self):
        self.assertGreaterEqual(len(self.rows), 284)
        self.assertEqual(len(self.by_name), len(self.rows))

    def test_nine_official_ats_have_source_proof_and_exact_owner(self):
        for name, (kind, slug) in ADDED_ATS.items():
            with self.subTest(name=name):
                c = self.by_name[name]
                self.assertEqual(c["verification_level"], "explicit_ats_pending_live_smoke")
                self.assertTrue(c.get("enabled"))
                self.assertEqual(len(c["ats"]), 1)
                target = c["ats"][0]
                self.assertEqual(target["kind"], kind)
                if slug:
                    self.assertEqual(target["slug"], slug)
                    self.assertEqual(urlsplit(c["careers_url"]).path.strip("/").lower(), slug)
                if kind == "workday":
                    self.assertIn(".myworkdayjobs.com", urlsplit(c["careers_url"]).netloc)
                    self.assertEqual(target["url"], c["careers_url"])
                if kind == "oracle_hcm":
                    self.assertEqual(target["site"], "BNY-Careers")
                    self.assertIn("/hcmUI/CandidateExperience/", c["careers_url"])
                evidence = c["origin"].split(": ", 1)[-1]
                self.assertEqual(urlsplit(evidence).scheme, "https")
                self.assertTrue(c["specialism"])

    def test_sixteen_websites_do_not_pretend_to_be_ats(self):
        for name in ADDED_SITES:
            with self.subTest(name=name):
                c = self.by_name[name]
                self.assertTrue(c["careers_url"].startswith("https://"))
                if name == "Euroclear":
                    # v3.11: the official employer site now exposes its Oracle HCM board.
                    self.assertEqual(c["ats"], [{"kind": "oracle_hcm",
                        "site": "CX_1003", "language": "en",
                        "url": c["careers_url"]}])
                    self.assertEqual(c["verification_level"], "official_ats_live_probe_passed")
                    self.assertIn("euroclear.com/careers/en.html", c["origin"])
                else:
                    self.assertFalse(c.get("ats"))
                    self.assertEqual(c["verification_level"],
                                     "official_careers_url_not_necessarily_api")
                    self.assertEqual(c["origin"].split(": ", 1)[-1], c["careers_url"])
                self.assertIn(c["sector"], ("Banca", "Fintech"))


if __name__ == "__main__":
    unittest.main()
