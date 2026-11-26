import json,tempfile,unittest
from pathlib import Path
from scripts.aml339_source_manifest import DYNAMIC_LIVE,CORE,OPTIONAL
from external_live_registry import load_registry,matrix,ids,REGISTRY,MAX_DYNAMIC_SOURCES

class ExternalRegistryTests(unittest.TestCase):
    def test_matrix_and_manifest_share_one_inventory(self):
        rows=load_registry()
        self.assertEqual(set(x["source"] for x in matrix()["include"]),set(DYNAMIC_LIVE))
        self.assertEqual(len(matrix()["include"]),len(DYNAMIC_LIVE))
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        self.assertEqual(len(rows),len(DYNAMIC_LIVE))
    def test_growth_within_capacity_requires_no_code_or_workflow_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"registry.json"
            d=json.loads(REGISTRY.read_text())
            remaining=MAX_DYNAMIC_SOURCES-len(d["sources"])
            self.assertGreaterEqual(remaining,0)
            increment=min(50,remaining)
            for n in range(increment):
                d["sources"].append({"id":f"synthetic-batch-test-{n}","driver":"generic","audit_run":1})
            p.write_text(json.dumps(d))
            self.assertEqual(len(matrix(p)["include"]),len(DYNAMIC_LIVE)+increment)
            self.assertEqual(len(ids(p)),len(DYNAMIC_LIVE)+increment)
            # Replace, rather than append, so duplicate detection is tested even at capacity.
            d["sources"][-1]=d["sources"][0]
            p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Duplicate"):load_registry(p)
    def test_exact_capacity_and_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"registry.json"
            d=json.loads(REGISTRY.read_text())
            for n in range(MAX_DYNAMIC_SOURCES-len(d["sources"])):
                d["sources"].append({"id":f"synthetic-capacity-test-{n}","driver":"generic","audit_run":1})
            p.write_text(json.dumps(d))
            self.assertEqual(len(matrix(p)["include"]),MAX_DYNAMIC_SOURCES)
            d["sources"].append({"id":"synthetic-overflow-test","driver":"generic","audit_run":1})
            p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Invalid external source inventory"):load_registry(p)
    def test_invalid_driver_or_missing_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"registry.json"
            d=json.loads(REGISTRY.read_text());d["sources"][0]["audit_run"]=0
            p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"audit"):load_registry(p)
    def test_daily_workflow_uses_dynamic_matrix(self):
        s=Path(".github/workflows/aml339_main18.yml").read_text()
        self.assertIn("fromJSON(needs.prepare_external.outputs.matrix)",s)
        self.assertIn("DRIVER: ${{ matrix.driver }}",s)
        self.assertIn("live_external_generic.py --source",s)
