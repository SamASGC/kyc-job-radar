from __future__ import annotations

import re
from job_radar.models import Job, norm_text

# Broad annual gross base estimates. These are deliberately ranges and always labelled "estimado".
BANDS = {
    "Spain": {"analyst": (32000, 43000, "EUR"), "senior": (42000, 57000, "EUR")},
    "Luxembourg": {"analyst": (50000, 68000, "EUR"), "senior": (65000, 85000, "EUR")},
    "Switzerland": {"analyst": (85000, 105000, "CHF"), "senior": (100000, 125000, "CHF")},
    "Germany": {"analyst": (48000, 65000, "EUR"), "senior": (60000, 80000, "EUR")},
    "Netherlands": {"analyst": (47000, 64000, "EUR"), "senior": (58000, 78000, "EUR")},
    "France": {"analyst": (42000, 57000, "EUR"), "senior": (52000, 70000, "EUR")},
    "Portugal": {"analyst": (28000, 40000, "EUR"), "senior": (38000, 52000, "EUR")},
    "Belgium": {"analyst": (45000, 62000, "EUR"), "senior": (58000, 76000, "EUR")},
    "Austria": {"analyst": (45000, 61000, "EUR"), "senior": (56000, 73000, "EUR")},
    "Ireland": {"analyst": (45000, 60000, "EUR"), "senior": (58000, 76000, "EUR")},
    "United Kingdom": {"analyst": (38000, 52000, "GBP"), "senior": (50000, 68000, "GBP")},
    "Italy": {"analyst": (32000, 44000, "EUR"), "senior": (42000, 56000, "EUR")},
}


def format_money(n: int, currency: str) -> str:
    sym = {"EUR": "€", "GBP": "£", "CHF": "CHF "}.get(currency, currency + " ")
    if currency == "CHF":
        return f"{sym}{n//1000}k"
    return f"{sym}{n//1000}k"


def published_salary(job: Job) -> str:
    s = (job.salary_text or "").strip()
    if not s:
        return ""
    # Avoid mistaking empty/placeholder salary metadata as useful.
    if norm_text(s) in {"none", "null", "not specified", "0 0"}:
        return ""
    return f"{s} · publicado"


def estimate_salary(job: Job) -> str:
    pub = published_salary(job)
    if pub:
        return pub
    country = job.country
    if not country and job.location_mode == "Remoto":
        country = "Spain"  # practical home-base estimate for Europe-remote roles
    band = BANDS.get(country)
    if not band:
        return "No estimado"
    title = norm_text(job.title)
    senior = bool(re.search(r"\b(senior|sr|lead)\b", title)) and not re.search(r"\b(junior|jr)\b", title)
    lo, hi, cur = band["senior" if senior else "analyst"]
    # Payments / crypto / specialist financial-crime roles often price a little higher.
    if job.sector == "Payments" and job.score >= 85:
        lo = int(lo * 1.05); hi = int(hi * 1.05)
    return f"{format_money(lo, cur)}–{format_money(hi, cur)} · estimado"
