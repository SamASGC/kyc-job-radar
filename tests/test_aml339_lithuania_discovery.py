import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request

from experiments.aml339.inspect_regulator50_careers import EmployerRedirects
from scripts.aml339_source_manifest import CORE, OPTIONAL


class LithuanianDiscoveryTests(unittest.TestCase):
    def test_wave_has_unique_authority_profiles_and_no_live_ids(self):
        data = json.loads(Path("experiments/aml339/lithuania_emi_wave01.json").read_text())
        rows = data["candidates"]
        self.assertEqual(len(rows), 50)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertEqual(len({row["regulator_profile"] for row in rows}), len(rows))
        self.assertTrue(all(urlsplit(row["regulator_profile"]).hostname == "www.lb.lt" for row in rows))
        self.assertTrue(set(CORE + OPTIONAL).isdisjoint(row["id"] for row in rows))
        self.assertTrue(all(row["careers_url"] is None or
                            row["careers_url"].startswith("https://") for row in rows))

    def test_employer_page_probe_leaves_external_job_boards_for_separate_review(self):
        handler = EmployerRedirects()
        request = Request("https://example.com/careers")
        same = handler.redirect_request(request, None, 301, "", {}, "https://www.example.com/jobs")
        self.assertEqual(same.full_url, "https://www.example.com/jobs")
        with self.assertRaisesRegex(ValueError, "External redirect"):
            handler.redirect_request(request, None, 301, "", {}, "https://external.example/jobs")
