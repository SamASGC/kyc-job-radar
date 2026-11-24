import unittest,json
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,CATALOG_LIVE
from external_live_registry import load_registry

class FinalCatalogBatchTests(unittest.TestCase):
    def test_reviewed_audited_batch_matches_catalog(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original={x["id"]:x for x in json.loads(z.read("fuentes.json"))["sources"]}
        rows=[x for x in load_registry() if x["audit_run"]==45465435385]
        self.assertEqual(len(rows),26)
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        for r in rows:
            self.assertIn(r["id"],CATALOG_LIVE)
            self.assertGreater(r["audit_artifact"],0)
            route=original[r["id"]]["route"]
            self.assertFalse(any(x in str(route).lower() for x in ("workable","sage.hr","linkedin.com")))
            self.assertEqual(sum(original[x]["route"]==route for x in set(CORE+OPTIONAL)&set(original)),1)
        self.assertTrue({"eneba","fis","fiserv","mastercard","okx","kraken","hopae","nelly"}.issubset({x["id"] for x in rows}))
