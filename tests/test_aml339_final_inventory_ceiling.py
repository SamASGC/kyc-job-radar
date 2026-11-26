import json
import tempfile
import unittest
from pathlib import Path
from scripts.aml339_source_manifest import CORE,OPTIONAL,DYNAMIC_LIVE,MAX_CONFIGURED_SOURCES
from external_live_registry import MAX_DYNAMIC_SOURCES,load_registry
from alert_history import blank_history,check_history,select_and_merge,MAX_BASELINED_SOURCES

class FinalInventoryCeilingTests(unittest.TestCase):
    def test_inventory_and_boundary(self):
        self.assertEqual(MAX_CONFIGURED_SOURCES,350)
        self.assertEqual(len(CORE+OPTIONAL)-len(DYNAMIC_LIVE),147)
        self.assertEqual(MAX_DYNAMIC_SOURCES,203)
        self.assertEqual(len(CORE+OPTIONAL),len(set(CORE+OPTIONAL)))
        self.assertLessEqual(len(CORE+OPTIONAL),350)
        rows=[{"id":f"test-{i:03d}","driver":"generic","audit_run":1} for i in range(204)]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"registry.json"
            for n in (203,204):
                p.write_text(json.dumps({"schema":"aml339_external_live_registry_v1","sources":rows[:n]}))
                if n==203:self.assertEqual(len(load_registry(p)),203)
                else:
                    with self.assertRaises(ValueError):load_registry(p)
    def test_history_grows_without_reset(self):
        sources=[f"source-{i:03d}" for i in range(350)]
        old=blank_history()
        old["novelty"]={"baselined_sources":sources[:339],"observed_listing_keys":["a"*24]}
        keys={s:[] for s in sources}
        next_state,report=select_and_merge([],old,configured_sources=sources,strict_novelty=True,listing_keys=keys)
        self.assertEqual(next_state["novelty"]["baselined_sources"],sources)
        self.assertEqual(next_state["novelty"]["observed_listing_keys"],["a"*24])
        self.assertEqual(report["sources_previously_baselined"],339)
        self.assertEqual(sum(report["new_counts"].values()),0)
        self.assertEqual(len(old["novelty"]["baselined_sources"]),339)
        check_history(next_state)
        next_state["novelty"]["baselined_sources"]=[f"source-{i:03d}" for i in range(MAX_BASELINED_SOURCES+1)]
        with self.assertRaises(ValueError):check_history(next_state)
