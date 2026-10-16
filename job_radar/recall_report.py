"""Read-only recall diagnostics: never an ATS approval or user alert.

Run-level funnel totals do not establish which vacancies were lost. This
report exposes bounded, source-backed examples for later investigation and
does not relax any score/date/language/geography/official-apply rules.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import urlsplit
from job_radar.config import ROOT
from job_radar.models import norm_text, utcnow_iso
from job_radar.v2_quality import original_posted_at, within_new_window

ROLE_TITLES = (
    "kyc", "kyb", "aml", "fincrime", "financial crime", "compliance",
    "sanction", "risk monitoring", "transaction monitoring", "edd",
    "due diligence", "onboarding", "screening", "investigat", "fraud",
)

FUNNEL_LABELS = (
    ("raw_total", "Registros brutos consultados"),
    ("official_ats", "Anuncios oficiales (ATS/careers)"),
    ("official_in_scope", "Geografía preliminar válida"),
    ("original_date_recent", "Fecha original reciente"),
    ("original_date_missing", "Fecha original no demostrada"),
    ("original_date_expired", "Fecha original fuera de 96h"),
    ("prefiltered_candidates", "Candidatos enviados a comprobación"),
    ("official_apply_page_verified", "Página candidatura verificada"),
    ("application_not_verified", "Sin prueba suficiente de candidatura/fecha"),
    ("mandatory_language_filtered", "Descartes por idiomas obligatorios"),
    ("verified_score_accepted", "Verificados y compatibles en puntuación"),
    ("verified_score_rejected", "Verificados pero rechazados en encaje"),
)


def _valid_official_url(url: str) -> bool:
    p = urlsplit(url)
    return p.scheme == "https" and bool(p.netloc) and not p.username


def select_recall_examples(audit: dict, max_count: int = 60) -> list[dict]:
    """Only relevant-title examples, never interpret unknown date as fresh."""
    records = []
    for source, stage in (
        (audit.get("verified_score_rejects", []), "Encaje insuficiente (candidatura comprobada)"),
        (audit.get("rejected_examples", []), "Falta prueba de fecha, candidatura o idiomas"),
    ):
        for v in source:
            if not isinstance(v, dict):
                continue
            title = str(v.get("title") or "")
            if not any(term in norm_text(title) for term in ROLE_TITLES):
                continue
            if v.get("geography_verified") is not True:
                continue
            url = str(v.get("url") or "")
            if not _valid_official_url(url):
                continue
            date = str(v.get("posted_at") or "")
            # A confirmed old date means it's not a useful missing alert.
            if original_posted_at(date) is not None and not within_new_window(date):
                continue
            records.append({
                "company": str(v.get("company") or ""),
                "title": title,
                "location": str(v.get("location") or ""),
                "url": url,
                "posted_at": date,
                "stage": stage,
                "reason": str(v.get("reason") or ""),
                "score": v.get("score") if stage.startswith("Encaje") else None,
                "original_date_proven": original_posted_at(date) is not None,
            })
    dedupe: dict[tuple[str, str, str], dict] = {}
    for v in records:
        k=(norm_text(v["company"]),norm_text(v["title"]),v["url"])
        dedupe.setdefault(k,v)
    rows=list(dedupe.values())
    rows.sort(key=lambda v: (
        not v["stage"].startswith("Encaje"),
        not v["original_date_proven"],
        -sum(term in norm_text(v["title"]) for term in ("kyc","aml","kyb","compliance","sanction","financial crime","edd")),
        v["company"],
    ))
    return rows[:max_count]


def build_recall_report(audit: dict, *, out_dir: str = "public") -> dict:
    counts = {k: int(audit.get(k, 0)) for k, _ in FUNNEL_LABELS}
    examples = select_recall_examples(audit)
    report = {
        "checked_at_utc": utcnow_iso(),
        "warning": "AUDITORÍA NO VERIFICADA: estas filas NO son ofertas ni alertas. Fecha, candidatura o encaje pueden impedir una postulación válida.",
        "funnel": counts, "examples": examples,
        "limitations": (
            "Los recuentos incluyen registros repetidos de diferentes fuentes; "
            "las muestras están limitadas y no son una auditoría exhaustiva de recall. "
            "La antigüedad de una fecha desconocida NO puede inferirse."
        ),
    }
    root=ROOT/out_dir if not Path(out_dir).is_absolute() else Path(out_dir)
    root.mkdir(parents=True,exist_ok=True)
    (root/"recall.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    totals="".join(
        "<tr><td>"+html.escape(label)+"</td><td>"+str(counts[key])+"</td></tr>"
        for key,label in FUNNEL_LABELS
    )
    items="".join(
        "<tr><td>"+html.escape(v["company"])+"</td>"
        "<td><a href=\""+html.escape(v["url"],quote=True)+"\" rel=\"noopener noreferrer\" target=\"_blank\">"
        +html.escape(v["title"])+"</a></td>"
        "<td>"+html.escape(v["location"])+"</td>"
        "<td>"+html.escape(v["stage"])+"</td>"
        "<td>"+html.escape(v["reason"])+"</td>"
        "<td>"+html.escape(v["posted_at"] or "Sin fecha original confirmada")+"</td></tr>"
        for v in examples
    )
    page=f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Auditoría de descartes — Radar AML Europa</title>
<style>body{{background:#f7f8fb;color:#1d2939;font:15px system-ui,sans-serif;padding:20px;max-width:1220px;margin:auto}}
table{{width:100%;border-collapse:collapse;background:white;margin-bottom:30px}}
td,th{{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #ddd}}
th{{background:#e9edf4}}a{{color:#1359bb}}
.notice{{border:2px solid #da9c31;background:#fff6df;border-radius:8px;padding:16px;line-height:1.6}}
.small{{color:#475467;line-height:1.6}}</style></head><body>
<h1>Auditoría de descartes y cobertura</h1>
<p class="notice"><strong>NO SON OFERTAS VERIFICADAS NI ALERTAS.</strong>
Los ejemplos siguientes han fallado algún filtro de fecha original, candidatura, idiomas o encaje.
No se debe afirmar que están disponibles ni que se han perdido realmente.</p>
<p class="small">Última ejecución UTC: {html.escape(report["checked_at_utc"])}.
{html.escape(report["limitations"])}</p>
<h2>Embudo de comprobación</h2>
<table><tbody>{totals}</tbody></table>
<h2>Muestras para investigar (máximo 60)</h2>
<table><thead><tr><th>Empresa</th><th>Rol</th><th>Ubicación</th><th>Fase</th><th>Motivo</th><th>Fecha ATS</th></tr></thead>
<tbody>{items}</tbody></table>
<p><a href="index.html">Ofertas verificadas</a> ·
<a href="review.html">Pendientes de comprobar</a> ·
<a href="recall.json">Datos del informe</a></p></body></html>"""
    (root/"recall.html").write_text(page,encoding="utf-8")
    return report
