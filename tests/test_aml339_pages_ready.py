"""GitHub Pages deployment waits for real artifact visibility, not upload completion."""
import io
import unittest
from unittest.mock import patch

from scripts.aml339_pages_ready import has_current_pages_artifact, wait_for_upload


class PagesArtifactReadinessTests(unittest.TestCase):
    def test_large_scan_requests_only_the_pages_artifact_from_the_current_run(self):
        data = b'{"total_count": 1, "artifacts": [{"name":"github-pages","id":13,"expired":false}]}'
        with patch("urllib.request.urlopen", return_value=io.BytesIO(data)) as fetch:
            wait_for_upload("owner/repo", "123", "test-token-123", attempts=1)
        self.assertEqual(fetch.call_args.args[0].full_url,
                         "https://api.github.com/repos/owner/repo/actions/runs/123/artifacts"
                         "?name=github-pages&per_page=100")

    def test_no_artifact_means_wait(self):
        self.assertFalse(has_current_pages_artifact({"total_count": 0, "artifacts": []}))

    def test_complete_single_pages_artifact_allows_deployment(self):
        self.assertTrue(has_current_pages_artifact({
            "total_count": 2, "artifacts": [
                {"name": "aml339-main18-audit", "id": 12, "expired": False},
                {"name": "github-pages", "id": 13, "expired": False}
            ],
        }))

    def test_reject_expired_malformed_duplicate_artifact(self):
        self.assertFalse(has_current_pages_artifact({
            "total_count": 1, "artifacts": [
                {"name": "github-pages", "id": 13, "expired": True}
            ],
        }))
        with self.assertRaises(ValueError):
            has_current_pages_artifact({})
        with self.assertRaises(ValueError):
            has_current_pages_artifact({"total_count": 100, "artifacts": []})
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            has_current_pages_artifact({
                "total_count": 2, "artifacts": [
                    {"name": "github-pages", "id": 13, "expired": False},
                    {"name": "github-pages", "id": 14, "expired": False}
                ],
            })


if __name__ == "__main__":
    unittest.main()
