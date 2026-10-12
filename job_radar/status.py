"""Human-readable/public heartbeat independent of vacancy counts.

This file is regenerated at every successful scan, even when there are no
new jobs. An old timestamp makes a stalled GitHub Actions scan visible.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from job_radar.config import ROOT
from job_radar.models import utcnow_iso


def build_status(health: list[dict], stats: dict,
                 out_dir: str = "public", generated_at: str = "") -> dict:
    now = generated_at or utcnow_iso()
    records = [r for r in health if not r.get("company", "").startswith("v2 ")]
    skipped = [r for r in records if any(
        "disabled" in str(t.get("kind", "")).lower()
        for t in r.get("targets", []) if isinstance(t, dict)
    ) or str(r.get("error", "")).startswith(("SKIPPED:", "skipped this hour"))]
    checked = [r for r in records if r not in skipped]
    reachable = sum(bool(x.get("ok")) for x in checked)
    productive = sum(bool(x.get("ok")) and int(x.get("jobs", 0)) > 0
                     for x in checked)
    failed = len(checked) - reachable
    snapshot = {
        "checked_at_utc": now,
        "source_checks": len(checked),
        "source_checks_skipped": len(skipped),
        "reachable_source_checks": reachable,
        "source_checks_with_jobs": productive,
        "source_checks_failed": failed,
        "active_verified_jobs": int(stats.get("active_dashboard", 0)),
        "historical_seen": int(stats.get("seen_forever", 0)),
        "notice": (
            "Counts are source checks, not unique employers. "
            "A reachable source does not guarantee every vacancy is indexed. "
            "Only ATS-verified fresh jobs enter the main dashboard."
        ),
    }
    root = ROOT / out_dir
    root.mkdir(parents=True, exist_ok=True)
    (root / "status.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fields = [
        ("Última ejecución UTC", now),
        ("Comprobaciones de fuentes", str(len(checked))),
        ("Fuentes omitidas (sin clave/cadencia)", str(len(skipped))),
        ("Fuentes que respondieron", str(reachable)),
        ("Fuentes con vacantes", str(productive)),
        ("Fuentes con error", str(failed)),
        ("Vacantes verificadas visibles", str(snapshot["active_verified_jobs"])),
        ("Vacantes conocidas en histórico", str(snapshot["historical_seen"])),
    ]
    cards = "\n".join(
        '<div class="card"><span>' + html.escape(label) +
        '</span><strong>' + html.escape(value) + '</strong></div>'
        for label, value in fields
    )
    doc = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Estado — Radar AML</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f5f7fb;color:#1d2939;margin:0}}
main{{max-width:860px;margin:3rem auto;padding:1rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}
.card{{background:white;border:1px solid #e4e7ec;border-radius:12px;padding:18px}}
.card span{{display:block;color:#667085;font-size:.85rem;margin-bottom:8px}}
.card strong{{font-size:1.3rem}}
p{{line-height:1.6;color:#475467}} a{{color:#155eef}}
</style></head><body><main>
<h1>Estado del Radar AML</h1>
<p>Este sello de tiempo se actualiza tras cada exploración completada. Si permanece
antiguo respecto a la frecuencia prevista, comprueba las ejecuciones de GitHub Actions.</p>
<div class="grid">{cards}</div>
<p>Las cifras corresponden a <b>comprobaciones</b>, no a empresas únicas.
Un origen puede responder sin ofrecer vacantes apropiadas.
Un cero en el dashboard no significa necesariamente que el radar esté caído.</p>
<p><a href="index.html">Dashboard de ofertas</a> ·
<a href="sources.html">Fuentes y empresas</a> · <a href="feed.xml">RSS de novedades</a> ·
<a href="status.json">Estado en JSON</a></p>
</main></body></html>"""
    (root / "status.html").write_text(doc, encoding="utf-8")
    return snapshot
