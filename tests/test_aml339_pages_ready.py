"""GitHub Pages deployment waits for real artifact visibility, not upload completion."""
import unittest

from scripts.aml339_pages_ready import has_current_pages_artifact


class PagesArtifactReadinessTests(unittest.TestCase):
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
