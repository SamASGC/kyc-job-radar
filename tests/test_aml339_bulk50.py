"""Wave of exactly 50 fully audited official fintech job sources, not license claims."""
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.aml339_source_manifest import CORE, EXPANSION, REGULATED, REGULATOR50, REG100_LIVE, OPTIONAL, collect, EXTERNAL50_LIVE
from batch50_sources import BATCH50
from growth_wave50_sources import WAVE50_B
from scripts.aml339_site import build
from alert_history import blank_history, select_and_merge, read_evidence


def evidence(sid, external=False, failed=False):
    result={
      "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
      "total_configured_sources":339,
      "sources":[{
         "source_id":sid,
         "state":"listing_failed" if failed else "listing_extracted",
         "list_complete":not failed,
         "total_listed":0,
         "relevant_leads":0,"audited":[],
         "listing_role_keys":[],"listing_untrackable_count":0,
         "unverified_in_scope":0
      }],
    }
    if external:
        result.update(source_registry="regulated_emi_sidecar_v1",original_catalog_sources=339)
    return result


class Bulk50EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original=json.loads(z.read("fuentes.json"))["sources"]
        cls.pinned={row["id"] for row in original}
        assert len(original)==len(cls.pinned)==339

    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.core=self.root/"core"
        self.optional=self.root/"optional"
        self.core.mkdir()
        self.optional.mkdir()
        for sid in CORE:
            self.write(self.core/f"source_{sid}.json",evidence(sid))
        for sid in EXPANSION+BATCH50:
            self.write(self.optional/f"candidate_{sid}.json",evidence(sid))
        for sid in REGULATED:
            self.write(self.optional/f"candidate_{sid}.json",evidence(sid,external=True))

    def write(self,path,payload):
        path.write_text(json.dumps(payload),encoding="utf-8")

    def test_exactly_50_reliable_original_catalog_sources_without_overlaps(self):
        self.assertEqual(len(BATCH50),50)
        self.assertEqual(len(set(BATCH50)),50)
        self.assertTrue(set(BATCH50).issubset(self.pinned))
        self.assertFalse(set(BATCH50)&set(CORE+EXPANSION+REGULATED))
        self.assertEqual(len(OPTIONAL),129+len(EXTERNAL50_LIVE))
        self.assertEqual(len(CORE+OPTIONAL),147+len(EXTERNAL50_LIVE))

    def test_93_source_site_from_verified_evidence_and_zero_false_new_alerts(self):
        paths,ids,manifest=collect(self.core,self.optional)
        self.assertEqual(len(paths),93)
        self.assertEqual(len(ids),93)
        self.assertEqual(len(set(ids)),93)
        self.assertEqual(manifest["core_verified"],18)
        self.assertEqual(manifest["bulk50_expected"],50)
        self.assertEqual(manifest["bulk50_verified"],50)
        self.assertEqual(manifest["regulated_external_verified"],5)
        self.assertEqual(manifest["configured_original"],339)
        before=blank_history()
        prior,first=select_and_merge(
            read_evidence(paths),before,
            configured_sources=ids,strict_novelty=True,
            listing_keys={sid:[] for sid in ids},
        )
        self.assertEqual(first["new_counts"],{
           "confirmed_recent":0,"promising_date_unconfirmed":0,
        })
        next_state,replay=select_and_merge(
            read_evidence(paths),prior,
            configured_sources=ids,strict_novelty=True,
            listing_keys={sid:[] for sid in ids},
        )
        self.assertEqual(replay["new_counts"],first["new_counts"])
        self.assertEqual(len(next_state["novelty"]["baselined_sources"]),93)
        out=self.root/"site"
        build(paths,next_state,replay,out,manifest)
        summary=json.loads((out/"summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["sources_complete"],93)
        self.assertEqual(summary["bulk50_expected"],50)
        self.assertEqual(summary["bulk50_verified"],50)
        self.assertTrue(summary["novelty_guard_enabled"])
        self.assertEqual(summary["new_counts"],first["new_counts"])

    def test_single_wave50_portal_failure_preserves_all_92_other_sources(self):
        sid=BATCH50[7]
        self.write(self.optional/f"candidate_{sid}.json",evidence(sid,failed=True))
        paths,ids,manifest=collect(self.core,self.optional)
        self.assertEqual(len(paths),92)
        self.assertEqual(manifest["bulk50_verified"],49)
        self.assertEqual(manifest["missing_or_failed_expansion"],{
            sid:"partial_or_failed_listing",
            **{reg:"no_live_source_evidence" for reg in REGULATOR50+REG100_LIVE+WAVE50_B+EXTERNAL50_LIVE},
        })
        self.assertTrue(set(CORE+EXPANSION+REGULATED).issubset(ids))
        self.assertNotIn(sid,ids)

    def test_all_wave50_unavailable_keeps_prior_43_and_baselines(self):
        for sid in BATCH50:
            (self.optional/f"candidate_{sid}.json").unlink()
        paths,ids,manifest=collect(self.core,self.optional)
        self.assertEqual(len(paths),43)
        self.assertEqual(manifest["bulk50_verified"],0)
        self.assertEqual(set(manifest["missing_or_failed_expansion"]),set(BATCH50)|set(REGULATOR50)|set(REG100_LIVE)|set(WAVE50_B)|set(EXTERNAL50_LIVE))
        self.assertEqual(manifest["regulated_external_verified"],5)

    def test_truncated_aggregate_archive_never_impersonates_50_complete_sources(self):
        path=self.optional/f"candidate_{BATCH50[0]}.json"
        data=json.loads(path.read_text())
        data["sources"][0]["relevant_leads"]=2
        self.write(path,data)
        paths,ids,manifest=collect(self.core,self.optional)
        self.assertEqual(len(paths),92)
        self.assertNotIn(BATCH50[0],ids)
        self.assertEqual(manifest["missing_or_failed_expansion"][BATCH50[0]],
                         "incomplete_role_detail_audit")


if __name__=="__main__":
    unittest.main()
