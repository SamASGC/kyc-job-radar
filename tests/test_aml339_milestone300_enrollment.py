import json,unittest
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,CATALOG_LIVE,EXTERNAL50_LIVE
from external_live_registry import load_registry
class Milestone300EnrollmentTests(unittest.TestCase):
    def test_exact_reviewed_ids_and_group_unique(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original={x["id"]:x for x in json.loads(z.read("fuentes.json"))["sources"]}
        rows=load_registry()
        selected=[r for r in rows if r["id"] in {"leovegasgroup","playson","external-rothschild-co","external-exante"}]
        self.assertTrue(all(r["audit_run"] in {45734320464,45735529488} for r in selected))
        self.assertEqual({r["id"] for r in selected},set(["leovegasgroup","playson","external-rothschild-co","external-exante"]))
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
        self.assertEqual(len(set(CORE+OPTIONAL)),300)
        self.assertEqual(next(r for r in selected if r["id"]=="external-exante")["route"],["greenhouse","boards-api.greenhouse.io","xntltd"])
