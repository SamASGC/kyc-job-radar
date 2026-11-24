"""V1 release is based on PUBLISHED coverage, never on guessed 100 lead readiness."""
import datetime as dt
from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from scripts.aml339_source_manifest import CORE, OPTIONAL
from scripts.aml339_v1_status import check_pages, evaluate, main


class V1ReleaseHealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.discovery=json.loads(Path("experiments/aml339/regulator100_discovery_queue.json").read_text(encoding="utf-8"))

    @staticmethod
    def summary(age=2,source_count=97):
        return {
           "checked_at_utc":(dt.datetime(2026,11,24,3,tzinfo=dt.timezone.utc)
                              -dt.timedelta(hours=age)).isoformat(),
           "sources_complete":source_count,
           "sources_expected":len(CORE+OPTIONAL),
           "core_sources_complete":len(CORE),
           "novelty_guard_enabled":True,
           "regulator50_discovered":50,
           "regulator50_live_expected":2,
           "reg100_research_leads":100,
           "reg100_live_expected":2,
           "reg100_live_verified":2,
           "new_counts":{"confirmed_recent":0,"promising_date_unconfirmed":0}
        }

    def test_exactly_100_research_only_distinct_sources_with_provenance(self):
        d=self.discovery
        self.assertEqual(d["count"],100)
        self.assertEqual(d["prior_regulator50_count"],50)
        self.assertEqual(len(d["candidates"]),100)
        self.assertEqual(len({x["id"] for x in d["candidates"]}),100)
        self.assertIn("CC BY 4.0",d["source"]["attribution"])
        self.assertEqual(d["source"]["source_rows"],999)
        self.assertEqual(d["scope"],"100_EXTRA_COMPANY_DISCOVERY_LEADS_NOT_100_LIVE_ATS_FEEDS")
        for x in d["candidates"]:
            self.assertFalse(x["licence_verified_national_authority"])
            self.assertFalse(x["official_careers_verified"])
            self.assertFalse(x["official_ats_verified"])
            self.assertFalse(x["live_monitoring_enabled"])
            self.assertIsNone(x["website_in_secondary_directory"])
            self.assertTrue(x["regulator_source"].startswith("https://"))
            self.assertTrue(x["licence_reference"])
        self.assertEqual(set(x["country"] for x in d["candidates"]),
           {"LT","MT","LU","ES","IE","NL","BE","LV","CY","PT","FR","DE","CZ","FI","IT"})

    def test_published_fresh_97_source_v1_may_be_verified_without_counting_100(self):
        health=evaluate(self.summary(),self.discovery,
                        now=dt.datetime(2026,11,24,3,tzinfo=dt.timezone.utc))
        self.assertTrue(health["v1_published_verified"])
        self.assertEqual(health["configured_maximum_live_sources"],97)
        self.assertEqual(health["actual_verified_live_sources"],97)
        self.assertEqual(health["100_extra_company_leads_with_verified_active_ats"],2)

    def test_published_34_old_version_is_not_claimed_v1(self):
        raw = {
            "checked_at_utc": "2026-11-23T17:14:53+00:00",
            "sources_complete": 34, "sources_expected": 34, "core_sources_complete": 18,
        }
        health=evaluate(raw,self.discovery,
                        now=dt.datetime(2026,11,24,1,tzinfo=dt.timezone.utc))
        self.assertFalse(health["v1_published_verified"])
        self.assertEqual(health["actual_verified_live_sources"],34)
        self.assertEqual(health["status"],"PENDING_PRODUCTION_VALIDATION")

    def test_public_dashboard_summary_and_both_feeds_must_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("summary.json", "index.html", "confirmed.xml", "review.xml"):
                (root / name).write_bytes(name.encode())

            def read(request, timeout):
                name = request.full_url.rsplit("/", 1)[1]
                if name == "confirmed.xml":
                    raise URLError("service unavailable")
                content = name.encode() + (b" stale" if name == "review.xml" else b"")
                response = io.BytesIO(content)
                response.status = 200
                return response

            with patch("urllib.request.urlopen", side_effect=read):
                results = check_pages(root / "summary.json")
        self.assertEqual(results["summary.json"], "match")
        self.assertEqual(results["index.html"], "match")
        self.assertIn("service unavailable", results["confirmed.xml"])
        self.assertIn("different", results["review.xml"])

    def test_release_status_requires_a_matching_deployment_even_with_full_coverage(self):
        reports = [
            ([], None, "SNAPSHOT_READY_TO_VERIFY"),
            (["--require-live"], "different from committed release", "PENDING_PRODUCTION_VALIDATION"),
            (["--require-live"], "match", "VERIFIED_PRODUCTION"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            out = Path(directory) / "status.json"
            summary = self.summary()
            summary["checked_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
            path.write_text(json.dumps(summary))
            for options, remote, status in reports:
                with self.subTest(status=status), patch("sys.argv", [
                    "health", "--summary", str(path), "--out", str(out), *options,
                ]), patch("scripts.aml339_v1_status.check_pages",
                          return_value={"review.xml": remote}) as check, redirect_stdout(io.StringIO()):
                    if status == "PENDING_PRODUCTION_VALIDATION":
                        with self.assertRaises(SystemExit):
                            main()
                    else:
                        main()
                    self.assertEqual(check.call_count, int(bool(options)))
                    result = json.loads(out.read_text())
                    self.assertEqual(result["status"], status)
                    self.assertEqual(result["v1_published_verified"], status == "VERIFIED_PRODUCTION")

    def test_low_optional_source_coverage_blocks_stable_release(self):
        s=self.summary(source_count=60)
        health=evaluate(s,self.discovery,now=dt.datetime(2026,11,24,3,tzinfo=dt.timezone.utc))
        self.assertFalse(health["v1_published_verified"])
        self.assertEqual(health["minimum_live_sources_for_stable_v1"],90)

    def test_stale_scan_never_claimed_released(self):
        s=self.summary(age=37)
        health=evaluate(s,self.discovery,now=dt.datetime(2026,11,24,3,tzinfo=dt.timezone.utc))
        self.assertFalse(health["fresh_publish"])
        self.assertFalse(health["v1_published_verified"])

    def test_missing_original_core_disables_release(self):
        s=self.summary()
        s["core_sources_complete"]=17
        health=evaluate(s,self.discovery,now=dt.datetime(2026,11,24,3,tzinfo=dt.timezone.utc))
        self.assertFalse(health["v1_published_verified"])

    def test_no_novelty_guard_never_release(self):
        s=self.summary()
        s["novelty_guard_enabled"]=False
        health=evaluate(s,self.discovery,now=dt.datetime(2026,11,24,3,tzinfo=dt.timezone.utc))
        self.assertFalse(health["v1_published_verified"])

    def test_invalid_100_lead_data_fails_closed(self):
        s=self.summary()
        d={**self.discovery,"candidates":[*self.discovery["candidates"][:-1],self.discovery["candidates"][0]]}
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            evaluate(s,d,now=dt.datetime(2026,11,24,3,tzinfo=dt.timezone.utc))
        d={**self.discovery,"candidates":[dict(x) for x in self.discovery["candidates"]]}
        d["candidates"][0]["live_monitoring_enabled"]=True
        with self.assertRaisesRegex(ValueError,"research-only"):
            evaluate(s,d,now=dt.datetime(2026,11,24,3,tzinfo=dt.timezone.utc))

    def test_all_three_pages_workflows_retry_only_deployment(self):
        for name in (".github/workflows/hourly.yml",
                     ".github/workflows/aml339_main18.yml",
                     ".github/workflows/aml339_pages_recovery.yml"):
            wf=Path(name).read_text()
            self.assertIn("id: deployment",wf,name)
            self.assertIn("id: deployment_retry",wf,name)
            self.assertIn("continue-on-error: true\n        uses: actions/deploy-pages@v5",wf,name)
            self.assertIn("if: ${{ steps.deployment.outcome == 'failure' }}".replace("\\",""),wf,name)
            self.assertIn("run: sleep 35",wf,name)
            self.assertIn("steps.deployment_retry.outputs.page_url || steps.deployment.outputs.page_url",wf,name)


if __name__=="__main__":
    unittest.main()
