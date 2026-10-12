from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from job_radar.feed import create_rss


class RSSFeedTests(unittest.TestCase):
    def test_only_verified_positions_are_emitted_once_per_fingerprint(self):
        records = [
            {
                "company":"PaymentsTest","title":"KYB Analyst","fingerprint":"ats-requisition-123",
                "apply_url":"https://jobs.ashbyhq.com/paymentstest/123",
                "location":"Spain - Remote","posted_at":"2026-10-12T09:00:00Z",
                "apply_verified_at":"2026-10-12T10:00:00+00:00",
                "first_seen":"2026-10-12T10:00:00+00:00",
            },
            {
                "company":"Unknown","title":"AML Analyst","fingerprint":"old123",
                "apply_url":"https://example.com/job",
                "apply_verified_at":"",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"feed.xml"
            create_rss(records,out_path=str(out))
            root=ET.parse(out).getroot()
            items=root.findall("./channel/item")
            self.assertEqual(len(items),1)
            self.assertEqual(items[0].findtext("guid"),"kyc-radar-ats-requisition-123")
            self.assertEqual(items[0].findtext("title"),"PaymentsTest — KYB Analyst")
            self.assertTrue(items[0].findtext("pubDate"))
            self.assertEqual(items[0].findtext("link"),"https://jobs.ashbyhq.com/paymentstest/123")

    def test_special_characters_escape_without_breaking_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"feed.xml"
            create_rss([{"company":"A&B","title":"AML <Analyst>",
                         "fingerprint":"xyz","apply_verified_at":"2026-10-12",
                         "apply_url":"https://example.com/a?x=1&y=2"}],str(out))
            item=ET.parse(out).getroot().find("./channel/item")
            self.assertEqual(item.findtext("title"),"A&B — AML <Analyst>")


if __name__ == "__main__":
    unittest.main()
