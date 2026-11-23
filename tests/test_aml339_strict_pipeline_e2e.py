"""Full 38-source no-network acceptance: official-listing novelty to public UI and RSS."""
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from alert_history import (
    blank_history, load_official_listing_keys, select_and_merge, verify_input_coverage,
)
from scripts.aml339_source_manifest import CORE, EXPANSION, collect
from scripts.aml339_site import build
from two_lane_alert_preview import listing_identity, read_evidence, role_template


def evidence_for(source, roles, *, audit=True):
    rows=list(roles)
    return {
        "total_configured_sources": 339,
        "mode": "READ_ONLY_ISOLATED_NO_PRODUCTION_DATA",
        "sources": [{
            "source_id": source, "state": "listing_extracted", "list_complete": True,
            "total_listed": len(rows), "relevant_leads":len(rows),
            "listing_role_keys": sorted({listing_identity(source, r) for r in rows}),
            "listing_untrackable_count":0,
            "audited":rows if audit else [],
            "unverified_in_scope":0,
        }],
    }


class StrictFullPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.core=self.root/"core"
        self.extra=self.root/"optional"
        self.core.mkdir()
        self.extra.mkdir()
        self.old=role_template(title="Financial Crime Screening Analyst",
                               url="https://jobs.example.org/jobs/1170001")
        self.new=role_template(title="Sanctions Monitoring Officer",
                               url="https://jobs.example.org/jobs/1170002")
        self.write_core(CORE[0],[self.old])
        for sid in CORE[1:]:
            self.write_core(sid,[])
        for sid in EXPANSION:
            self.write_extra(sid,[])

    def write_core(self,sid,roles):
        (self.core/f"source_{sid}.json").write_text(json.dumps(evidence_for(sid,roles)),
                                                    encoding="utf-8")

    def write_extra(self,sid,roles):
        (self.extra/f"candidate_{sid}.json").write_text(json.dumps(evidence_for(sid,roles)),
                                                        encoding="utf-8")

    def run_once(self,state):
        paths,ids,manifest=collect(self.core,self.extra)
        verify_input_coverage(paths,ids,True)
        keys=load_official_listing_keys(paths,ids)
        rows=read_evidence(paths)
        state,report=select_and_merge(rows,state,configured_sources=ids,
                                       strict_novelty=True,listing_keys=keys)
        output=self.root/"public"
        build(paths,state,report,output,manifest)
        return state,report,json.loads((output/"summary.json").read_text()),output

    def test_first_full_38_scan_seeds_history_and_real_second_scan_alerts_once(self):
        first,report1,summary1,out=self.run_once(blank_history())
        self.assertEqual(summary1["sources_complete"],38)
        self.assertEqual(summary1["current_qualifying"],1)
        self.assertTrue(summary1["novelty_guard_enabled"])
        self.assertEqual(summary1["new_counts"],{
            "confirmed_recent":0,"promising_date_unconfirmed":0,
        })
        self.assertEqual(len(first["novelty"]["baselined_sources"]),38)
        html=(out/"index.html").read_text(encoding="utf-8")
        self.assertIn("Nuevas en este seguimiento: 0",html)
        self.assertIn("<details>",html)
        self.write_core(CORE[0],[self.old,self.new])
        second,report2,summary2,out=self.run_once(first)
        self.assertEqual(summary2["new_counts"],{
            "confirmed_recent":0,"promising_date_unconfirmed":1,
        })
        self.assertIn("Sanctions Monitoring Officer",report2["new_alert_previews"]["promising_date_unconfirmed"][0]["title"])
        self.assertIn("Nuevas en este seguimiento: 1",
                      (out/"index.html").read_text(encoding="utf-8"))
        feed=ET.fromstring((out/"review.xml").read_text(encoding="utf-8"))
        self.assertEqual(len(feed.findall("./channel/item")),2)
        self.assertEqual(len(second["records"]),2)
        third,report3,summary3,out=self.run_once(second)
        self.assertEqual(summary3["new_counts"],{
            "confirmed_recent":0,"promising_date_unconfirmed":0,
        })
        self.assertEqual(set(third["records"]),set(second["records"]))
        self.assertEqual(len(third["novelty"]["observed_listing_keys"]),2)


if __name__=="__main__":
    unittest.main()
