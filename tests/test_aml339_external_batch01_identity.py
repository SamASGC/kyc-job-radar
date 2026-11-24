import json,re,unittest
from pathlib import Path
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,EXTERNAL50_LIVE
from external_live_registry import load_registry
class ExternalBatch01Identity(unittest.TestCase):
    def test_no_existing_live_group_alias(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original=json.loads(z.read("fuentes.json"))["sources"]
        rows=load_registry()
        new=[x for x in rows if x.get("audit_run")==45448388827]
        self.assertEqual(len(new),2)
        for r in new:
            for x in original:
                if x["id"] not in set(CORE+OPTIONAL):continue
                label=" ".join([x["id"],x.get("name",""),x.get("careers_url","")]).lower()
                for alias in r["aliases"]:
                    self.assertNotIn(alias,label,(r["id"],x["id"]))
            self.assertTrue(r["regulatory_reference"].startswith("https://www.lb.lt/"))
            self.assertIn(r["id"],EXTERNAL50_LIVE)
