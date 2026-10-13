"""Protect 330-source employer coverage and verified ATS identity."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
EMPLOYERS = {
    "Capital on Tap": ("greenhouse", "capitalontap"),
    "OpenFX": ("greenhouse", "openfx"),
    "Allica Bank": ("ashby", "allica-bank"),
    "Incard": ("ashby", "incard"),
    "Verifone": ("greenhouse", "verifone"),
    "Blockstream": ("ashby", "blockstream"),
    "Sotheby's": ("greenhouse", "sothebys"),
    "Juniper Square": ("ashby", "junipersquare"),
    "EQT Group": ("greenhouse", "eqtpartners"),
    "Aksia": ("greenhouse", "aksia"),
    "Tandem Bank": ("greenhouse", "tandemmoneylimited"),
    "Breeze": ("greenhouse", "breezecash"),
    "Garda Capital Partners": ("greenhouse", "gardacp"),
    "Mercury": ("greenhouse", "mercury"),
    "Bluevine": ("greenhouse", "bluevineus"),
    "Lead Bank": ("ashby", "leadbank"),
    "Nubank": ("ashby", "nubank"),
    "Caruso": ("ashby", "caruso"),
    "Sydecar": ("ashby", "sydecar"),
    "Emigrant Bank": ("greenhouse", "emigrantbank"),
}


class V28EmployerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "config/companies.json").read_text()) + json.loads(
            (ROOT / "config/extra_companies.json").read_text()
        )
        cls.by_name = {e["name"].casefold(): e for e in cls.config}

    def test_330_distinct_direct_employers(self):
        self.assertGreaterEqual(len(self.config), 330)
        self.assertEqual(len(self.by_name), len(self.config))
        self.assertGreaterEqual(sum(bool(c.get("ats")) for c in self.config), 112)

    def test_authentic_specific_ats_board_identity_and_evidence(self):
        for name, (kind, slug) in EMPLOYERS.items():
            with self.subTest(name=name):
                c = self.by_name[name.casefold()]
                self.assertTrue(c["enabled"])
                self.assertEqual(c["sector"] in {"Fintech", "Banca", "Payments"}, True)
                self.assertEqual(c["verification_level"], "explicit_ats_pending_live_smoke")
                self.assertEqual(c["ats"], [{"kind": kind, "slug": slug}])
                proof = c["origin"].split(": ", 1)[1]
                proof_url = urlsplit(proof)
                board_url = urlsplit(c["careers_url"])
                self.assertEqual(proof_url.scheme, "https")
                self.assertEqual(board_url.scheme, "https")
                expected_host = ("job-boards.greenhouse.io"
                                 if kind == "greenhouse" else "jobs.ashbyhq.com")
                self.assertEqual(board_url.hostname, expected_host)
                self.assertEqual(proof_url.hostname, expected_host)
                self.assertEqual(board_url.path.strip("/"), slug)
                self.assertEqual(proof_url.path.strip("/").split("/")[0], slug)

    def test_no_source_crosses_legacy_existing_direct_name(self):
        self.assertEqual(len(EMPLOYERS), 20)
        self.assertTrue(set(x.casefold() for x in EMPLOYERS).issubset(
            self.by_name.keys()
        ))


if __name__ == "__main__":
    unittest.main()
