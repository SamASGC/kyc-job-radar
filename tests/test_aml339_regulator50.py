"""Genuine regulated-company discovery vs live official job monitoring safeguards."""
import json,tempfile,unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.aml339_source_manifest import CORE, EXPANSION, REGULATED, REGULATOR50, REG100_LIVE, OPTIONAL, collect, EXTERNAL50_LIVE
from scripts.aml339_site import build
from batch50_sources import BATCH50
from growth_wave50_sources import WAVE50_B
from alert_history import blank_history, select_and_merge, read_evidence


def evidence(sid, *, registry=None, failed=False):
    data={"mode":"READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
          "total_configured_sources":339,
          "sources":[{
            "source_id":sid,
            "state":"listing_failed" if failed else "listing_extracted",
            "list_complete":not failed,
            "total_listed":0,"relevant_leads":0,"audited":[],
            "unverified_in_scope":0,"listing_role_keys":[],"listing_untrackable_count":0,
          }]}
    if registry:
        data.update(source_registry=registry, original_catalog_sources=339)
    return data


class Regulator50SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory=json.loads(Path("experiments/aml339/regulator50_external_candidates.json").read_text())
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            originals=json.loads(z.read("fuentes.json"))["sources"]
        cls.pinned_ids={row["id"] for row in originals}
        assert len(originals)==len(cls.pinned_ids)==339

    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.core=self.root/"core"
        self.extra=self.root/"extras"
        self.core.mkdir();self.extra.mkdir()
        for sid in CORE:
            self.write(self.core/f"source_{sid}.json",evidence(sid))
        for sid in EXPANSION+BATCH50:
            self.write(self.extra/f"candidate_{sid}.json",evidence(sid))
        for sid in REGULATED:
            self.write(self.extra/f"candidate_{sid}.json",evidence(sid,registry="regulated_emi_sidecar_v1"))
        for sid in REGULATOR50:
            self.write(self.extra/f"candidate_{sid}.json",evidence(sid,registry="regulated_employer_sidecar_v2"))

    @staticmethod
    def write(path,data):
        path.write_text(json.dumps(data),encoding="utf-8")

    def test_exactly_50_new_legal_entity_candidates_and_two_real_ats_sources(self):
        d=self.inventory
        self.assertEqual(d["purpose"],"DISCOVERY_ONLY_NOT_A_LIVE_JOB_MONITOR")
        self.assertEqual(len(d["candidates"]),d["round_size"])
        self.assertEqual(d["round_size"],50)
        ids={row["id"] for row in d["candidates"]}
        self.assertEqual(len(ids),50)
        self.assertFalse(ids & self.pinned_ids)
        self.assertFalse(ids & set(CORE+EXPANSION+BATCH50+REGULATED))
        self.assertTrue(set(REGULATOR50).issubset(ids))
        self.assertEqual(len(CORE+OPTIONAL),152)
        for c in d["candidates"]:
            self.assertEqual(c["live_alerts_enabled"],False)
            self.assertTrue(c["regulatory_discovery_url"].startswith("https://"))
        self.assertEqual(sum(bool(c["careers_url"]) for c in d["candidates"]),10)

    def test_95_sources_are_possible_without_misrepresenting_all_50(self):
        paths,ids,manifest=collect(self.core,self.extra)
        self.assertEqual(len(paths),95)
        self.assertEqual(len(ids),95)
        self.assertEqual(manifest["core_verified"],18)
        self.assertEqual(manifest["expansion_expected"],134)
        self.assertEqual(manifest["regulator50_discovered"],50)
        self.assertEqual(manifest["regulator50_live_expected"],2)
        self.assertEqual(manifest["regulator50_live_verified"],2)
        self.assertEqual(manifest["regulated_external_verified"],5)
        self.assertEqual(manifest["reg100_live_verified"],0)
        history,report=select_and_merge(read_evidence(paths),blank_history(),
            configured_sources=ids,strict_novelty=True,listing_keys={sid:[] for sid in ids})
        self.assertEqual(report["new_counts"],{
            "confirmed_recent":0,"promising_date_unconfirmed":0})
        site=self.root/"site"
        build(paths,history,report,site,manifest)
        summary=json.loads((site/"summary.json").read_text())
        self.assertEqual(summary["sources_complete"],95)
        self.assertEqual(summary["regulator50_discovered"],50)
        self.assertEqual(summary["regulator50_live_expected"],2)
        self.assertEqual(summary["regulator50_live_verified"],2)
        self.assertTrue(summary["novelty_guard_enabled"])

    def test_failed_new_ats_source_keeps_94_others(self):
        sid=REGULATOR50[0]
        self.write(self.extra/f"candidate_{sid}.json",
                   evidence(sid,registry="regulated_employer_sidecar_v2",failed=True))
        paths,ids,manifest=collect(self.core,self.extra)
        self.assertEqual(len(paths),94)
        self.assertEqual(manifest["regulator50_live_verified"],1)
        self.assertEqual(manifest["missing_or_failed_expansion"],{
            sid:"partial_or_failed_listing",
            **{k:"no_live_source_evidence" for k in REG100_LIVE+WAVE50_B+EXTERNAL50_LIVE},
        })
        self.assertNotIn(sid,ids)

    def test_both_new_employers_fail_legacy_93_remain(self):
        for sid in REGULATOR50:
            (self.extra/f"candidate_{sid}.json").unlink()
        paths,ids,manifest=collect(self.core,self.extra)
        self.assertEqual(len(paths),93)
        self.assertEqual(manifest["regulator50_live_verified"],0)
        self.assertEqual(set(manifest["missing_or_failed_expansion"]),set(REGULATOR50)|set(REG100_LIVE)|set(WAVE50_B)|set(EXTERNAL50_LIVE))

    def test_new_entity_cannot_impersonate_old_zip_or_emi_sidecar(self):
        sid=REGULATOR50[0]
        self.write(self.extra/f"candidate_{sid}.json",evidence(sid))
        with self.assertRaisesRegex(ValueError,"newly discovered regulated employer"):
            collect(self.core,self.extra)
        self.write(self.extra/f"candidate_{sid}.json",
                   evidence(sid,registry="regulated_emi_sidecar_v1"))
        with self.assertRaisesRegex(ValueError,"newly discovered regulated employer"):
            collect(self.core,self.extra)

    def test_incomplete_original_mandatory_core_still_stops_publication(self):
        (self.core/f"source_{CORE[0]}.json").unlink()
        with self.assertRaisesRegex(ValueError,"core evidence"):
            collect(self.core,self.extra)


if __name__=="__main__":
    unittest.main()
