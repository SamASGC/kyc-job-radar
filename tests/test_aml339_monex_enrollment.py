import unittest
from scripts.aml339_source_manifest import CORE,OPTIONAL,EXTERNAL50_LIVE
from external_live_registry import load_registry
class MonexEnrollmentTests(unittest.TestCase):
    def test_exact_identity(self):
        rows=load_registry()
        r=next(x for x in rows if x["id"]=="external-monex-europe")
        self.assertIn(r["id"],EXTERNAL50_LIVE)
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        self.assertEqual(r["route"],["workday","monex.wd3.myworkdayjobs.com","Careers"])
        self.assertEqual(sum(x.get("route")==r["route"] for x in rows),1)
        self.assertEqual(r["audit_artifact"],15159829191)
