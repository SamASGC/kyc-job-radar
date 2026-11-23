"""Out-of-original-339 EMI sources must be independently complete and truthfully named."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.aml339_source_manifest import CORE, EXPANSION, REGULATED, collect
from batch50_sources import BATCH50
from scripts.aml339_site import build
from alert_history import blank_history, select_and_merge, read_evidence


def snapshot(sid, *,external=False,failed=False):
    data={"total_configured_sources":339,
          "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
          "sources":[{
              "source_id":sid, "state":"listing_failed" if failed else "listing_extracted",
              "list_complete":not failed, "relevant_leads":0,"audited":[],
              "unverified_in_scope":0,
              "listing_role_keys":[],"listing_untrackable_count":0,"total_listed":0
          }]}
    if external:
        data.update(source_registry="regulated_emi_sidecar_v1",
                    original_catalog_sources=339)
    return data


class RegulatedEMISidecarTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.core=self.root/"core"
        self.extra=self.root/"extra"
        self.core.mkdir()
        self.extra.mkdir()
        for sid in CORE:
            self.write(self.core/f"source_{sid}.json",snapshot(sid))
        for sid in EXPANSION:
            self.write(self.extra/f"candidate_{sid}.json",snapshot(sid))
        for sid in REGULATED:
            self.write(self.extra/f"candidate_{sid}.json",snapshot(sid,external=True))

    @staticmethod
    def write(path,data):
        path.write_text(json.dumps(data),encoding="utf-8")

    def test_five_truly_external_sources_expand_to_43_with_history_preserved(self):
        paths,ids,manifest=collect(self.core,self.extra)
        self.assertEqual(len(paths),43)
        self.assertEqual(manifest["core_verified"],18)
        self.assertEqual(manifest["expansion_expected"],75)
        self.assertEqual(manifest["regulated_external_expected"],5)
        self.assertEqual(manifest["regulated_external_verified"],5)
        self.assertEqual(set(manifest["regulated_external_ids"]),set(REGULATED))
        self.assertEqual(manifest["configured_original"],339)
        self.assertEqual(set(ids),set(CORE+EXPANSION+REGULATED))
        history,report=select_and_merge(read_evidence(paths),blank_history(),
                                        configured_sources=ids)
        build(paths,history,report,self.root/"site",manifest)
        summary=json.loads((self.root/"site"/"summary.json").read_text())
        self.assertEqual(summary["sources_complete"],43)
        self.assertEqual(summary["original_catalog_sources"],339)
        self.assertEqual(summary["external_regulated_sources_verified"],5)

    def test_external_provider_failure_keeps_original_38_operational(self):
        sid="emi-zen-lt"
        self.write(self.extra/f"candidate_{sid}.json",
                   snapshot(sid,external=True,failed=True))
        paths,ids,manifest=collect(self.core,self.extra)
        self.assertEqual(len(paths),42)
        self.assertEqual(manifest["regulated_external_verified"],4)
        self.assertEqual(manifest["missing_or_failed_expansion"],{
            sid:"partial_or_failed_listing",
            **{item:"no_live_source_evidence" for item in BATCH50}})

    def test_no_sidecar_files_keeps_original_38_operational(self):
        for sid in REGULATED:
            (self.extra/f"candidate_{sid}.json").unlink()
        paths,ids,manifest=collect(self.core,self.extra)
        self.assertEqual(len(paths),38)
        self.assertEqual(manifest["regulated_external_verified"],0)
        self.assertEqual(set(manifest["missing_or_failed_expansion"]),set(REGULATED)|set(BATCH50))

    def test_fake_sidecar_claiming_original_catalog_is_rejected(self):
        sid="emi-zen-lt"
        self.write(self.extra/f"candidate_{sid}.json",snapshot(sid))
        with self.assertRaisesRegex(ValueError,"external EMI registry"):
            collect(self.core,self.extra)

    def test_original_cannot_claim_external_registry(self):
        sid=EXPANSION[0]
        self.write(self.extra/f"candidate_{sid}.json",snapshot(sid,external=True))
        with self.assertRaisesRegex(ValueError,"mismatched source"):
            collect(self.core,self.extra)

    def test_incomplete_core_still_blocks_everything(self):
        (self.core/f"source_{CORE[0]}.json").unlink()
        with self.assertRaisesRegex(ValueError,"core evidence"):
            collect(self.core,self.extra)


if __name__=="__main__":
    unittest.main()
