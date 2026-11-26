import json,unittest
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,CATALOG_LIVE,EXTERNAL50_LIVE
from external_live_registry import load_registry
class Wave3EnrollmentTests(unittest.TestCase):
    def test_exact_reviewed_ids_and_group_unique(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original={x["id"]:x for x in json.loads(z.read("fuentes.json"))["sources"]}
        rows=load_registry()
        selected=[r for r in rows if r["audit_run"]==45734320464]
        self.assertEqual({r["id"] for r in selected},set(["dinotech","betsson","external-flutter-international","external-lgt-bank"]))
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        for r in selected:
            self.assertGreater(r["audit_artifact"],0)
            self.assertTrue(r["regulatory_reference"].startswith("https://"))
            self.assertTrue(r["hiring_reference"].startswith("https://"))
            sid=r["id"]
            if r["driver"]=="catalog":
                self.assertIn(sid,CATALOG_LIVE)
                self.assertEqual(sum(original[x]["route"]==original[sid]["route"] for x in set(CORE+OPTIONAL)&set(original)),1)
            else:
                self.assertIn(sid,EXTERNAL50_LIVE)
                self.assertFalse(any(x["route"]==r["route"] for x in original.values()))
                self.assertEqual(sum(x.get("route")==r["route"] for x in rows),1)
        self.assertNotIn("external-lgt-capital-partners",{x["id"] for x in rows})
