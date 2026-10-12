"""Read-only list of ambiguous official postings excluded from notifications.

Only the verified dashboard and RSS are actionable alerts. This diagnostic
page may include unknown dates, inaccessible apply forms, or unrelated roles:
neither freshness nor an open application has been established.
"""
from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import urlsplit

from job_radar.config import ROOT
from job_radar.models import norm_text
from job_radar.v2_quality import within_new_window

RELEVANT_TITLE_TERMS = (
    "kyc", "kyb", "aml", "edd", "cdd", "compliance", "fincrime",
    "financial crime", "sanction", "screening", "due diligence",
    "transaction monitoring", "fi u", "investigat", "merchant risk",
    "onboarding", "fraud", "source of funds", "source of wealth",
)
REASON_NAMES = {
    "page_200_but_no_visible_apply_action": "Formulario no detectable",
    "original_publication_missing_or_older_than_96h": "Fecha original sin confirmar o antigua",
    "explicitly_closed": "Cerrada (no elegible)",
}


def review_candidates(records: list[dict], seen: dict | None = None,
                      max_count: int = 80) -> list[dict]:
    from job_radar.v2_quality import original_posted_at
    seen = seen or {}
    out, dedupe = [], set()
    for rec in records:
        if not isinstance(rec, dict):
            continue
        title, company = str(rec.get("title") or ""), str(rec.get("company") or "")
        normalized_title = norm_text(title)
        if not company or not any(word in normalized_title for word in RELEVANT_TITLE_TERMS):
            continue
        # An unconfirmed "remote Europe" hint is not valid Spain/Canaries
        # eligibility, and London office jobs must never appear here.
        if rec.get("geography_verified") is not True:
            continue
        reason = str(rec.get("reason") or "")
        # Confirmed old/closed postings must not slip into this side list.
        if reason == "explicitly_closed":
            continue
        posted = rec.get("posted_at", "")
        if original_posted_at(posted) is not None and not within_new_window(posted):
            continue
        link = str(rec.get("url") or "")
        parsed = urlsplit(link)
        if parsed.scheme != "https" or not parsed.netloc:
            continue
        identity = (norm_text(company), normalized_title, link)
        if identity in dedupe:
            continue
        # Suppress positions explicitly known from previous reports as well.
        already_known = any(
            norm_text(x.get("company")) == norm_text(company)
            and norm_text(x.get("title")) == normalized_title
            for x in seen.values() if isinstance(x, dict)
        )
        if already_known:
            continue
        dedupe.add(identity)
        out.append({
            "company": company, "title": title,
            "location": str(rec.get("location") or ""),
            "posted_at": posted,
            "url": link, "reason": REASON_NAMES.get(reason, reason),
        })
    out.sort(key=lambda j: (not within_new_window(j["posted_at"]), -sum(t in norm_text(j["title"]) for t in ("kyc", "kyb", "aml", "financial crime", "edd", "sanction", "transaction monitoring", "investigat")), j["company"]))
    return out[:max_count]


def build_review_page(records: list[dict], seen: dict | None = None,
                      out_path: str = "public/review.html") -> int:
    accepted = review_candidates(records, seen)
    root = ROOT / out_path if not Path(out_path).is_absolute() else Path(out_path)
    root.parent.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        "<tr><td>" + ("Prioritaria · " if within_new_window(rec["posted_at"]) else "") + html.escape(rec["company"]) + "</td><td>" +
        '<a href="' + html.escape(rec["url"], quote=True) +
        '" target="_blank" rel="noopener noreferrer">' +
        html.escape(rec["title"]) + "</a></td><td>" +
        html.escape(rec["location"]) + "</td><td>" +
        html.escape(str(rec["posted_at"] or "Desconocida")) + "</td><td>" +
        html.escape(rec["reason"]) + "</td></tr>"
        for rec in accepted
    )
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pendientes de verificar — Radar AML</title><style>
body{{background:#f8fafc;color:#1e293b;font:15px system-ui,sans-serif;padding:2rem;max-width:1200px;margin:auto}}
table{{width:100%;border-collapse:collapse;background:white}}
th,td{{padding:12px;border-bottom:1px solid #dbe2e8;text-align:left}}
th{{background:#e8eef5}} a{{color:#175cd3}}
.notice{{border:1px solid #ffd591;background:#fff8e7;padding:16px;border-radius:8px}}
</style></head><body>
<h1>Publicaciones pendientes de revisión</h1>
<div class="notice"><b>NO SON OFERTAS VERIFICADAS NI ALERTAS.</b>
La fecha puede ser desconocida o el formulario imposible de comprobar automáticamente.
Las publicaciones recientes aparecen primero, marcadas como prioritarias, pero tampoco son ofertas confirmadas. Antes de aplicar,
comprueba manualmente que la oferta está abierta y permite trabajar en la ubicación indicada.</div>
<p>{len(accepted)} enlaces potencialmente relevantes, sin duplicados ya comunicados.</p>
<table><thead><tr><th>Empresa</th><th>Rol</th><th>Ubicación</th>
<th>Fecha declarada</th><th>Motivo de duda</th></tr></thead>
<tbody>{rows}</tbody></table>
<p><a href="index.html">Volver a ofertas verificadas</a> ·
<a href="status.html">Estado del rastreo</a></p></body></html>"""
    root.write_text(doc, encoding="utf-8")
    return len(accepted)
