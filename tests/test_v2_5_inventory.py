"""Direct company counts must not include one-off rotating registry batches."""
import tempfile
import unittest
from pathlib import Path

from job_radar.source_inventory import build_source_inventory, summarize_source_coverage


class DirectInventoryTests(unittest.TestCase):
    def test_direct_watchlist_is_separate_from_rotating_discovery(self):
        companies = [
            {"name": "Direct Bank", "careers_url": "https://bank.example/jobs",
             "sector": "Banca", "ats": [{"kind": "greenhouse", "slug": "bank"}]},
            {"name": "Rotating Payments", "careers_url": "https://pay.example/jobs",
             "sector": "Payments"},
            {"name": "Rotating Fund", "careers_url": "https://fund.example/jobs",
             "sector": "Fintech"},
        ]
        health = [
            {"company": "Direct Bank", "ok": True, "jobs": 2},
            {"company": "Rotating Payments", "ok": False, "jobs": 0},
            {"company": "Rotating Fund", "ok": True, "jobs": 1},
        ]
        result = summarize_source_coverage(
            companies, health, direct_company_names={"direct bank"}
        )
        self.assertEqual(result["total_configured_checked_or_scheduled"], 3)
        self.assertEqual(result["direct_configured"], 1)
        self.assertEqual(result["rotating_checked"], 2)
        self.assertEqual(
            [r["origin_class"] for r in result["sources"]],
            ["direct", "rotating", "rotating"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            build_source_inventory(companies, health, out_dir=tmp,
                                   direct_company_names={"direct bank"})
            html = (Path(tmp) / "sources.html").read_text()
            self.assertIn("Empresas directas: 1", html)
            self.assertIn("Rotatorias incluidas: 2", html)


if __name__ == "__main__":
    unittest.main()
