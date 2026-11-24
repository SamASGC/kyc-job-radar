"""Second 50 company batch: no duplicate sources, false new job, or core loss."""
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from growth_wave50_sources import WAVE50_B
from batch50_sources import BATCH50
from scripts.aml339_source_manifest import (
    EXTERNAL50_LIVE,
    CORE, EXPANSION, REGULATED, REGULATOR50, REG100_LIVE, collect,
)
from scripts.aml339_site import build
from alert_history import blank_history, read_evidence, select_and_merge


def report(sid,registry=None,failed=False):
    envelope={
        "mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "total_configured_sources":339,
        "sources":[{
            "source_id":sid,
            "state":"listing_failed" if failed else "listing_extracted",
            "list_complete":not failed,
            "total_listed":0,"relevant_leads":0,"audited":[],
            "listing_role_keys":[],"listing_untrackable_count":0,
            "unverified_in_scope":0
        }],
    }
    if registry:
        envelope.update(source_registry=registry,original_catalog_sources=339)
    return envelope


class Growth50Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original=json.loads(z.read("fuentes.json"))["sources"]
        cls.known_ids={row["id"] for row in original}
        assert len(original)==len(cls.known_ids)==339

    def setUp(self):
        d=tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root=Path(d.name)
        self.core=self.root/"core"
        self.optional=self.root/"extra"
        self.core.mkdir()
        self.optional.mkdir()
        for sid in CORE:self._write(self.core/f"source_{sid}.json",report(sid))
        for sid in EXPANSION+BATCH50+WAVE50_B:
            self._write(self.optional/f"candidate_{sid}.json",report(sid,registry="original_339"))
        for sid in REGULATED:self._write(self.optional/f"candidate_{sid}.json",report(sid,"regulated_emi_sidecar_v1"))
        for sid in REGULATOR50:self._write(self.optional/f"candidate_{sid}.json",report(sid,"regulated_employer_sidecar_v2"))
        for sid in REG100_LIVE:self._write(self.optional/f"candidate_{sid}.json",report(sid,"regulated_emi_reg100_live_v1"))

    @staticmethod
    def _write(path,value):
        path.write_text(json.dumps(value),encoding="utf-8")

    def test_exactly_50_additional_original_sources_not_current_97(self):
        self.assertEqual(len(WAVE50_B),len(set(WAVE50_B)))
        self.assertEqual(len(WAVE50_B),50)
        self.assertTrue(set(WAVE50_B).issubset(self.known_ids))
        self.assertFalse(set(WAVE50_B)&set(CORE+EXPANSION+BATCH50+REGULATED+REGULATOR50+REG100_LIVE))

    def test_all_147_verifiable_sources_publish_with_zero_manufactured_alerts(self):
        paths,ids,manifest=collect(self.core,self.optional)
        self.assertEqual(len(paths),147)
        self.assertEqual(len(ids),147)
        self.assertEqual(manifest["growth50_expected"],50)
        self.assertEqual(manifest["growth50_verified"],50)
        self.assertEqual(set(manifest["missing_or_failed_expansion"]),set(EXTERNAL50_LIVE))
        initial=blank_history()
        current,preview=select_and_merge(read_evidence(paths),initial,
             configured_sources=ids,strict_novelty=True,listing_keys={k:[] for k in ids})
        self.assertEqual(preview["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":0})
        out=self.root/"site"
        build(paths,current,preview,out,manifest)
        summary=json.loads((out/"summary.json").read_text())
        self.assertEqual(summary["sources_complete"],147)
        self.assertEqual(summary["sources_expected"],150)
        self.assertEqual(summary["growth50_verified"],50)
        again,replay=select_and_merge(read_evidence(paths),current,
             configured_sources=ids,strict_novelty=True,listing_keys={k:[] for k in ids})
        self.assertEqual(replay["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":0})
        self.assertTrue(set(current["records"]).issubset(again["records"]))

    def test_failed_optional_portal_drops_source_not_entire_radar(self):
        sid=WAVE50_B[0]
        self._write(self.optional/f"candidate_{sid}.json",report(sid,"original_339",failed=True))
        paths,ids,manifest=collect(self.core,self.optional)
        self.assertEqual(len(paths),146)
        self.assertEqual(manifest["growth50_verified"],49)
        self.assertEqual(manifest["missing_or_failed_expansion"],{sid:"partial_or_failed_listing", **{x:"no_live_source_evidence" for x in EXTERNAL50_LIVE}})
        self.assertTrue(set(CORE).issubset(ids))
        self.assertNotIn(sid,ids)

    def test_no_second_wave_still_preserves_original_97_sources(self):
        for sid in WAVE50_B:
            (self.optional/f"candidate_{sid}.json").unlink()
        paths,ids,manifest=collect(self.core,self.optional)
        self.assertEqual(len(paths),97)
        self.assertEqual(manifest["growth50_verified"],0)
        self.assertEqual(set(manifest["missing_or_failed_expansion"]),set(WAVE50_B)|set(EXTERNAL50_LIVE))
        self.assertEqual(manifest["reg100_live_verified"],2)

    def test_forged_or_incomplete_role_evidence_is_excluded(self):
        sid=WAVE50_B[-1]
        invalid=report(sid,"original_339")
        invalid["sources"][0]["relevant_leads"]=1
        self._write(self.optional/f"candidate_{sid}.json",invalid)
        paths,ids,manifest=collect(self.core,self.optional)
        self.assertEqual(len(paths),146)
        self.assertEqual(manifest["missing_or_failed_expansion"][sid],
                         "incomplete_role_detail_audit")
        self.assertNotIn(sid,ids)

    def test_a_failed_existing_mandatory_employer_remains_a_hard_failure(self):
        (self.core/f"source_{CORE[0]}.json").unlink()
        with self.assertRaisesRegex(ValueError,"core evidence"):
            collect(self.core,self.optional)


if __name__=="__main__":
    unittest.main()
