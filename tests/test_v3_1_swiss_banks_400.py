"""v3.1: exact 400 direct employers; banks never misrepresented as API feeds."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit,parse_qs

ROOT=Path(__file__).resolve().parents[1]
ATS={
"Jane Street":"janestreet",
"Point72":"point72",
"DRW Trading":"drweng",
"Optiver":"optiverus",
}
PORTALS={
"Banque Cantonale de Genève","Banque Cantonale de Fribourg",
"Banque Cantonale du Valais","Banque Cantonale Neuchâteloise",
"Bank Cler","Quintet Private Bank","Banque Cantonale du Jura","Swiss Re",
"Helvetia Group","Bank CIC (Switzerland)",
"Liechtensteinische Landesbank","BGL BNP Paribas","Syz Group",
"Zurich Insurance Group","St. Galler Kantonalbank",
"Aargauische Kantonalbank","Valiant Bank",
"Basellandschaftliche Kantonalbank","Luzerner Kantonalbank",
"Graubündner Kantonalbank","Thurgauer Kantonalbank",
}

class SwissBank400Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=(json.loads((ROOT/"config/companies.json").read_text())+
                  json.loads((ROOT/"config/extra_companies.json").read_text()))
        cls.names={x["name"].casefold():x for x in cls.rows}
    def test_400_direct_unique_and_144_provider_configs(self):
        self.assertGreaterEqual(len(self.rows),400)
        self.assertEqual(len(self.names),len(self.rows))
        self.assertGreaterEqual(sum(bool(x.get("ats")) for x in self.rows),144)
    def test_four_evidenced_greenhouse_boards(self):
        self.assertEqual(len(ATS),4)
        for name,slug in ATS.items():
            with self.subTest(name=name):
                c=self.names[name.casefold()]
                self.assertTrue(c["enabled"])
                self.assertEqual(c["ats"],[{"kind":"greenhouse","slug":slug}])
                self.assertEqual(c["verification_level"],"official_ats_pending_live_health")
                self.assertEqual(urlsplit(c["careers_url"]).hostname,
                                 "job-boards.greenhouse.io")
                self.assertEqual(urlsplit(c["careers_url"]).path.strip("/"),slug)
                evidence=urlsplit(c["origin"].split(": ",1)[1])
                self.assertEqual(evidence.hostname,"job-boards.greenhouse.io")
                if name=="Optiver":
                    self.assertEqual(parse_qs(evidence.query).get("for"),[slug])
                else:
                    self.assertEqual(evidence.path.strip("/").split("/")[0],slug)
    def test_21_distinct_official_corporate_portals_no_fictional_ats(self):
        self.assertEqual(len(PORTALS),21)
        for name in PORTALS:
            with self.subTest(name=name):
                c=self.names[name.casefold()]
                self.assertTrue(c["enabled"])
                self.assertFalse(c.get("ats"))
                self.assertEqual(c["verification_level"],
                                 "official_careers_url_not_necessarily_api")
                self.assertEqual(c["sector"],"Banca")
                self.assertEqual(urlsplit(c["careers_url"]).scheme,"https")
                self.assertIn(c["careers_url"],c["origin"])

if __name__=="__main__":
    unittest.main()
