import json,unittest
from pathlib import Path
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,CATALOG_LIVE,EXTERNAL50_LIVE,DYNAMIC_LIVE
from external_live_registry import load_registry,matrix
class CatalogRegistryTests(unittest.TestCase):
    def test_audited_original_sources_distinct_from_external(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            rows=json.loads(z.read("fuentes.json"))["sources"]
        original={x["id"]:x for x in rows}
        self.assertEqual(len(original),339)
        self.assertTrue(set(CATALOG_LIVE).issubset(original))
        self.assertFalse(set(EXTERNAL50_LIVE)&set(original))
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        promoted=[r for r in load_registry() if r["audit_run"]==45459697155]
        self.assertEqual(len(promoted),43)
        for r in promoted:
            self.assertEqual(r["driver"],"catalog")
            self.assertEqual(r["audit_artifact"],14950514515)
            self.assertNotIn("workable",str(original[r["id"]].get("route",[])).lower())
        self.assertFalse({"melio","gohenry","nexo","visa-currencycloud","capimoney","lt-paystrax-official-external","lt-nayax-global-legal-compliance"}&set(CATALOG_LIVE))
    def test_dynamic_dispatch_and_reporting(self):
        self.assertEqual(set(x["source"] for x in matrix()["include"]),set(DYNAMIC_LIVE))
        workflow=Path(".github/workflows/aml339_main18.yml").read_text()
        self.assertIn('elif [[ "$DRIVER" == "catalog" ]]',workflow)
        self.assertIn("live_catalog_registry.py --source",workflow)
