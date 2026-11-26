import json,unittest
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,CATALOG_LIVE
from external_live_registry import load_registry
class HiringFirstEnrollmentTests(unittest.TestCase):
    def test_reviewed_original_routes_unique(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original={x["id"]:x for x in json.loads(z.read("fuentes.json"))["sources"]}
        rows=[r for r in load_registry() if r["audit_run"]==45731536703 and r["driver"]=="catalog"]
        self.assertEqual(set(r["id"] for r in rows),["vontobel","state-street","northern-trust","robinhood","pwc-experienced","guidehouse","capco","loyens-loeff"] and set(["vontobel","state-street","northern-trust","robinhood","pwc-experienced","guidehouse","capco","loyens-loeff"]))
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        for r in rows:
            sid=r["id"]
            self.assertIn(sid,CATALOG_LIVE)
            self.assertGreater(r["audit_artifact"],0)
            self.assertTrue(r["hiring_reference"].startswith("https://"))
            route=original[sid]["route"]
            self.assertNotIn("workable",str(route).lower())
            self.assertEqual(sum(original[x]["route"]==route for x in set(CORE+OPTIONAL)&set(original)),1)
            if sid in ("vontobel","state-street","northern-trust","robinhood"):
                self.assertTrue(r["regulatory_reference"].startswith("https://"))
