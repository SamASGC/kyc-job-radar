#!/usr/bin/env python3
"""Publish verified AML339 pilot opportunities into a SEPARATE static dashboard.

This is not the 500-employer production feed and does not send emails.
All roles come from individually audited official HTTP evidence. No cached/unverified
record, date guess or simulation-only alert may masquerade as an open role.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "aml339"))
from two_lane_alert_preview import triage, read_evidence
from alert_history import check_history
from scripts.aml339_source_manifest import CORE, OPTIONAL, EXTERNAL50_LIVE

ROOT = "https://samasgc.github.io/kyc-job-radar/aml339/"
LANES = ("confirmed_recent", "promising_date_unconfirmed")
LANE_NAMES = {
    "confirmed_recent": "Publicación original reciente y comprobada (72 h)",
    "promising_date_unconfirmed": "En revisión: fecha original no acreditada",
}
FEED_FILES = {
    "confirmed_recent": "confirmed.xml",
    "promising_date_unconfirmed": "review.xml",
}


def live_roles(records):
    """Only still-qualifying live roles; prefer fully confirmed evidence."""
    current = {}
    for employer_id, role in records:
        item, reason = triage(employer_id, role)
        if item is None:
            continue
        key = item["role_key"]
        prev = current.get(key)
        if prev is None or (
            item["lane"] == "confirmed_recent"
            and prev["lane"] != "confirmed_recent"
        ):
            current[key] = item
    return sorted(current.values(), key=lambda x: (x["lane"], x["employer_id"], x["title"] or ""))


def render_card(item, first_seen, new_keys):
    esc = lambda v: html.escape(str(v or ""), quote=True)
    key = item["role_key"]
    is_new = key in new_keys.get(item["lane"], set())
    flag = " <strong class='new'>Nueva en este seguimiento</strong>" if is_new else ""
    posted = (f"Fecha original acreditada: {esc(item['original_date'])}"
              if item["lane"] == "confirmed_recent"
              else "Fecha original no acreditada. NO significa que sea una vacante nueva.")
    duties = ", ".join(item.get("confirmed_job_duties") or [])
    swiss_note = (
        "<p><strong>Suiza:</strong> elegibilidad para trabajar, permiso y "
        "aceptación de la candidatura sin confirmar.</p>"
        if item.get("geography") == "swiss_future" else ""
    )
    return (
        f"<article class='job'><h3><a rel='noopener noreferrer' target='_blank' href='{esc(item['url'])}'>"
        f"{esc(item['title'])}</a>{flag}</h3>"
        f"<p>{esc(item['employer_id'])} · {esc(item['location'])}</p>"
        f"<p>Funciones expresas: {esc(duties)}</p><p>{posted}</p>{swiss_note}"
        f"<small>Detectada en el historial: {esc(first_seen or 'desconocido')}. "
        "Revisar personalmente requisitos y disponibilidad antes de solicitar.</small></article>"
    )


def render_html(roles, history, report, manifest=None):
    esc = lambda v: html.escape(str(v or ""), quote=True)
    recent = {lane: [] for lane in LANES}
    for item in roles:
        recent[item["lane"]].append(item)
    new_keys = {
        lane: {x["role_key"] for x in report["new_alert_previews"][lane]}
        for lane in LANES
    }
    sections = []
    for lane in LANES:
        chunks = []
        for item in recent[lane]:
            seen = history["records"].get(item["role_key"], {}).get("first_seen")
            chunks.append(render_card(item, seen, new_keys))
        sections.append(
            f"<section id='{lane}'><h2>{esc(LANE_NAMES[lane])}</h2>"
            f"<p>{len(recent[lane])} oportunidades verificadas en esta categoría; "
            f"{len(new_keys[lane])} incorporadas al historial en este escaneo.</p>"
            + ("".join(chunks) if chunks else "<p>No hay ofertas verificadas en esta categoría.</p>")
            + "</section>"
        )
    checked = report["checked_at_utc"]
    truly_new = []
    for lane in LANES:
        for item in report["new_alert_previews"][lane]:
            seen = history["records"].get(item["role_key"], {}).get("first_seen")
            truly_new.append(render_card(item, seen, new_keys))
    newest_html = "".join(truly_new) if truly_new else (
        "<p>No se han detectado nuevas oportunidades que superen los filtros "
        "y la comparación con los anuncios oficiales previamente observados.</p>"
    )
    novelty_text = (
        "La primera revisión completa de una empresa nueva establece un historial "
        "de referencia: las ofertas sin fecha acreditada ya existentes NO generan avisos. "
        "Un cambio en el parser tampoco hace nueva una oferta antigua."
        if report.get("strict_novelty") else
        "Modo de verificación sin comparación estricta de novedades."
    )
    excluded_core=(manifest or {}).get("missing_or_failed_core",{})
    core_warning=(
        "<p><strong>Fuente temporalmente inaccesible: Payabl.</strong> "
        "Sus anuncios no se han comprobado ni incorporado en esta ejecución; "
        "las demás fuentes sí se han auditado. No debe interpretarse como "
        "cierre de vacantes ni ausencia de contrataciones.</p>"
        if excluded_core else ""
    )
    # The audited count is derived from complete evidence, never from the 339-source archive.
    return (
        "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>AML339 · Radar de {report['source_count']} fuentes verificadas</title>"
        "<style>body{font-family:system-ui,-apple-system,sans-serif;max-width:850px;"
        "margin:3rem auto;padding:0 1rem;line-height:1.55;color:#18212f;background:#f8fafc}"
        "h1{font-size:1.8rem}h2{margin-top:2rem}a{color:#1859a0}"
        "section{margin-bottom:2.5rem}.job{background:white;padding:1.2rem;"
        "border:1px solid #dce2ea;border-radius:10px;margin:1rem 0}"
        ".job h3{margin:.1rem 0}.job p{margin:.4rem 0}.job small{color:#546272}"
        ".new{color:#176332;font-size:.8rem;margin-left:.5rem}"
        ".notice{border-left:4px solid #576d89;padding:.8rem 1rem;background:#eaf0f7}"
        "</style>"
        "<link rel='alternate' type='application/rss+xml' title='AML339 confirmadas' href='confirmed.xml'>"
        "<link rel='alternate' type='application/rss+xml' title='AML339 revisión' href='review.xml'>"
        f"</head><body><h1>Radar AML339 · {report['source_count']} fuentes verificadas</h1>"
        f"<p>Última auditoría completa: {esc(checked)} UTC · "
        f"{report['source_count']}/{len(CORE+OPTIONAL)} fuentes configuradas · {report['roles_evaluated']} fichas evaluadas.</p>"
        + core_warning
        + f"<section id='novedades'><h2>Nuevas en este seguimiento: {len(truly_new)}</h2>"
        f"<p>{esc(novelty_text)}</p>{newest_html}</section>"
        "<div class='notice'><strong>Monitor independiente y conservador.</strong> "
        "El radar principal de 500 empleadores sigue separado. La fecha no acreditada "
        "no demuestra que una vacante se haya publicado recientemente. "
        "Las candidaturas se comprueban automáticamente, pero su aceptación "
        "y los requisitos deben verificarse manualmente. Sin envíos de correo automáticos.</div>"
        "<p>RSS: <a href='confirmed.xml'>Novedades confirmadas</a> · "
        "<a href='review.xml'>Revisión por fecha desconocida</a>. "
        "Los elementos conservan un identificador estable para no duplicarse.</p>"
        + "<details><summary>Ver inventario histórico y vacantes con fecha desconocida "
          "(no son nuevos descubrimientos)</summary>"
        + "".join(sections) + "</details>"
        + "<footer><p>Solo anuncios comprobados hoy; 17 fuentes esenciales, una fuente susceptible de bloqueo temporal (Payabl), más fuentes opcionales con exclusión individual de fallos; "
        "no representa la cobertura efectiva de las 339 fuentes originales.</p></footer></body></html>"
    )


def render_rss(items, history, lane, checked, source_count=18):
    channel_root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(channel_root, "channel")
    title = "AML339 — " + LANE_NAMES[lane]
    for name, text in [
        ("title", title), ("link", ROOT),
        ("description", f"Ofertas actualmente verificadas de {source_count} fuentes; "
                        "fecha de aparición en el radar no es fecha de publicación del empleo."),
        ("language", "es"),
        ("lastBuildDate", format_datetime(dt.datetime.now(dt.timezone.utc), usegmt=True)),
    ]:
        ET.SubElement(channel, name).text = text
    for entry in items:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = str(entry["title"] or "")
        ET.SubElement(item, "link").text = entry["url"]
        ET.SubElement(item, "guid", isPermaLink="false").text = (
            "aml339:" + entry["role_key"] + ":" + lane
        )
        seen = history["records"].get(entry["role_key"], {}).get("first_seen") or checked
        try:
            ts = dt.datetime.fromisoformat(seen.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                raise ValueError("Missing timezone")
            posted = format_datetime(ts.astimezone(dt.timezone.utc), usegmt=True)
        except (ValueError, TypeError):
            posted = format_datetime(dt.datetime.fromisoformat(checked).astimezone(dt.timezone.utc), usegmt=True)
        ET.SubElement(item, "pubDate").text = posted
        duty = ", ".join(entry.get("confirmed_job_duties") or [])
        note = ("Publicación original no acreditada. NO etiquetar como nueva. "
                if lane == "promising_date_unconfirmed"
                else "Fecha original verificada dentro de 72 horas en el escaneo. ")
        swiss_note = (
            "Suiza: elegibilidad laboral, permiso y aceptación de candidatura por comprobar. "
            if entry.get("geography") == "swiss_future" else ""
        )
        ET.SubElement(item, "description").text = (
            f"{entry['employer_id']} · {entry['location']} · {note}{swiss_note}"
            f"Funciones expresas: {duty}. Detección en radar: {seen}."
        )
    return ET.tostring(channel_root, encoding="unicode", xml_declaration=True)


def build(evidence_paths, state, report, output, manifest=None):
    count = report.get("source_count")
    if not isinstance(count, int) or not 17 <= count <= len(CORE+OPTIONAL):
        raise ValueError("Refuse to publish a partial core pilot scan or unexpected source count")
    if count != 18 and manifest is None:
        raise ValueError("Refuse partial or expanded source publication without a verified manifest")
    if manifest is not None and (
        manifest.get("core_expected") != 18
        or manifest.get("strict_core_expected") != 17
        or manifest.get("strict_core_verified") != 17
        or manifest.get("core_verified") not in (17,18)
        or set(manifest.get("missing_or_failed_core",{})) != (
            {"payabl"} if manifest.get("core_verified")==17 else set())
        or manifest.get("total_verified") != count
        or manifest.get("expansion_verified") != count - manifest.get("core_verified")
        or manifest.get("expansion_expected") != len(OPTIONAL)
        or manifest.get("external50_research_leads") != 50
        or manifest.get("external50_live_expected") != len(EXTERNAL50_LIVE)
        or manifest.get("external50_live_verified_ids") != [sid for sid in EXTERNAL50_LIVE if sid in set(manifest.get("verified_source_ids",[]))]
        or manifest.get("external50_live_verified") != len(manifest.get("external50_live_verified_ids",[]))
        or manifest.get("growth50_expected") != 50
        or manifest.get("growth50_verified") != sum(
            sid in set(manifest.get("verified_source_ids", []))
            for sid in manifest.get("growth50_verified_ids", []))
        or len(manifest.get("growth50_verified_ids", [])) != manifest.get("growth50_verified")
        or manifest.get("reg100_research_leads") != 100
        or manifest.get("reg100_live_expected") != 2
        or manifest.get("reg100_live_verified") != sum(
            sid in set(manifest.get("verified_source_ids",[]))
            for sid in manifest.get("reg100_live_verified_ids",[]))
        or len(manifest.get("reg100_live_verified_ids",[])) != manifest.get("reg100_live_verified")
        or manifest.get("regulator50_discovered") != 50
        or manifest.get("regulator50_live_expected") != 2
        or manifest.get("regulator50_live_verified") != sum(
            sid in set(manifest.get("verified_source_ids",[]))
            for sid in manifest.get("regulator50_live_verified_ids",[]))
        or len(manifest.get("regulator50_live_verified_ids",[])) != manifest.get("regulator50_live_verified")
        or manifest.get("bulk50_expected") != 50
        or manifest.get("bulk50_verified") != sum(
            sid in set(manifest.get("verified_source_ids", []))
            for sid in manifest.get("bulk50_verified_ids", []))
        or len(manifest.get("bulk50_verified_ids", [])) != manifest.get("bulk50_verified")
        or manifest.get("regulated_external_expected") != 5
        or manifest.get("regulated_external_verified") != sum(
            sid in set(manifest.get("verified_source_ids",[]))
            for sid in ("emi-trumia-mt","emi-zen-lt",
                        "emi-andaria-mt","emi-finxp-mt","emi-paydo-mt"))
    ):
        raise ValueError("Invalid live expansion manifest; refusing to publish")
    if set(report.get("new_counts", {})) != set(LANES):
        raise ValueError("Missing both alert lanes")
    history = check_history(state)
    roles = live_roles(read_evidence(evidence_paths))
    if len(roles) != report.get("qualifying_distinct_roles"):
        raise ValueError("Mismatch between published live jobs and audited history")
    if any(item["role_key"] not in history["records"] for item in roles):
        raise ValueError("Missing role from persistent history")
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(render_html(roles, history, report, manifest), encoding="utf-8")
    for lane, filename in FEED_FILES.items():
        lane_roles = [x for x in roles if x["lane"] == lane]
        (output / filename).write_text(
            render_rss(lane_roles, history, lane, report["checked_at_utc"], count),
            encoding="utf-8",
        )
    (output / "summary.json").write_text(json.dumps({
        "checked_at_utc": report["checked_at_utc"],
        "sources_complete": count,
        "source_count": count,
        "sources_expected": len(CORE+OPTIONAL),
        "external50_research_leads": (manifest or {}).get("external50_research_leads",0),
        "external50_live_expected": (manifest or {}).get("external50_live_expected",0),
        "external50_live_verified": (manifest or {}).get("external50_live_verified",0),
        "growth50_expected": (manifest or {}).get("growth50_expected",0),
        "growth50_verified": (manifest or {}).get("growth50_verified",0),
        "reg100_research_leads": (manifest or {}).get("reg100_research_leads",0),
        "reg100_live_expected": (manifest or {}).get("reg100_live_expected",0),
        "reg100_live_verified": (manifest or {}).get("reg100_live_verified",0),
        "regulator50_discovered": (manifest or {}).get("regulator50_discovered",0),
        "regulator50_live_expected": (manifest or {}).get("regulator50_live_expected",0),
        "regulator50_live_verified": (manifest or {}).get("regulator50_live_verified",0),
        "bulk50_expected": (manifest or {}).get("bulk50_expected",0),
        "bulk50_verified": (manifest or {}).get("bulk50_verified",0),
        "original_catalog_sources":339,
        "external_regulated_source_ids": (manifest or {}).get("regulated_external_ids",[]),
        "external_regulated_sources_verified": (manifest or {}).get("regulated_external_verified",0),
        "core_sources_complete": (manifest or {}).get("core_verified",18),
        "core_sources_expected":18,
        "strict_core_sources_complete":(manifest or {}).get("strict_core_verified",17),
        "missing_or_failed_core":(manifest or {}).get("missing_or_failed_core",{}),
        "expanded_sources_complete": count - (manifest or {}).get("core_verified",18),
        "missing_or_failed_expansion": (manifest or {}).get("missing_or_failed_expansion", {}),
        "roles_evaluated": report["roles_evaluated"],
        "current_qualifying": len(roles),
        "current_lanes": {lane: sum(x["lane"] == lane for x in roles) for lane in LANES},
        "new_counts": report["new_counts"],
        "novelty_guard_enabled": bool(report.get("strict_novelty")),
        "listing_ids_added_to_tracking_index_not_new_publications": report.get("newly_observed_listing_keys"),
        "sources_previously_baselined": report.get("sources_previously_baselined"),
        "limitations": [
            "Source discovery does not imply all 50 regulated companies have viable official job boards",
            "No automatic email/push delivery",
            "Date-unconfirmed roles are not claimed newly published",
            "New optional employer baseline and parser changes never generate false novelty alerts",
            "First-seen listing hashes indicate tracking coverage, NOT verified publication dates",
            "18 mandatory sources, 20 previously audited optional catalog providers, 50 additional original-catalog fintech boards and 5 newly sourced regulated EMI sidecar providers; original catalog remains 339",
            "Swiss roles require independent verification of work eligibility and permits",
        ],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("AML339_PUBLIC_SITE_BUILT", json.dumps({
        "current": len(roles), "new": report["new_counts"]
    }, ensure_ascii=False), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sources-file", required=True)
    p.add_argument("--state-file", required=True)
    p.add_argument("--report-file", required=True)
    p.add_argument("--dest", required=True)
    p.add_argument("--manifest-file")
    a = p.parse_args()
    paths = [Path(line.strip()) for line in Path(a.sources_file).read_text().splitlines() if line.strip()]
    if not 17 <= len(paths) <= len(CORE+OPTIONAL):
        raise ValueError("Expected 17-18 independently audited core sources and the configured complete optional source snapshots")
    state = json.loads(Path(a.state_file).read_text(encoding="utf-8"))
    report = json.loads(Path(a.report_file).read_text(encoding="utf-8"))
    manifest = json.loads(Path(a.manifest_file).read_text(encoding="utf-8")) if a.manifest_file else None
    build(paths, state, report, Path(a.dest), manifest)


if __name__ == "__main__":
    main()
