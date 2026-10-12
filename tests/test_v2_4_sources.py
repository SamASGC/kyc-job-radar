"""Guard new employer sources against invented board IDs and duplicates."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit


class V24FinancialSourcesTests(unittest.TestCase):
    def test_nine_new_direct_sources_have_evidence_and_unique_names(self):
        root = Path(__file__).resolve().parents[1]
        companies = json.loads((root / "config/companies.json").read_text())
        extra = json.loads((root / "config/extra_companies.json").read_text())
        names = [x["name"].casefold() for x in companies + extra]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(names), 242)
        expected = {
            "Paytm": ("lever", "paytm"),
            "Aspora": ("ashby", "Aspora"),
            "LHV Bank": ("greenhouse", "lhvuk"),
            "Wolt": ("greenhouse", "wolt"),
            "Bondora": ("greenhouse", "bondora"),
            "Boku": ("greenhouse", "boku"),
            "Apron": ("ashby", "apron"),
            "Seccl": ("ashby", "seccl"),
            "Creem": ("ashby", "creem"),
        }
        indexed = {x["name"]: x for x in companies + extra}
        for name, (provider, slug) in expected.items():
            with self.subTest(company=name):
                c = indexed[name]
                self.assertTrue(c["enabled"])
                self.assertEqual(c["ats"], [{"kind": provider, "slug": slug}])
                self.assertEqual(
                    c["verification_level"], "official_ats_job_page_api_pending_smoke"
                )
                proof = c["origin"].split(": ", 1)[1]
                self.assertEqual(urlsplit(proof).scheme, "https")
                self.assertEqual(urlsplit(c["careers_url"]).scheme, "https")
                self.assertIn(slug.casefold(), c["careers_url"].casefold())


if __name__ == "__main__":
    unittest.main()
