"""Auditable employer-source coverage: configured != reachable != jobs observed."""
from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from job_radar.config import ROOT
from job_radar.models import norm_text


def summarize_source_coverage(companies: list[dict], health: list[dict],
                              direct_company_names: set[str] | None = None) -> dict:
    # Scan batches include rotating directory firms; do not call them direct.
    if direct_company_names is None:
        direct_company_names = {norm_text(c.get("name")) for c in companies}
    by_name = {}
    for check in health:
        name = check.get("company", "")
        if name and not name.startswith("v2 "):
            by_name.setdefault(name, []).append(check)
    records = []
    for c in companies:
        if c.get("enabled", True) is False:
            continue
        name = c.get("name", "")
        results = by_name.get(name, [])
        # Fresh scan results only. If source was not included in this scan,
        # its status is "not_checked", never "ok".
        status = ("ok" if any(r.get("ok") for r in results)
                  else "error" if results else "not_checked")
        records.append({
            "company": name,
            "origin_class": "direct" if norm_text(name) in direct_company_names else "rotating",
            "category": c.get("specialism") or c.get("sector") or "Fintech",
            "configured_feed": "ATS API" if c.get("ats") else "Careers site / discovery",
            "result": status,
            "jobs_found": sum(int(x.get("jobs") or 0) for x in results),
            "url": c.get("careers_url") or "",
        })
    counts = Counter(r["result"] for r in records)
    return {
        "total_configured_checked_or_scheduled": len(records),
        "direct_configured": sum(r["origin_class"] == "direct" for r in records),
        "rotating_checked": sum(r["origin_class"] == "rotating" for r in records),
        "ats_explicit": sum(bool(c.get("ats")) for c in companies if c.get("enabled", True)),
        "careers_discovery": sum(not c.get("ats") for c in companies if c.get("enabled", True)),
        "reached": counts["ok"], "errors": counts["error"],
        "not_checked": counts["not_checked"],
        "with_jobs": sum(r["result"] == "ok" and r["jobs_found"] > 0 for r in records),
        "by_specialism": dict(Counter(r["category"] for r in records)),
        "sources": records,
        "note": (
            "Employer sources are not individually verified vacancy alerts. "
            "ATS API means a configured connector, not proof the provider API "
            "currently responds. Open applications have a separate 96-hour gate."
        ),
    }


def build_source_inventory(companies: list[dict], health: list[dict],
                           out_dir: str = "public",
                           direct_company_names: set[str] | None = None) -> dict:
    summary = summarize_source_coverage(companies, health, direct_company_names)
    root = ROOT / out_dir if not Path(out_dir).is_absolute() else Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "sources.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rows = []
    for source in sorted(summary["sources"], key=lambda x: (x["category"],x["company"])):
        url = source["url"]
        parsed = urlsplit(url)
        url_safe = url if parsed.scheme == "https" and parsed.netloc else ""
        label = html.escape(source["company"])
        if url_safe:
            label = ('<a href="' + html.escape(url_safe, quote=True)
                     + '" rel="noopener noreferrer" target="_blank">' + label + '</a>')
        rows.append(
            "<tr><td>" + label + "</td><td>" + html.escape(source["category"])
            + "</td><td>" + html.escape(source["configured_feed"])
            + "</td><td>" + html.escape(source["result"])
            + "</td><td>" + str(source["jobs_found"]) + "</td></tr>"
        )
    page = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fuentes del Radar AML</title><style>
body{{font:14px system-ui,sans-serif;margin:2rem auto;padding:0 1rem;
max-width:1200px;color:#182230;background:#f9fafb}}
table{{border-collapse:collapse;width:100%;background:#fff}}
th,td{{padding:12px;border-bottom:1px solid #eee;text-align:left}}
th{{position:sticky;top:0;background:#e9eff5}}
.summary{{font-weight:600}}a{{color:#1654aa}}
</style></head><body><h1>Fuentes auditables · Radar AML</h1>
<p>Este inventario distingue empresas con ATS configurado, webs de empleo
pendientes de descubrimiento, respuestas correctas y fallos. Las cifras
NO son vacantes abiertas ni fuentes ATS garantizadas.</p>
<p class="summary">Fuentes en esta pasada: {total} · Empresas directas: {direct} ·
Rotatorias incluidas: {rotating} · ATS configurados: {ats} ·
Webs de empleo: {generic} · Respondieron: {ok} · Errores: {errors} ·
No consultadas: {missing} · Con vacantes brutas: {productive}</p>
<p><a href="index.html">Vacantes verificadas</a> · <a href="status.html">Estado</a></p>
<table><thead><tr><th>Empresa</th><th>Especialidad</th><th>Integración</th>
<th>Última comprobación</th><th>Anuncios brutos</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>""".format(
        total=summary["total_configured_checked_or_scheduled"],
        direct=summary["direct_configured"],
        rotating=summary["rotating_checked"],
        ats=summary["ats_explicit"],generic=summary["careers_discovery"],
        ok=summary["reached"],errors=summary["errors"],
        missing=summary["not_checked"],productive=summary["with_jobs"],
        rows="\n".join(rows),
    )
    (root / "sources.html").write_text(page, encoding="utf-8")
    return summary
