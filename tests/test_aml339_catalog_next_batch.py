import json,unittest
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,CATALOG_LIVE,EXTERNAL50_LIVE
from external_live_registry import load_registry

class NextCatalogBatchTests(unittest.TestCase):
    def test_new_sources_use_distinct_official_routes_and_audited_evidence(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original={x["id"]:x for x in json.loads(z.read("fuentes.json"))["sources"]}
        rows=[r for r in load_registry() if r["audit_run"]==45462680827]
        self.assertEqual(len(rows),27)
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        for r in rows:
            self.assertIn(r["id"],CATALOG_LIVE)
            self.assertGreater(r["audit_artifact"],0)
            route=original[r["id"]]["route"]
            self.assertFalse(any(x in str(route).lower() for x in ("workable","sage.hr","linkedin.com")))
            self.assertEqual(sum(original[x]["route"]==route for x in set(CORE+OPTIONAL)&set(original)),1)
        a=next(r for r in load_registry() if r["id"]=="reg100-cy-altery-eu-limited-formerly-named-heado-limited")
        self.assertIn(a["id"],EXTERNAL50_LIVE)
        self.assertEqual(a["audit_run"],45462936034)
        self.assertEqual(a["audit_artifact"],14953181538)
        self.assertFalse(any("altery" in (x.get("id","")+" "+x.get("name","")).lower() for x in original.values() if x["id"] in set(CORE+OPTIONAL)))
