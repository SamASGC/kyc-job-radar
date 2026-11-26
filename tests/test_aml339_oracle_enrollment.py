import unittest
from pathlib import Path
from scripts.aml339_source_manifest import CORE,OPTIONAL,EXTERNAL50_LIVE
from external_live_registry import load_registry
class OracleEnrollmentTests(unittest.TestCase):
    def test_exact_reviewed_route(self):
        rows=load_registry()
        oracle=[r for r in rows if r["driver"]=="oracle"]
        self.assertEqual(len(oracle),1)
        self.assertEqual(oracle[0]["id"],"external-danske-bank")
        self.assertEqual(oracle[0]["route"],["oracle","ejqi.fa.ocs.oraclecloud.eu","CX_1001"])
        self.assertIn(oracle[0]["id"],EXTERNAL50_LIVE)
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        self.assertEqual(oracle[0]["audit_artifact"],15151908244)
    def test_scoped_runtime(self):
        workflow=Path(".github/workflows/aml339_main18.yml").read_text()
        self.assertIn("matrix.driver == 'oracle' && 'ubuntu-24.04' || 'ubuntu-latest'",workflow)
        self.assertIn('if: ${{ matrix.driver == \'oracle\' }}',workflow)
        self.assertIn('python3 live_oracle.py --source "$SOURCE"',workflow)
        self.assertIn('cron: "23 0-6,8-23 * * *"',workflow)
        self.assertIn('cron: "23 7 * * *"',workflow)
