"""Fail-closed publication, HTML escaping and RSS stability for AML339."""
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts import aml339_site
from alert_history import blank_history, select_and_merge
from two_lane_alert_preview import role_template


class AML339PublicationTests(unittest.TestCase):
    def setUp(self):
        self.roles = [("first-source", role_template(title="<script>alert(1)</script>"))]
        self.history, self.report = select_and_merge(
            self.roles, blank_history(), "test-run",
            configured_sources=[f"source-{i}" for i in range(18)]
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.evidence = self.root / "source.json"
        self.evidence.write_text(json.dumps({
            "total_configured_sources": 339,
            "sources": [{"source_id": "first-source", "audited": [self.roles[0][1]]}]
        }), encoding="utf-8")

    def test_publish_escaped_html_and_stable_rss(self):
        output = self.root / "site"
        aml339_site.build([self.evidence], self.history, self.report, output)
        html = (output / "index.html").read_text()
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("Sin envíos de correo automáticos", html)
        feed = ET.fromstring((output / "review.xml").read_text())
        items = feed.findall("./channel/item")
        self.assertEqual(len(items), 1)
        guid = items[0].findtext("guid")
        self.assertTrue(guid.startswith("aml339:"))
        self.assertIn("NO etiquetar como nueva", items[0].findtext("description"))
        self.assertEqual(
            len(ET.fromstring((output / "confirmed.xml").read_text()).findall("./channel/item")), 0
        )
        new_state, replay = select_and_merge(self.roles, self.history, "test-replay",
                                              configured_sources=list(range(18)))
        self.assertEqual(replay["new_counts"], {"confirmed_recent": 0, "promising_date_unconfirmed": 0})
        aml339_site.build([self.evidence], new_state, replay, output)
        feed2 = ET.fromstring((output / "review.xml").read_text())
        self.assertEqual(feed2.findtext("./channel/item/guid"), guid)

    def test_incomplete_scan_never_publishes_or_changes_history(self):
        rejected = dict(self.report, source_count=17)
        with self.assertRaisesRegex(ValueError, "partial"):
            aml339_site.build([self.evidence], self.history, rejected, self.root / "out")
        self.assertFalse((self.root / "out").exists())
        rejected = dict(self.report, qualifying_distinct_roles=0)
        with self.assertRaisesRegex(ValueError, "Mismatch"):
            aml339_site.build([self.evidence], self.history, rejected, self.root / "out")
        self.assertFalse((self.root / "out").exists())


if __name__ == "__main__":
    unittest.main()
