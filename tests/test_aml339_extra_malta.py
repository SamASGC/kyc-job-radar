"""Three new outside-339 Maltese EMI career sources remain separate and official."""
import unittest
from pathlib import Path
from zipfile import ZipFile
import json

from scripts.aml339_source_manifest import CORE, EXPANSION, REGULATED, REGULATOR50, OPTIONAL
from probe_malta_three_new import REGULATED_CANDIDATES
from batch50_sources import BATCH50


class MaltaExtraSourcesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as f:
            src=json.loads(f.read("fuentes.json"))["sources"]
        cls.original={s["id"] for s in src}
        assert len(cls.original)==len(src)==339

    def test_three_new_ids_are_actually_absent_from_original_archive(self):
        three={"emi-andaria-mt","emi-finxp-mt","emi-paydo-mt"}
        self.assertEqual(set(REGULATED_CANDIDATES),three)
        self.assertEqual(set(REGULATED),{"emi-trumia-mt","emi-zen-lt"}|three)
        self.assertFalse(three&self.original)
        self.assertFalse(three&set(CORE+EXPANSION+BATCH50))
        self.assertEqual(len(OPTIONAL),77)
        self.assertEqual(len(CORE+OPTIONAL),95)

    def test_careers_are_owned_official_host_with_real_licence_reference(self):
        for sid, cfg in REGULATED_CANDIDATES.items():
            self.assertEqual(sid,cfg["id"])
            self.assertTrue(cfg["careers_url"].startswith("https://"))
            self.assertTrue(cfg["regulator_evidence"].startswith("https://"))
            self.assertEqual(len(cfg["route"]),3)
            self.assertIn(cfg["route"][0],{"site_jobs","bamboohr"})
            self.assertTrue(cfg["route"][1] in cfg["careers_url"])
            self.assertIn("(MT EMI C",cfg["name"])

    def test_original_339_parser_is_checksum_pinned_and_not_duplicated(self):
        self.assertTrue(Path("experiments/aml339/full_original_339_sources.zip").exists())
        self.assertEqual(len(set(REGULATED)),5)
        self.assertNotIn("colibrix-one",REGULATED)


if __name__=="__main__":
    unittest.main()
