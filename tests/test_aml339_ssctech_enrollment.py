import unittest
from pathlib import Path
from scripts.aml339_source_manifest import CORE,OPTIONAL,EXTERNAL50_LIVE
from external_live_registry import load_registry
class SSCEnrollmentTests(unittest.TestCase):
    def test_exact_identity(self):
        rows=load_registry()
        r=next(x for x in rows if x["id"]=="external-ssctech")
        self.assertIn(r["id"],EXTERNAL50_LIVE)
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        self.assertEqual(r["route"],["workday","ssctech.wd1.myworkdayjobs.com","SSCTechnologies"])
        self.assertEqual(sum(x.get("route")==r["route"] for x in rows),1)
        self.assertEqual(r["audit_artifact"],15153193157)
    def test_scoped_selector(self):
        script=Path("experiments/aml339/live_external_generic.py").read_text()
        self.assertIn('if sid=="external-ssctech":',script)
        self.assertIn("audit.candidate=ssc_candidate",script)
        self.assertIn("audit.candidate=previous",script)
