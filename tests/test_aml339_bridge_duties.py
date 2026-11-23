"""Regression: distinguish real FinCrime duties from mere required knowledge."""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


class BridgeDutiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        with ZipFile("experiments/aml339/full_original_339_sources.zip") as z:
            allowed={"amlradar/__init__.py", "amlradar/model.py", "amlradar/net.py",
                     "amlradar/employer_links.py", "amlradar/sources.py",
                     "fuentes.json", "VALIDAR_REAL_SIN_TOCAR_DATOS.py"}
            assert set(z.namelist()) == allowed
            z.extractall(cls.root)
        cls.path = str(cls.root)
        sys.path.insert(0, cls.path)
        cls.audit_path = str(Path("experiments/aml339").resolve())
        sys.path.insert(0, cls.audit_path)
        cls.qa = importlib.import_module("quality_audit")

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(cls.path)
        sys.path.remove(cls.audit_path)
        cls.temp.cleanup()

    def test_real_transfergo_heading_and_screening_responsibilities(self):
        role = {
            "title": "AML & Fraud Risk Analyst",
            "location": "Vilnius, Lithuania",
            "description": "\n".join([
                "What you'll be doing:",
                "Conducting PEP, Sanctions, and Adverse Media screening alert investigations and escalations;",
                "Conducting Enhanced Due Diligence checks;",
                "What you'll bring:",
                "Relevant work experience in compliance.",
                "Proficiency in English.",
            ]),
            "date": None,
        }
        assessment = self.qa.evaluate(role, application_verified=True)
        self.assertTrue(
            {"PEP", "Sanctions screening", "Adverse media"}.issubset(
                set(assessment["explicit_duties"])
            ),
            assessment,
        )
        self.assertNotIn("Idioma adicional obligatorio no acreditado", assessment["barriers"])

    def test_specialist_screening_and_transaction_monitoring_titles_never_missed(self):
        for title in ("Transaction Monitoring Specialist", "Senior Transaction Monitoring Specialist",
                      "Junior AML Analyst", "Sanctions Screening Officer"):
            self.assertTrue(self.qa.candidate({"title": title, "description": "",
                                                "location": "Ta' Xbiex, Malta"}), title)
        self.assertFalse(self.qa.candidate({"title": "Account Executive", "description": "",
                                             "location": "Malta"}))

    def test_requirements_only_not_counted_as_duties(self):
        role = {
            "title": "KYC Compliance Officer",
            "location": "Tallinn, Estonia",
            "description": "\n".join([
                "What you'll be doing:",
                "Check identity documents and reconcile operational accounts.",
                "What you'll bring:",
                "Knowledge of sanctions screening, PEP and adverse media required.",
            ]),
            "date": None,
        }
        assessment = self.qa.evaluate(role, application_verified=True)
        self.assertFalse(
            {"PEP", "Sanctions screening", "Adverse media"} &
            set(assessment["explicit_duties"]),
            assessment,
        )


if __name__ == "__main__":
    unittest.main()
