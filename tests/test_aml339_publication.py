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


    def test_promotion_changes_rss_lane_without_losing_identity_or_realerting(self):
        old_role = self.roles[0][1]
        old_key = next(iter(self.history["records"]))
        first_seen = self.history["records"][old_key]["first_seen"]
        promoted_role = role_template(
            title=old_role["title"],
            url=old_role["url"],
            evaluation={
                "class": "possible_match_confirmed_recent",
                "publication_status": "fresh",
                "original_posting_date": "2026-11-23T12:00:00+00:00",
                "date_field": "Greenhouse.first_published",
                "uncertainties": [],
            },
        )
        history, report = select_and_merge(
            [("first-source", promoted_role)], self.history, "promotion-run",
            configured_sources=[f"source-{i}" for i in range(18)],
        )
        self.assertEqual(report["new_counts"],
                         {"confirmed_recent": 1, "promising_date_unconfirmed": 0})
        self.assertEqual(list(history["records"]), [old_key])
        self.assertEqual(history["records"][old_key]["first_seen"], first_seen)
        self.assertEqual(set(history["records"][old_key]["delivered_lanes"]),
                         {"confirmed_recent", "promising_date_unconfirmed"})
        self.evidence.write_text(json.dumps({
            "total_configured_sources": 339,
            "sources": [{"source_id": "first-source", "audited": [promoted_role]}]
        }), encoding="utf-8")
        out = self.root / "site"
        aml339_site.build([self.evidence], history, report, out)
        confirmed = ET.fromstring((out / "confirmed.xml").read_text())
        review = ET.fromstring((out / "review.xml").read_text())
        self.assertEqual(len(confirmed.findall("./channel/item")), 1)
        self.assertEqual(len(review.findall("./channel/item")), 0)
        guid = confirmed.findtext("./channel/item/guid")
        self.assertEqual(guid, "aml339:" + old_key + ":confirmed_recent")

        second_history, repeat = select_and_merge(
            [("first-source", promoted_role)], history, "replay",
            configured_sources=[f"source-{i}" for i in range(18)],
        )
        self.assertEqual(repeat["new_counts"],
                         {"confirmed_recent": 0, "promising_date_unconfirmed": 0})
        aml339_site.build([self.evidence], second_history, repeat, out)
        confirmed_again = ET.fromstring((out / "confirmed.xml").read_text())
        self.assertEqual(confirmed_again.findtext("./channel/item/guid"), guid)
        self.assertEqual(len(second_history["records"]), 1)

    def test_history_missing_live_role_never_publishes(self):
        with self.assertRaisesRegex(ValueError, "Missing role"):
            aml339_site.build([self.evidence], blank_history(), self.report,
                              self.root / "out")
        self.assertFalse((self.root / "out").exists())


if __name__ == "__main__":
    unittest.main()
