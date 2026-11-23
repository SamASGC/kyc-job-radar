"""The radar must discover genuinely unseen official job IDs, not recycle old listings."""
import json
import tempfile
import unittest
from pathlib import Path

from alert_history import (
    blank_history, check_history, load_official_listing_keys, select_and_merge,
)
from two_lane_alert_preview import key, role_template

SOURCES=("already-tracked","new-fintech")


def under_review(title, url):
    return role_template(title=title,url=url,location="Tallinn, Estonia")


class TrueNoveltyTests(unittest.TestCase):
    def test_first_seen_undated_vacancies_on_new_sources_are_baseline_not_alerts(self):
        old=under_review("AML Screening Specialist","https://jobs.example.com/job/123")
        records=[("already-tracked",old)]
        hashes={"already-tracked":[key("already-tracked",old)],"new-fintech":[]}
        state,report=select_and_merge(
            records,blank_history(),"initial",configured_sources=SOURCES,
            strict_novelty=True,listing_keys=hashes)
        self.assertEqual(report["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":0})
        self.assertEqual(report["suppressed_reasons"]["new_source_first_scan_baseline_only"],1)
        self.assertEqual(state["novelty"]["baselined_sources"],sorted(SOURCES))
        _,replay=select_and_merge(
            records,state,"replay",configured_sources=SOURCES,
            strict_novelty=True,listing_keys=hashes)
        self.assertEqual(replay["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":0})
        self.assertEqual(replay["suppressed_reasons"]["previously_listed_not_a_new_vacancy"],1)

    def test_new_stable_job_on_warmed_source_alerts_only_once(self):
        first=under_review("KYC AML Analyst","https://jobs.example.com/job/20")
        first_keys={"already-tracked":[key("already-tracked",first)],"new-fintech":[]}
        state,_=select_and_merge([("already-tracked",first)],blank_history(),
                                 configured_sources=SOURCES,strict_novelty=True,
                                 listing_keys=first_keys)
        new=under_review("Financial Crime Screening Analyst","https://jobs.example.com/job/21")
        new_keys={"already-tracked":[key("already-tracked",first),
                                      key("already-tracked",new)],
                  "new-fintech":[]}
        history,report=select_and_merge([("already-tracked",first),("already-tracked",new)],
                                        state,configured_sources=SOURCES,
                                        strict_novelty=True,listing_keys=new_keys)
        self.assertEqual(report["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":1})
        self.assertEqual(report["new_alert_previews"]["promising_date_unconfirmed"][0]["title"],
                         "Financial Crime Screening Analyst")
        _,repeat=select_and_merge([("already-tracked",first),("already-tracked",new)],
                                  history,configured_sources=SOURCES,
                                  strict_novelty=True,listing_keys=new_keys)
        self.assertEqual(repeat["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":0})

    def test_parser_fix_cannot_relabel_an_old_listed_job_as_new(self):
        old=under_review("Transaction Monitoring Specialist",
                         "https://apply.workable.com/example/j/OLD123/")
        no_selected={"already-tracked":[key("already-tracked",old)],"new-fintech":[]}
        state,_=select_and_merge([],blank_history(),configured_sources=SOURCES,
                                 strict_novelty=True,listing_keys=no_selected)
        history,report=select_and_merge([("already-tracked",old)],state,
                                        configured_sources=SOURCES,
                                        strict_novelty=True,listing_keys=no_selected)
        self.assertEqual(report["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":0})
        self.assertEqual(report["suppressed_reasons"]["previously_listed_not_a_new_vacancy"],1)
        self.assertEqual(len(history["records"]),1)
        self.assertFalse(history["records"][next(iter(history["records"]))]["delivered_lanes"])

    def test_existing_source_baselines_survive_new_optional_source(self):
        # Adding a new FinCrime portal with undated older positions never floods alerts.
        old=under_review("KYC Investigator","https://example.org/jobs/old")
        newcomer=under_review("AML Screening Specialist","https://example.org/jobs/old2")
        keys1={"already-tracked":[key("already-tracked",old)]}
        state,_=select_and_merge([("already-tracked",old)],blank_history(),
                                 configured_sources=["already-tracked"],
                                 strict_novelty=True,listing_keys=keys1)
        keys2={"already-tracked":[key("already-tracked",old)],
               "new-fintech":[key("new-fintech",newcomer)]}
        _,report=select_and_merge([("already-tracked",old),("new-fintech",newcomer)],
                                  state,configured_sources=SOURCES,
                                  strict_novelty=True,listing_keys=keys2)
        self.assertEqual(report["new_counts"]["promising_date_unconfirmed"],0)
        self.assertEqual(report["suppressed_reasons"]["new_source_first_scan_baseline_only"],1)

    def test_fresh_original_date_can_alert_on_first_source_scan_but_not_on_replay(self):
        recent=role_template(title="Junior Sanctions Screening Analyst",
              evaluation={"class":"possible_match_confirmed_recent",
                          "publication_status":"fresh",
                          "original_posting_date":"2026-11-23T15:00:00+00:00",
                          "date_field":"Greenhouse.first_published",
                          "uncertainties":[]})
        hashes={"already-tracked":[key("already-tracked",recent)]}
        history,report=select_and_merge([("already-tracked",recent)],blank_history(),
                                        configured_sources=["already-tracked"],
                                        strict_novelty=True,listing_keys=hashes)
        self.assertEqual(report["new_counts"],{"confirmed_recent":1,"promising_date_unconfirmed":0})
        _,second=select_and_merge([("already-tracked",recent)],history,
                                  configured_sources=["already-tracked"],
                                  strict_novelty=True,listing_keys=hashes)
        self.assertEqual(second["new_counts"],{"confirmed_recent":0,"promising_date_unconfirmed":0})

    def test_incomplete_or_invalid_official_listing_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"complete per-source"):
            select_and_merge([],blank_history(),configured_sources=["source"],
                             strict_novelty=True,listing_keys={})
        with self.assertRaisesRegex(ValueError,"Invalid official listing"):
            select_and_merge([],blank_history(),configured_sources=["source"],
                             strict_novelty=True,listing_keys={"source":["not-sha"]})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"source.json"
            path.write_text(json.dumps({"total_configured_sources":339,
              "sources":[{"source_id":"source","state":"listing_extracted",
                "list_complete":True,"total_listed":3,
                "listing_role_keys":["a"*24,"b"*24],"listing_untrackable_count":0}]}))
            self.assertEqual(load_official_listing_keys([path],["source"])["source"],
                             ["a"*24,"b"*24])
            path.write_text(json.dumps({"total_configured_sources":339,
              "sources":[{"source_id":"source","state":"listing_extracted",
                "list_complete":True,"total_listed":3}]}))
            with self.assertRaisesRegex(ValueError,"Missing/malformed"):
                load_official_listing_keys([path],["source"])
        broken=blank_history()
        broken["novelty"]={"baselined_sources":["dup","dup"],"observed_listing_keys":[]}
        with self.assertRaises(ValueError):
            check_history(broken)


if __name__=="__main__":
    unittest.main()
