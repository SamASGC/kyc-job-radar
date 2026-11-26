import unittest
from scripts.aml339_source_manifest import CORE,OPTIONAL,EXTERNAL50_LIVE
from external_live_registry import load_registry
IDS=["external-bank-of-china","external-tipico","external-bet365","external-playtech","external-everymatrix"]
class Wave6EnrollmentTests(unittest.TestCase):
    def test_exact_reviewed_ids(self):
        rows=load_registry()
        selected=[r for r in rows if r["id"] in IDS]
        self.assertEqual({r["id"] for r in selected},set(IDS))
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        for r in selected:
            self.assertIn(r["id"],EXTERNAL50_LIVE)
            self.assertEqual(r["driver"],"generic")
            self.assertEqual(sum(x.get("route")==r["route"] for x in rows),1)
            self.assertGreater(r["audit_artifact"],0)
            self.assertTrue(r["regulatory_reference"].startswith("https://"))
            self.assertTrue(r["hiring_reference"].startswith("https://"))
        self.assertEqual(sum(r["route"][0]=="smart_external" for r in selected),4)
