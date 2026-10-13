"""v3.4 audited career-site expansion; HTML portals are NOT certified ATS."""
import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
NAMES = {
    "BBVA","CaixaBank","ABANCA","Ibercaja Banco","Grupo Cooperativo Cajamar",
    "Banca March","NEO Finance","Bank of Lithuania","CSSF Luxembourg",
    "FINMA","Swiss National Bank","Banco de España",
}
EVIDENCE = {
    "BBVA": "https://www.bbva.com/es/empleo/",
    "CaixaBank": "https://caixabankcareers.com/",
    "ABANCA": "https://empleo.abanca.com/",
    "Ibercaja Banco": "https://empleo.ibercaja.es/ofertas-de-empleo/",
    "Grupo Cooperativo Cajamar": "https://www.cajamar.es/es/comun/informacion-corporativa/empleo/",
    "Banca March": "https://www.bancamarch.es/es/nosotros/trabaje-con-nosotros/",
    "NEO Finance": "https://careers.neofinance.com/",
    "Bank of Lithuania": "https://karjera.lb.lt/jobs",
    "CSSF Luxembourg": "https://careers.cssf.lu/en/all-jobs/",
    "FINMA": "https://jobs.finma.ch/",
    "Swiss National Bank": "https://careers.snb.ch/",
    "Banco de España": "https://www.bde.es/wbe/es/sobre-banco/trabajar-banco/convocatorias-plazo-abierto/",
}


class RealFinancialSourcesV34Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = []
        for p in ("config/companies.json", "config/extra_companies.json"):
            cls.rows += json.loads((ROOT/p).read_text(encoding="utf-8"))
        cls.by_name = {r["name"].casefold(): r for r in cls.rows}

    def test_462_direct_unique_and_no_fictitious_ats_growth(self):
        self.assertGreaterEqual(len(self.rows), 462)
        self.assertEqual(len(self.rows), len(self.by_name), "Duplicate employers")
        self.assertGreaterEqual(sum(bool(c.get("ats")) for c in self.rows), 152)

    def test_all_new_12_employers_have_official_first_party_evidence(self):
        self.assertEqual(len(NAMES), 12)
        for name in NAMES:
            with self.subTest(name=name):
                rec=self.by_name[name.casefold()]
                self.assertEqual(rec["careers_url"], EVIDENCE[name])
                self.assertEqual(urlsplit(rec["careers_url"]).scheme, "https")
                self.assertTrue(rec["enabled"])
                self.assertFalse(rec.get("ats"), "Do not invent provider ATS")
                self.assertEqual(rec["verification_level"],
                                 "official_careers_url_not_necessarily_api")
                self.assertIn(rec["careers_url"], rec["origin"])
                self.assertTrue(rec["specialism"])


if __name__ == "__main__":
    unittest.main()
