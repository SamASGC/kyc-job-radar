import json,unittest
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,CATALOG_LIVE,EXTERNAL50_LIVE
from external_live_registry import load_registry
class ResidualBatchTests(unittest.TestCase):
    def test_reviewed_sources_and_regulated_group(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            original={x["id"]:x for x in json.loads(z.read("fuentes.json"))["sources"]}
        rows=[r for r in load_registry() if r["audit_run"]==45467942426]
        self.assertEqual(len(rows),16)
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        for r in rows:
            self.assertIn(r["id"],CATALOG_LIVE)
            self.assertGreater(r["audit_artifact"],0)
            route=original[r["id"]]["route"]
            self.assertFalse(any(x in str(route).lower() for x in ("workable","sage.hr","linkedin.com")))
            self.assertEqual(sum(original[x]["route"]==route for x in set(CORE+OPTIONAL)&set(original)),1)
        row=next(x for x in load_registry() if x["id"]=="external-monese-group")
        self.assertIn(row["id"],EXTERNAL50_LIVE)
        self.assertEqual(row["audit_artifact"],14955797290)
        self.assertIn("agent of PPS EU",row["eea_regulatory_note"])
        self.assertFalse(any(any(a in (x["id"]+" "+x.get("name","")).lower() for a in ("monese","pockit")) for x in original.values()))
