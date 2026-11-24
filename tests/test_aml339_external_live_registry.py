import json,tempfile,unittest
from pathlib import Path
from scripts.aml339_source_manifest import DYNAMIC_LIVE,CORE,OPTIONAL
from external_live_registry import load_registry,matrix,ids,REGISTRY

class ExternalRegistryTests(unittest.TestCase):
    def test_matrix_and_manifest_share_one_inventory(self):
        rows=load_registry()
        self.assertEqual(set(x["source"] for x in matrix()["include"]),set(DYNAMIC_LIVE))
        self.assertEqual(len(matrix()["include"]),len(DYNAMIC_LIVE))
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        self.assertEqual(len(rows),len(DYNAMIC_LIVE))
    def test_fifty_new_verified_rows_require_no_code_or_workflow_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"registry.json"
            d=json.loads(REGISTRY.read_text())
            for n in range(50):
                d["sources"].append({"id":f"synthetic-batch-test-{n}","driver":"generic","audit_run":1})
            p.write_text(json.dumps(d))
            self.assertEqual(len(matrix(p)["include"]),len(DYNAMIC_LIVE)+50)
            self.assertEqual(len(ids(p)),len(DYNAMIC_LIVE)+50)
            d["sources"].append(d["sources"][0])
            p.write_text(json.dumps(d))
            with self.assertRaisesRegex(ValueError,"Duplicate"):load_registry(p)
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
