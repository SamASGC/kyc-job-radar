"""V1 regulated-100 sources: ONLY two truly audited official ATS portals promoted."""
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.aml339_source_manifest import CORE, EXPANSION, REGULATED, REGULATOR50, REG100_LIVE, OPTIONAL, collect, DYNAMIC_LIVE, EXTERNAL50_LIVE
from scripts.aml339_site import build
from batch50_sources import BATCH50
from growth_wave50_sources import WAVE50_B
from alert_history import blank_history, read_evidence, select_and_merge

def evidence(sid, registry=None, failed=False):
    obj={"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
         "total_configured_sources":339,
         "sources":[{
             "source_id":sid,
             "state":"listing_failed" if failed else "listing_extracted",
             "list_complete":not failed,
             "relevant_leads":0,"total_listed":0,"audited":[],
             "listing_role_keys":[],"listing_untrackable_count":0,
             "unverified_in_scope":0
         }]}
    if registry:
        obj.update(source_registry=registry,original_catalog_sources=339)
    return obj

class Reg100LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queue=json.loads(Path("experiments/aml339/regulator100_discovery_queue.json").read_text())
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original=json.loads(z.read("fuentes.json"))["sources"]
        cls.original_ids={r["id"] for r in original}
        assert len(original)==len(cls.original_ids)==339

    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.core=self.root/"core"
        self.extra=self.root/"extra"
        self.core.mkdir()
        self.extra.mkdir()
        for sid in CORE:self.write(self.core/f"source_{sid}.json",evidence(sid))
        for sid in EXPANSION+BATCH50:self.write(self.extra/f"candidate_{sid}.json",evidence(sid))
        for sid in REGULATED:self.write(self.extra/f"candidate_{sid}.json",evidence(sid,"regulated_emi_sidecar_v1"))
        for sid in REGULATOR50:self.write(self.extra/f"candidate_{sid}.json",evidence(sid,"regulated_employer_sidecar_v2"))
        for sid in REG100_LIVE:self.write(self.extra/f"candidate_{sid}.json",evidence(sid,"regulated_emi_reg100_live_v1"))

    @staticmethod
    def write(path,data):
        path.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")

    def test_two_original_reg100_sources_and_separate_audited_enrollment(self):
        self.assertEqual(len(self.queue["candidates"]),100)
        self.assertEqual(len(REG100_LIVE),2)
        ids={r["id"] for r in self.queue["candidates"]}
        self.assertTrue(set(REG100_LIVE).issubset(ids))
        self.assertFalse(set(REG100_LIVE) & self.original_ids)
        self.assertEqual(len(set(CORE+OPTIONAL)),147+len(DYNAMIC_LIVE))
        self.assertEqual(len(CORE),18)
        self.assertEqual(len(OPTIONAL),129+len(DYNAMIC_LIVE))
        self.assertNotIn("reg100-ie-currenxie-technologies-limited",OPTIONAL)
        self.assertNotIn("reg100-de-allunity-gmbh",REG100_LIVE)
        if "reg100-de-allunity-gmbh" in OPTIONAL:
            self.assertIn("reg100-de-allunity-gmbh",EXTERNAL50_LIVE)
        self.assertNotIn("reg100-mt-payfuture-fs-mt-ltd",OPTIONAL)

    def test_full_97_source_synthetic_publish_reports_exact_promotion(self):
        paths,ids,manifest=collect(self.core,self.extra)
        self.assertEqual(len(ids),97)
        self.assertEqual(manifest["reg100_live_expected"],2)
        self.assertEqual(manifest["reg100_live_verified"],2)
        self.assertEqual(manifest["reg100_research_leads"],100)
        state,report=select_and_merge(read_evidence(paths),blank_history(),
                 configured_sources=ids,strict_novelty=True,listing_keys={sid:[] for sid in ids})
        build(paths,state,report,self.root/"site",manifest)
        summary=json.loads((self.root/"site"/"summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["sources_complete"],97)
        self.assertEqual(summary["sources_expected"],len(CORE+OPTIONAL))
        self.assertEqual(summary["reg100_research_leads"],100)
        self.assertEqual(summary["reg100_live_verified"],2)
        self.assertTrue(summary["novelty_guard_enabled"])
        self.assertEqual(summary["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":0})

    def test_one_failed_new_ats_keeps_96_others_and_old_history(self):
        sid=REG100_LIVE[0]
        self.write(self.extra/f"candidate_{sid}.json",evidence(sid,"regulated_emi_reg100_live_v1",failed=True))
        paths,ids,manifest=collect(self.core,self.extra)
        self.assertEqual(len(ids),96)
        self.assertEqual(manifest["reg100_live_verified"],1)
        self.assertEqual(manifest["missing_or_failed_expansion"],{
            sid:"partial_or_failed_listing", **{x:"no_live_source_evidence" for x in WAVE50_B+DYNAMIC_LIVE}})
        self.assertTrue(set(CORE+EXPANSION+REGULATED+REGULATOR50).issubset(ids))

    def test_two_missing_employers_preserves_old_95(self):
        for sid in REG100_LIVE:(self.extra/f"candidate_{sid}.json").unlink()
        paths,ids,manifest=collect(self.core,self.extra)
        self.assertEqual(len(paths),95)
        self.assertEqual(manifest["reg100_live_verified"],0)
        self.assertEqual(set(manifest["missing_or_failed_expansion"]),set(REG100_LIVE)|set(WAVE50_B)|set(DYNAMIC_LIVE))

    def test_external_reg100_cannot_impersonate_original_or_previous_sidecar(self):
        sid=REG100_LIVE[0]
        self.write(self.extra/f"candidate_{sid}.json",evidence(sid))
        with self.assertRaisesRegex(ValueError,"regulator100 official ATS"):
            collect(self.core,self.extra)
        self.write(self.extra/f"candidate_{sid}.json",evidence(sid,"regulated_emi_sidecar_v1"))
        with self.assertRaisesRegex(ValueError,"regulator100 official ATS"):
            collect(self.core,self.extra)

    def test_old_18_core_still_mandatory(self):
        (self.core/f"source_{CORE[0]}.json").unlink()
        with self.assertRaisesRegex(ValueError,"core evidence"):
            collect(self.core,self.extra)

if __name__=="__main__":
    unittest.main()
