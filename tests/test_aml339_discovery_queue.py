"""Never promote unevaluated outside-catalog sources or violate a Workable rate limit."""
import datetime as dt
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from scripts.aml339_source_manifest import CORE, EXPANSION


class OfficialDiscoveryQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(Path("experiments/aml339/official_fintech_discovery_queue.json").read_text(encoding="utf-8"))

    def test_new_careers_are_not_misrepresented_as_active(self):
        d=self.data
        self.assertEqual(d["status"], "RESEARCH_ONLY_NOT_IN_ACTIVE_MONITOR")
        self.assertEqual(d["original_catalog_sources"], 339)
        ids={r["id"] for r in d["outside_original_catalog"]}
        self.assertEqual(ids,{"trumia","paymont"})
        self.assertFalse(ids & (set(CORE)|set(EXPANSION)))
        for r in d["outside_original_catalog"]:
            self.assertEqual(r["integration"],"NOT_MONITORED_ADAPTER_PENDING")
            self.assertEqual(urlsplit(r["official_board"]).scheme,"https")
            self.assertEqual(urlsplit(r["official_job_evidence"]).scheme,"https")

    def test_colibrix_remains_unmonitored_during_429_cooldown(self):
        d=self.data["preconfigured_but_temporarily_deferred"]
        self.assertEqual(len(d),1)
        r=d[0]
        self.assertEqual(r["id"],"colibrix-one")
        self.assertNotIn("colibrix-one",CORE+EXPANSION)
        self.assertEqual(r["integration"],"DEFERRED_NOT_ACTIVE_NEVER_BYPASS_COOLDOWN")
        t=dt.datetime.fromisoformat(r["do_not_probe_before_utc"].replace("Z","+00:00"))
        self.assertGreater(t,dt.datetime(2026,11,24,2,35,tzinfo=dt.timezone.utc))


if __name__=="__main__":
    unittest.main()
