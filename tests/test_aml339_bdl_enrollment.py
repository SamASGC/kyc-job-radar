import unittest
from scripts.aml339_source_manifest import CORE,OPTIONAL,CATALOG_LIVE
from external_live_registry import load_registry
class BDLTest(unittest.TestCase):
    def test_exact_identity(self):
        rows=load_registry()
        r=next(x for x in rows if x["id"]=="banque-de-luxembourg")
        self.assertIn(r["id"],CATALOG_LIVE)
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        self.assertEqual(r["driver"],"catalog")
        self.assertEqual(r["audit_artifact"],15146820009)
