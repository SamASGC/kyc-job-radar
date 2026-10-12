"""Deduplicatable public RSS output for verified-open, fresh positions."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
import xml.etree.ElementTree as ET

from job_radar.config import ROOT
from job_radar.models import norm_text

SITE_URL = "https://samasgc.github.io/kyc-job-radar/"


def create_rss(jobs: list[dict], out_path: str = "public/feed.xml",
               channel_link: str = SITE_URL) -> None:
    target = ROOT / out_path
    target.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = "Radar AML — nuevas vacantes verificadas"
    ET.SubElement(channel, "link").text = channel_link
    ET.SubElement(channel, "description").text = (
        "Vacantes Financial Crime, KYC/KYB y AML verificadas en ATS oficiales, "
        "publicadas hace menos de 96 horas, sin reposts."
    )
    items = sorted(jobs, key=lambda r: r.get("first_seen", ""), reverse=True)
    for job in items[:80]:
        if not job.get("apply_verified_at") or not job.get("fingerprint"):
            continue
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = (
            str(job.get("company", "")) + " — " + str(job.get("title", ""))
        )
        ET.SubElement(item, "link").text = str(job.get("apply_url", ""))
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = (
            "kyc-radar-" + str(job["fingerprint"])
        )
        ET.SubElement(item, "description").text = (
            "Puesto: " + str(job.get("title", "")) + ". "
            "Empresa: " + str(job.get("company", "")) + ". "
            "Ubicación: " + str(job.get("location", "")) + ". "
            "Publicado originalmente: " + str(job.get("posted_at", "")) + ". "
            "Verificación ATS: " + str(job.get("apply_verified_at", "")) + "."
        )
        published = str(job.get("first_seen") or job.get("discovered_at") or "")
        try:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            ET.SubElement(item, "pubDate").text = format_datetime(dt.astimezone(timezone.utc))
        except (ValueError, TypeError, OverflowError):
            pass
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
