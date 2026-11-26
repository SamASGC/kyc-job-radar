import json,unittest
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,EXTERNAL50_LIVE
from external_live_registry import load_registry
IDS=set(["external-mufg","external-mobilize-rci","external-light-wonder"])
class ResidualWorkdayEnrollmentTests(unittest.TestCase):
    def test_exact_reviewed_routes(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            old=json.loads(z.read("fuentes.json"))["sources"]
        rows=load_registry()
        selected=[r for r in rows if r["id"] in IDS]
        self.assertEqual({r["id"] for r in selected},IDS)
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        for r in selected:
            self.assertIn(r["id"],EXTERNAL50_LIVE)
            self.assertEqual(r["driver"],"generic")
            self.assertEqual(r["route"][0],"workday")
            self.assertGreater(r["audit_artifact"],0)
            self.assertTrue(r["regulatory_reference"].startswith("https://"))
            self.assertTrue(r["hiring_reference"].startswith("https://"))
            self.assertFalse(any(x["id"]==r["id"] or x.get("route")==r["route"] for x in old))
            self.assertEqual(sum(x.get("route")==r["route"] for x in rows),1)
