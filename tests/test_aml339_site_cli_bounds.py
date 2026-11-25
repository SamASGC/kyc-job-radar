"""Regression: the site CLI must accept all 145 fully checked source paths.

The standalone build() unit tests previously missed an obsolete CLI 97-source
limit and blocked an otherwise valid 145-source production publish.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import aml339_site
from scripts.aml339_source_manifest import CORE, OPTIONAL, STRICT_CORE


class SiteCLIUpperBoundTests(unittest.TestCase):
    def invoke(self,n,has_manifest=True):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            listing=root/"sources.txt"
            listing.write_text("\n".join(f"source_{i}.json" for i in range(n))+"\n",encoding="utf-8")
            for name in ["history.json","report.json","manifest.json"]:
                (root/name).write_text("{}\n",encoding="utf-8")
            args=["aml339_site.py","--sources-file",str(listing),
                  "--state-file",str(root/"history.json"),
                  "--report-file",str(root/"report.json"),
                  "--dest",str(root/"out")]
            if has_manifest:
                args.extend(["--manifest-file",str(root/"manifest.json")])
            with patch("sys.argv",args),patch.object(aml339_site,"build") as build:
                aml339_site.main()
                self.assertEqual(build.call_count,1)
                paths=build.call_args.args[0]
                self.assertEqual(len(paths),n)

    def test_real_145_sources_are_allowed_by_cli(self):
        self.invoke(145)

    def test_future_maximum_registry_is_allowed_by_cli(self):
        self.invoke(len(CORE+OPTIONAL))

    def test_payabl_degraded_seventeen_core_allowed_with_manifest(self):
        self.invoke(17)

    def test_extra_source_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError,"Expected complete strict core"):
            self.invoke(len(CORE+OPTIONAL)+1)

    def test_too_small_unverified_core_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"Expected complete strict core"):
            self.invoke(len(STRICT_CORE)-1)

    def test_two_quarantined_core_allowed_with_manifest(self):
        self.invoke(len(STRICT_CORE))

    def test_legacy_18_source_preview_without_manifest_is_still_possible(self):
        self.invoke(18,False)


if __name__=="__main__":
    unittest.main()
