"""v3.0: attributable brokerage, FinCrime and Swiss fund employer coverage."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
ATS={
"Clear Street":("greenhouse","clearstreet"),
"Virtu Financial":("greenhouse","virtu"),
"FalconX":("greenhouse","falconx"),
"GSR Markets":("greenhouse","gsrmarkets"),
"DigitalBridge":("greenhouse","digitalbridge"),
"PINE Advisor Solutions":("greenhouse","pineadvisorsolutions"),
"Nansen":("greenhouse","nansen"),
"Galaxy Digital":("greenhouse","galaxydigitalservices"),
"Alpaca Markets":("greenhouse","alpaca"),
"Morpho":("ashby","morpho"),
"Thrivo Wealth Partners":("ashby","thrivo-wealth"),
"Windranger Labs":("ashby","windranger"),
"Unison Infrastructure":("lever","unisoninfra"),
}
CORPORATES={
"VZ VermögensZentrum","GAM Investments","Pemberton Asset Management",
"Schroders","Hamilton Lane","Aquila Capital","Zodia Custody","Taurus SA",
"Man Group","Wintermute","Gemini Exchange","Anchorage Digital",
}

class SourceCoverageV30Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.companies=json.loads((ROOT/"config/companies.json").read_text())+json.loads(
            (ROOT/"config/extra_companies.json").read_text())
        cls.by_name={c["name"].casefold():c for c in cls.companies}
    def test_375_unique_direct_and_140_explicit_ats(self):
        self.assertEqual(len(cls.companies) if (cls:=self.__class__) else 0,375)
        self.assertEqual(len(self.by_name),375)
        self.assertGreaterEqual(sum(bool(c.get("ats")) for c in self.companies),140)
    def test_13_provider_owned_ats_identifiers_and_evidence(self):
        self.assertEqual(len(ATS),13)
        for name,(kind,slug) in ATS.items():
            with self.subTest(company=name):
                c=self.by_name[name.casefold()]
                self.assertTrue(c["enabled"])
                self.assertEqual(c["ats"],[{"kind":kind,"slug":slug}])
                self.assertEqual(c["verification_level"],"official_ats_pending_live_health")
                base=urlsplit(c["careers_url"])
                evidence=urlsplit(c["origin"].split(": ",1)[1])
                host={"greenhouse":"job-boards.greenhouse.io",
                      "ashby":"jobs.ashbyhq.com","lever":"jobs.lever.co"}[kind]
                self.assertEqual(base.hostname,host)
                self.assertEqual(base.path.strip("/"),slug)
                self.assertEqual(evidence.hostname,host)
                self.assertEqual(evidence.path.strip("/").split("/")[0],slug)
    def test_12_official_portals_not_falsely_classified_as_ats(self):
        self.assertEqual(len(CORPORATES),12)
        for name in CORPORATES:
            with self.subTest(company=name):
                c=self.by_name[name.casefold()]
                self.assertTrue(c["enabled"])
                self.assertEqual(c["verification_level"],
                                 "official_careers_url_not_necessarily_api")
                self.assertFalse(c.get("ats"))
                self.assertEqual(urlsplit(c["careers_url"]).scheme,"https")
                self.assertIn(c["careers_url"],c["origin"])

if __name__=="__main__":
    unittest.main()
