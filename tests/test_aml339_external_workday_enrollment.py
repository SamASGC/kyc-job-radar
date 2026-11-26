"""Fail-closed validation for reviewed external Workday tenants."""
import ast,json,re,unittest
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile
from scripts.aml339_source_manifest import CORE,OPTIONAL,EXTERNAL50_LIVE
from external_live_registry import load_registry

IDS=set(["external-saxo-bank","external-fidelity-international","external-invesco","external-ares-management","external-blackstone","external-swiss-life-international","external-pgim-prudential","external-wellington-management","external-gunvor","external-trafigura"])

class ExternalWorkdayEnrollmentTests(unittest.TestCase):
    def test_distinct_approved_sources(self):
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            old=json.loads(z.read("fuentes.json"))["sources"]
        rows=load_registry()
        new=[r for r in rows if r.get("route",[""])[0]=="workday" and r["driver"]=="generic"]
        self.assertTrue(IDS.issubset({r["id"] for r in new}))
        self.assertEqual(len(set(CORE+OPTIONAL)),len(CORE+OPTIONAL))
        for r in new:
            self.assertIn(r["id"],EXTERNAL50_LIVE)
            self.assertGreater(r["audit_artifact"],0)
            self.assertTrue(r["hiring_reference"].startswith("https://"))
            self.assertTrue(r["id"] in ("external-gunvor","external-trafigura") or r.get("regulatory_reference","").startswith("https://"))
            self.assertFalse(any(o["id"]==r["id"] or o.get("route")==r["route"] for o in old))
            self.assertEqual(sum(o.get("route")==r["route"] for o in rows),1)

    def test_worker_positive_and_negative_evidence(self):
        # Extract exact pure function for unit testing without importing the isolated ZIP.
        path=Path("experiments/aml339/live_external_generic.py")
        tree=ast.parse(path.read_text())
        func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="audit_workday")
        response={"state":"listing_extracted","list_complete":True,"total_listed":2,
                  "relevant_leads":0,"audited":[],"unverified_in_scope":0,
                  "listing_untrackable_count":0,"listing_role_keys":["a","b"]}
        calls=[]
        def mock_audit(row,minutes):
            calls.append((row,minutes))
            return dict(response)
        env={"re":re,"urlsplit":urlsplit,"audit_one":mock_audit}
        exec(compile(ast.Module(body=[func],type_ignores=[]),str(path),"exec"),env)
        run=env["audit_workday"]
        row={"id":"test","name":"Test","careers_url":"https://test.wd1.myworkdayjobs.com/Careers",
             "route":["workday","test.wd1.myworkdayjobs.com","Careers"]}
        self.assertTrue(run(row)[1])
        for url in ("http://test.wd1.myworkdayjobs.com/Careers",
                    "https://test.wd1.myworkdayjobs.com.evil.example/Careers",
                    "https://test.wd1.myworkdayjobs.com/Wrong",
                    "https://test.wd1.myworkdayjobs.com/Careers?other=x"):
            with self.assertRaisesRegex(ValueError,"Unapproved Workday"):
                run(dict(row,careers_url=url))
        self.assertEqual(len(calls),1)
        for k,bad in (("total_listed",0),("list_complete",False),("unverified_in_scope",1),
                      ("listing_untrackable_count",1),("listing_role_keys",["a"]),("relevant_leads",1)):
            original=response[k];response[k]=bad
            result,ok=run(row)
            self.assertFalse(ok)
            self.assertFalse(result["list_complete"])
            response[k]=original
