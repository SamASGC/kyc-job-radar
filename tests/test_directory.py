from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

from job_radar.directory import load_directory_batch, rotate_company_directory, usable_website
from scripts.import_fintech_directory import parse_directory_csv


class DirectoryTests(unittest.TestCase):
    def test_site_must_be_https(self):
        self.assertTrue(usable_website("https://example.com"))
        self.assertFalse(usable_website("http://example.com"))
        self.assertFalse(usable_website("file:///etc/passwd"))
        self.assertFalse(usable_website("https://localhost"))

    def test_hot_ats_company_revisited(self):
        data = [
            {"name": "A", "website": "https://a.test.com", "priority": 1},
            {"name": "B", "website": "https://b.test.com", "priority": 1},
            {"name": "C", "website": "", "priority": 1},
        ]
        discovered = {"A": {"targets": [{"kind": "ashby", "slug": "a"}]}}
        batch, stats = rotate_company_directory(data, discovered, set(), hour=42, cold_per_hour=1, hot_per_hour=1)
        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[0]["name"], "A")
        self.assertEqual(stats["discovered_ats"], 1)
        self.assertEqual(stats["directory_rows"], 3)

    def test_does_not_revisit_normal_watchlist_names(self):
        data = [
            {"name": "Finom", "website": "https://finom.co"},
            {"name": "Alt Pay", "website": "https://altpay.com"},
        ]
        result, _ = rotate_company_directory(data, {}, {"Finom"}, 1)
        self.assertEqual([r["name"] for r in result], ["Alt Pay"])

    def test_csv_records_without_website_are_catalogued_not_scanned(self):
        with tempfile.TemporaryDirectory() as temp:
            csv = Path(temp) / "sample.csv"
            csv.write_text("Firm name,Website,Country,Sector\nAlt Pay,altpay.com,Spain,Payments\nUnknown,,Lithuania,Banking\n", encoding="utf-8")
            rows = parse_directory_csv(csv)
            self.assertEqual(len(rows), 2)
            self.assertEqual(sum(bool(r["enabled"]) for r in rows), 1)
            self.assertIn("https://altpay.com", [r["website"] for r in rows])


if __name__ == "__main__":
    unittest.main()
