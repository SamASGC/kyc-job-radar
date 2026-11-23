"""Swiss opportunities are in geographic scope but never imply employment eligibility."""
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from experiments.aml339.two_lane_alert_preview import triage, role_template
from scripts.aml339_site import build
from alert_history import blank_history, select_and_merge


def swiss_role(**overrides):
    evidence = {
        "class": "manual_review",
        "geography": "swiss_future",
        "publication_status": "fresh",
        "original_posting_date": dt.datetime.now(dt.timezone.utc).isoformat(),
        "date_field": "Greenhouse.first_published",
        "application_verified": True,
        "functions": ["PEP", "Sanctions screening"],
        "explicit_duties": ["Sanctions screening"],
        "barriers": [],
        "uncertainties": ["Suiza: vía profesional futura; no asumir elegibilidad actual"],
    }
    evidence.update(overrides)
    return role_template(
        title="Financial Crime Screening Analyst",
        location="Zürich, Switzerland",
        url="https://careers.example.org/jobs/543210",
        evaluation=evidence,
    )


class SwissScopeTests(unittest.TestCase):
    def test_recent_original_date_swiss_is_not_hidden(self):
        item, err = triage("swiss-bank", swiss_role())
        self.assertIsNone(err)
        self.assertEqual(item["lane"], "confirmed_recent")
        self.assertEqual(item["geography"], "swiss_future")
        self.assertIn("permiso", item["note"])
        self.assertEqual(item["confirmed_job_duties"], ["Sanctions screening"])

    def test_undated_swiss_is_review_only(self):
        item, err = triage("swiss-bank", swiss_role(
            publication_status="undated", original_posting_date=None, date_field=""
        ))
        self.assertIsNone(err)
        self.assertEqual(item["lane"], "promising_date_unconfirmed")

    def test_no_eligibility_claim_when_german_or_extra_experience_required(self):
        self.assertEqual(
            triage("swiss-bank", swiss_role(barriers=["German C1 mandatory"]))[1],
            "explicit_barrier",
        )
        self.assertEqual(
            triage("swiss-bank", swiss_role(application_verified=False))[1],
            "application_unverified",
        )
        self.assertEqual(
            triage("swiss-bank", swiss_role(explicit_duties=[]))[1],
            "target_functions_not_in_job_duties",
        )
        self.assertEqual(
            triage("swiss-bank", swiss_role(geography="outside_scope"))[1],
            "unconfirmed_or_outside_geography",
        )

    def test_swiss_card_and_rss_are_explicit_about_work_rights(self):
        role = swiss_role()
        history, report = select_and_merge(
            [("swiss-bank", role)], blank_history(),
            configured_sources=[str(i) for i in range(18)]
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / "source.json"
            evidence.write_text(json.dumps({
                "total_configured_sources": 339,
                "sources": [{"source_id": "swiss-bank", "audited": [role]}]
            }), encoding="utf-8")
            output = root / "site"
            build([evidence], history, report, output)
            page = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("permiso y", page)
            self.assertIn("aceptación de la candidatura sin confirmar", page)
            feed = ET.fromstring((output / "confirmed.xml").read_text(encoding="utf-8"))
            items = feed.findall("./channel/item")
            self.assertEqual(len(items), 1)
            self.assertIn("elegibilidad laboral", items[0].findtext("description"))
            self.assertIn("permiso", items[0].findtext("description"))


if __name__ == "__main__":
    unittest.main()
