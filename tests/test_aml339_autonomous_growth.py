import datetime as dt,json,unittest
from pathlib import Path
from growth_discovery import select,norm
from growth_report import reconcile

NOW=dt.datetime(2026,11,24,tzinfo=dt.timezone.utc)
def row(n,name=None,**kw):
    return {"id":f"test-{n}","name":name or f"Example {n} UAB","country":"LT","profile":None,"careers_url":None,"company_site":None,"known_aliases":[],**kw}
def selection(rows):
    return {"selected":rows,"run_id":1,"checked_at":NOW.isoformat(),"eligible_pending":len(rows),"new_register_profiles_observed":0,"discovery_errors":[]}
def result(r,**kw):
    return {"id":r["id"],"name":r["name"],"key":r["key"],"verified":False,"status":"NO_CONFIRMED_CAREERS",**kw}
class AutonomousGrowthTests(unittest.TestCase):
    def test_exact_batch_limit_and_no_recent_repeats(self):
        rows=[row(n) for n in range(105)]
        first,pending=select(rows,set(),[],[],{},NOW)
        self.assertEqual(len(first),50);self.assertEqual(pending,105)
        ledger={"schema":"aml339_growth_ledger_v1","records":{}}
        ledger,report,_=reconcile(selection(first),ledger,[result(r) for r in first])
        second,_=select(rows,set(),[],[],ledger["records"],NOW)
        self.assertEqual(len(second),50)
        self.assertFalse({x["key"] for x in first}&{x["key"] for x in second})
        self.assertEqual(report["total_researched_unique_keys"],50)
    def test_cross_queue_and_existing_catalog_dedup(self):
        rows=[row(1,"Example UAB"),row(2,"Example, UAB"),row(3,"Existing Ltd"),row(4,"Alias UAB"),row(5,"Alias Ltd"),row(6,"Different UAB")]
        got,_=select(rows,{"test-4"},[{"id":"existing","name":"Existing Ltd"}],[],{},NOW)
        self.assertEqual({r["key"] for r in got},{"example","different"})
    def test_report_rejects_missing_duplicate_and_fake_pass(self):
        rows,_=select([row(1)],set(),[],[],{},NOW)
        p={"schema":"aml339_growth_ledger_v1","records":{}}
        r=result(rows[0])
        for reports in ([],[r,r],[dict(r,verified=True,status="TECHNICAL_PASS_REVIEW_REQUIRED")]):
            with self.assertRaises(ValueError):reconcile(selection(rows),p,reports)
        led,summ,proposals=reconcile(selection(rows),p,[dict(r,verified=True,status="TECHNICAL_PASS_REVIEW_REQUIRED",listed=3,unverified=0,config={"id":r["id"]})])
        self.assertEqual(summ["technical_passes"],1)
        self.assertEqual(len(proposals),1)
    def test_discovery_cache_persists_across_batches(self):
        p={"schema":"aml339_growth_ledger_v1","records":{}}
        cache={"checked_at":NOW.isoformat(),"rows":[row(1)],"errors":[]}
        first=selection([])
        first["discovery_cache"]=cache
        updated,summary,_=reconcile(first,p,[])
        self.assertEqual(updated["discovery_cache"],cache)
        later,_,_=reconcile(selection([]),updated,[])
        self.assertEqual(later["discovery_cache"],cache)
        self.assertEqual(summary["selected"],0)
    def test_workflow_write_separation(self):
        text=Path(".github/workflows/aml339_autonomous_growth.yml").read_text()
        self.assertIn("on:\n  workflow_dispatch:\npermissions:",text)
        self.assertNotIn("\n  schedule:",text)
        self.assertNotIn("\n  push:",text)
        self.assertNotIn("\n  pull_request:",text)
        self.assertIn("fromJSON(needs.select.outputs.shards)",text)
        self.assertIn("needs.select.outputs.count != '0'",text)
        self.assertIn("git push origin HEAD:refs/heads/aml339-growth-evidence",text)
        self.assertIn("github.event_name != 'pull_request'",text)
        self.assertNotIn("git push origin HEAD:main",text)
        self.assertNotIn("data/aml339_main18_state.json",text)
