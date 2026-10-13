"""v2.9 direct bank and capital markets coverage regressions."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ATS = {
    "Lightspark": ("ashby", "lightspark"),
    "iCapital": ("greenhouse", "icapitalnetwork"),
    "Digital Asset": ("greenhouse", "digitalassetcorp"),
    "21shares": ("greenhouse", "21shares"),
    "Alpha Financial Markets Consulting": ("greenhouse", "alphafmcroles"),
    "Petra Funds Group": ("greenhouse", "petrafundsgroup"),
    "Securitize": ("greenhouse", "securitize"),
    "Kota": ("ashby", "kota"),
    "Capi Money": ("ashby", "capimoney"),
    "Bitstack": ("ashby", "bitstack"),
    "GetGround": ("ashby", "getground"),
    "CertiK": ("lever", "certik"),
    "Wahed": ("lever", "wahed.com"),
    "Diligent Corporation": ("greenhouse", "diligentcorporation"),
}
BANKS = {
    "Artea Bank", "VP Bank Group", "Arab Bank Switzerland",
    "EFG International", "Banque Internationale à Luxembourg", "Bank Frick",
}


class DirectFinancial350Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = (json.loads((ROOT/"config/companies.json").read_text()) +
                    json.loads((ROOT/"config/extra_companies.json").read_text()))
        cls.by_name = {x["name"].casefold(): x for x in cls.rows}

    def test_350_unique_direct_sources_and_126_ats(self):
        self.assertEqual(len(self.rows), 350)
        self.assertEqual(len(self.by_name), 350)
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.rows), 126)

    def test_exact_provider_origin_and_board_identifier(self):
        for name, (kind, slug) in ATS.items():
            with self.subTest(name=name):
                c = self.by_name[name.casefold()]
                self.assertTrue(c["enabled"])
                self.assertEqual(c["ats"], [{"kind": kind, "slug": slug}])
                self.assertEqual(c["verification_level"], "explicit_ats_pending_live_smoke")
                self.assertIn(c["sector"], {"Banca", "Fintech", "Payments"})
                url = urlsplit(c["careers_url"])
                proof = urlsplit(c["origin"].split(": ", 1)[1])
                host = {"greenhouse": "job-boards.greenhouse.io",
                        "ashby": "jobs.ashbyhq.com",
                        "lever": "jobs.lever.co"}[kind]
                self.assertEqual(url.scheme, "https")
                self.assertEqual(url.hostname, host)
                self.assertEqual(proof.hostname, host)
                self.assertEqual(url.path.strip("/"), slug)
                self.assertEqual(proof.path.strip("/").split("/")[0], slug)

    def test_six_official_bank_portals_not_mislabelled_ats(self):
        for name in BANKS:
            with self.subTest(name=name):
                c = self.by_name[name.casefold()]
                self.assertTrue(c["enabled"])
                self.assertFalse(c.get("ats"))
                self.assertEqual(c["sector"], "Banca")
                self.assertEqual(c["verification_level"],
                                 "official_careers_url_not_necessarily_api")
                self.assertEqual(urlsplit(c["careers_url"]).scheme, "https")
                self.assertIn(c["careers_url"], c["origin"])

    def test_no_existing_employer_identity_collisions(self):
        self.assertEqual(len(ATS), 14)
        self.assertEqual(len(BANKS), 6)
        self.assertTrue(set(n.casefold() for n in ATS).isdisjoint(
            set(n.casefold() for n in BANKS)
        ))


if __name__ == "__main__":
    unittest.main()
