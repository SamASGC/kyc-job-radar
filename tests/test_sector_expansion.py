from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

from job_radar.source_inventory import build_source_inventory, summarize_source_coverage
from job_radar.review import review_candidates


class ExpandedSourcesTests(unittest.TestCase):
    def test_all_new_employers_have_documented_official_career_urls(self):
        root=Path(__file__).resolve().parents[1]
        company_files=("config/companies.json","config/extra_companies.json")
        rows=[]
        for item in company_files:
            rows+=json.loads((root/item).read_text(encoding="utf-8"))
        names=[str(c.get("name","")).casefold() for c in rows]
        self.assertEqual(len(names),len(set(names)),"Duplicate configured employer")
        wanted={
            "UBS","Pictet","Lombard Odier","Vontobel","LGT Group",
            "SEB","Swedbank","Nordea","Deutsche Bank","HSBC","State Street",
            "Northern Trust","IQ-EQ","Alter Domus","Vistra","Azets",
            "Deloitte Luxembourg","KPMG Luxembourg",
            "CACEIS","SIX Group","Luminor","Citadele Bank","Avaloq",
            "TMF Group","Brown Brothers Harriman",
        }
        by_name={c["name"]:c for c in rows}
        for name in wanted:
            self.assertIn(name,by_name)
            c=by_name[name]
            self.assertTrue(c["careers_url"].startswith("https://"))
            if name == "Northern Trust":
                # v3.12: the official employer-owned Workday board was verified live.
                self.assertEqual(c["verification_level"], "official_ats_live_probe_passed")
                self.assertEqual(c.get("ats"), [{"kind": "workday",
                    "url": "https://ntrs.wd1.myworkdayjobs.com/northerntrust"}])
            elif name == "IQ-EQ":
                # v3.17: public employer-scoped IQEQ SmartRecruiters feed
                # was checked against the provider's company identifier.
                self.assertEqual(c["verification_level"], "official_ats_live_probe_passed")
                self.assertEqual(c.get("ats"), [{"kind": "smartrecruiters", "slug": "iqeq"}])
                self.assertIn("iqeq.com/careers/vacancies/", c["origin"])
            else:
                self.assertEqual(c["verification_level"],
                                 "official_careers_url_not_necessarily_api")
            self.assertIn(c["sector"],{"Banca","Fintech"})

    def test_source_inventory_distinguishes_configuration_and_reachability(self):
        companies=[
            {"name":"Private Bank","sector":"Banca","specialism":"Private banking",
             "careers_url":"https://bank.example/jobs",
             "ats":[{"kind":"greenhouse","slug":"privatebank"}]},
            {"name":"Fund Admin","sector":"Fintech","specialism":"Fund administrator",
             "careers_url":"https://fundadmin.example/careers"},
            {"name":"No Fetch","sector":"Fintech",
             "careers_url":"https://unknown.example/careers"},
        ]
        health=[
            {"company":"Private Bank","ok":True,"jobs":12},
            {"company":"Fund Admin","ok":False,"jobs":0},
        ]
        stats=summarize_source_coverage(companies,health)
        self.assertEqual(stats["ats_explicit"],1)
        self.assertEqual(stats["reached"],1)
        self.assertEqual(stats["errors"],1)
        self.assertEqual(stats["not_checked"],1)
        self.assertEqual(stats["with_jobs"],1)
        with tempfile.TemporaryDirectory() as tmp:
            build_source_inventory(companies,health,out_dir=tmp)
            html=(Path(tmp)/"sources.html").read_text(encoding="utf-8")
            self.assertIn("Private banking",html)
            self.assertIn("ATS configurados",html)
            self.assertTrue((Path(tmp)/"sources.json").exists())

    def test_urgent_pending_list_is_not_limited_to_provider_first_25(self):
        recent=datetime.now(timezone.utc).isoformat()
        records=[]
        for n in range(31):
            records.append({"company":f"Fintech {n}","title":"Sales Director",
                            "location":"Spain - Remote",
                            "geography_verified":True,
                            "posted_at":recent,
                            "url":f"https://jobs.ashbyhq.com/fintech/{n}",
                            "reason":"page_200_but_no_visible_apply_action"})
        records.extend([
            {"company":"Asset Servicing A","title":"AML/KYC Analyst",
             "location":"Luxembourg - Hybrid",
             "geography_verified":True,"posted_at":recent,
             "url":"https://jobs.ashbyhq.com/funds/123",
             "reason":"page_200_but_no_visible_apply_action"},
            {"company":"Bank B","title":"Sanctions Investigator",
             "location":"Switzerland - Hybrid",
             "geography_verified":True,"posted_at":"",
             "url":"https://jobs.ashbyhq.com/bank/xyz",
             "reason":"original_publication_missing_or_older_than_96h"},
        ])
        result=review_candidates(records)
        self.assertEqual([r["company"] for r in result],
                         ["Asset Servicing A","Bank B"])


if __name__=="__main__":
    unittest.main()
