from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
from dateutil import parser as dtparser
from job_radar.models import Job, norm_text

ROLE_TERMS = {
    "kyc": 30, "kyb": 30, "customer due diligence": 30, "due diligence": 24,
    "cdd": 28, "edd": 23, "enhanced due diligence": 26, "onboarding": 22,
    "aml": 26, "anti money laundering": 28, "financial crime": 28, "fincrime": 28,
    "anti financial crime": 28, "afc": 24, "sanctions": 22, "screening": 20,
    "transaction monitoring": 20, "investigations": 18, "fraud": 16,
    "risk operations": 18, "merchant risk": 22, "payment risk": 20,
    "compliance operations": 22, "client lifecycle": 22, "customer verification": 24,
    "business verification": 24, "financial integrity": 18,
}

FINANCE_TERMS = [
    "fintech", "payment", "payments", "bank", "banking", "neobank", "e money", "money transfer",
    "remittance", "remittances", "crypto", "exchange", "broker", "trading", "cards", "card issuing",
    "merchant", "acquiring", "financial services", "financial crime", "aml", "kyc", "kyb", "lending",
    "wealth", "open banking", "regtech", "identity verification", "fx", "foreign exchange",
]

CURRENT_SKILLS = {
    "kyc", "kyb", "cdd", "corporate onboarding", "merchant onboarding", "business verification",
    "ubo", "beneficial ownership", "complex ownership", "high risk cdd", "edd support",
    "pep", "sanctions screening", "adverse media", "financial crime red flags", "risk based assessment",
    "escalations", "audit ready documentation", "quality review", "sop", "sla", "regulated payments",
    "periodic review", "trigger based review", "directors", "corporate documentation",
}

GROWTH_SKILLS = [
    ("transaction monitoring", ["transaction monitoring", "transaction-monitoring", "tm alerts", "tm alert"]),
    ("SAR/STR drafting", ["sar", "suspicious activity report", "str", "suspicious transaction report"]),
    ("AML investigations", ["aml investigation", "financial crime investigation", "case investigation"]),
    ("sanctions investigations", ["sanctions investigation", "sanctions advisory", "sanction escalation"]),
    ("customer risk rating", ["customer risk rating", "risk rating", "customer risk assessment"]),
    ("merchant risk", ["merchant risk", "merchant underwriting", "merchant monitoring"]),
    ("payment investigations", ["payment investigation", "payments investigation", "payment monitoring"]),
    ("fraud investigations", ["fraud investigation", "fraud operations", "fraud monitoring"]),
    ("regulatory reporting", ["regulatory reporting", "regulatory filing", "regulator reporting"]),
    ("correspondent banking", ["correspondent banking", "financial institutions due diligence", "fidd"]),
    ("crypto compliance", ["crypto compliance", "blockchain analytics", "virtual assets", "vasp"]),
    ("cards/acquiring risk", ["acquiring", "card acquiring", "card issuing", "cards risk"]),
    ("screening tooling", ["world-check", "worldcheck", "dow jones risk", "lexisnexis", "screening tool"]),
    ("SQL/data analysis", ["sql", "data analysis", "analytics"]),
]



NON_JOB_CONTENT_PATH = re.compile(
    r"/(?:learn|blog|resources?|glossary|academy|guides?|whitepapers?|webinars?|podcasts?|events?|customers?|case-stud(?:y|ies)|docs?|documentation|regulations?)(?:/|$)",
    re.I,
)
NON_JOB_CONTENT_TITLE = re.compile(
    r"\b(?:glossary|whitepaper|webinar|podcast|case study|regulations? directory|resource library|knowledge base|blog post|research report|guide to|handbook)\b",
    re.I,
)


def obvious_non_job_content(source_kind: str, title: str, apply_url: str) -> bool:
    """Reject content/resources accidentally linked from custom career pages.

    Structured ATS and aggregator records are not affected.
    """
    if source_kind != "official career page":
        return False
    path = urlsplit(apply_url or "").path.lower()
    if NON_JOB_CONTENT_PATH.search(path):
        return True
    if NON_JOB_CONTENT_TITLE.search(title or ""):
        return True
    return False


HARD_EXCLUDE_TITLE = [
    "software engineer", "data engineer", "data scientist", "developer", "product designer", "account executive",
    "sales manager", "business development", "marketing", "recruiter", "talent acquisition", "customer success manager",
]

COUNTRY_ALIASES = {
    # Target countries / Europe
    "spain": "Spain", "españa": "Spain", "madrid": "Spain", "malaga": "Spain", "málaga": "Spain",
    "canary islands": "Spain", "barcelona": "Spain", "valencia": "Spain", "sevilla": "Spain",
    "luxembourg": "Luxembourg", "luxemburgo": "Luxembourg", "munsbach": "Luxembourg",
    "switzerland": "Switzerland", "swiss": "Switzerland", "zurich": "Switzerland", "zürich": "Switzerland",
    "gland": "Switzerland", "geneva": "Switzerland", "genève": "Switzerland", "lausanne": "Switzerland", "zug": "Switzerland",
    "germany": "Germany", "berlin": "Germany", "frankfurt": "Germany", "munich": "Germany", "münchen": "Germany",
    "netherlands": "Netherlands", "amsterdam": "Netherlands", "france": "France", "paris": "France",
    "portugal": "Portugal", "lisbon": "Portugal", "lisboa": "Portugal", "italy": "Italy", "milan": "Italy", "rome": "Italy",
    "ireland": "Ireland", "dublin": "Ireland", "united kingdom": "United Kingdom", "london": "United Kingdom", " uk ": "United Kingdom",
    "belgium": "Belgium", "brussels": "Belgium", "austria": "Austria", "vienna": "Austria",
    "poland": "Poland", "warsaw": "Poland", "estonia": "Estonia", "tallinn": "Estonia", "lithuania": "Lithuania", "vilnius": "Lithuania",
    "latvia": "Latvia", "riga": "Latvia", "romania": "Romania", "bucharest": "Romania", "sweden": "Sweden", "stockholm": "Sweden",
    "denmark": "Denmark", "copenhagen": "Denmark", "finland": "Finland", "helsinki": "Finland", "czechia": "Czechia", "czech republic": "Czechia", "prague": "Czechia",
    "greece": "Greece", "athens": "Greece", "bulgaria": "Bulgaria", "sofia": "Bulgaria", "malta": "Malta", "valletta": "Malta",
    "cyprus": "Cyprus", "limassol": "Cyprus", "nicosia": "Cyprus", "slovakia": "Slovakia", "bratislava": "Slovakia",
    "slovenia": "Slovenia", "ljubljana": "Slovenia", "hungary": "Hungary", "budapest": "Hungary", "croatia": "Croatia", "zagreb": "Croatia",
    "norway": "Norway", "oslo": "Norway", "iceland": "Iceland", "liechtenstein": "Liechtenstein", "serbia": "Serbia", "belgrade": "Serbia",
    "montenegro": "Montenegro", "bosnia": "Bosnia and Herzegovina", "north macedonia": "North Macedonia", "albania": "Albania",
    # Common non-European locations: detecting them prevents false 'remote Europe' positives.
    "united states": "United States", " usa ": "United States", "new york": "United States", "san francisco": "United States",
    "canada": "Canada", "toronto": "Canada", "india": "India", "mumbai": "India", "bangalore": "India", "bengaluru": "India",
    "singapore": "Singapore", "australia": "Australia", "philippines": "Philippines", "manila": "Philippines",
    "united arab emirates": "United Arab Emirates", " uae ": "United Arab Emirates", "dubai": "United Arab Emirates",
    "south africa": "South Africa", "cape town": "South Africa", "johannesburg": "South Africa",
    "brazil": "Brazil", "mexico": "Mexico", "argentina": "Argentina", "hong kong": "Hong Kong", "malaysia": "Malaysia", "kuala lumpur": "Malaysia",
}

EUROPE_COUNTRIES = {
    "Spain", "Luxembourg", "Switzerland", "Germany", "Netherlands", "France", "Portugal", "Italy", "Ireland",
    "United Kingdom", "Belgium", "Austria", "Poland", "Estonia", "Lithuania", "Latvia", "Romania", "Sweden", "Denmark",
    "Finland", "Czechia", "Greece", "Bulgaria", "Malta", "Cyprus", "Slovakia", "Slovenia", "Hungary", "Croatia",
    "Norway", "Iceland", "Liechtenstein", "Serbia", "Montenegro", "Bosnia and Herzegovina", "North Macedonia", "Albania",
}


EUROPE_TERMS = ["europe", "emea", "eu", "european union", "worldwide", "global", "anywhere"]
BLOCKED_REMOTE_TERMS = ["remote usa", "remote us", "united states only", "us only", "canada only", "latin america only", "latam only"]


def infer_sector(job: Job, known_company: bool = False) -> str:
    if known_company and job.sector in {"Fintech", "Banca", "Payments"}:
        return job.sector
    blob = norm_text(" ".join([job.company, job.title, job.description]))
    if any(x in blob for x in ["payment", "acquiring", "merchant", "remittance", "money transfer", "card issuing", "open banking", "fx"]):
        return "Payments"
    if any(x in blob for x in ["bank", "banking", "neobank", "lending", "savings", "wealth bank"]):
        return "Banca"
    return "Fintech"


def financial_context(job: Job, known_company: bool = False) -> bool:
    if known_company:
        return True
    blob = norm_text(" ".join([job.company, job.title, job.description]))
    return any(t in blob for t in FINANCE_TERMS)


def role_relevance(title: str, description: str) -> tuple[int, list[str]]:
    t = norm_text(title)
    d = norm_text(description)
    hits = []
    best = 0
    for term, pts in ROLE_TERMS.items():
        if term in t:
            hits.append(term)
            best = max(best, pts)
    desc_hits = [term for term in ROLE_TERMS if term in d]
    if best == 0:
        if len(desc_hits) >= 2:
            best = min(20, 8 + len(desc_hits) * 2)
            hits.extend(desc_hits[:5])
    elif desc_hits:
        # A broad title such as "Compliance Analyst" can hide an almost exact KYB/CDD role.
        # Reward corroborating duties in the description without allowing this block above 30 pts.
        best = min(30, best + min(8, len(set(desc_hits))))
        for term in desc_hits:
            if term not in hits:
                hits.append(term)
    return best, hits


def extract_growth_skills(job: Job) -> list[str]:
    blob = norm_text(job.title + " " + job.description)
    out = []
    for label, aliases in GROWTH_SKILLS:
        if any(norm_text(a) in blob for a in aliases):
            # Avoid reporting as new if already clearly in current skill bank.
            if norm_text(label) not in CURRENT_SKILLS:
                out.append(label)
    return out[:5]


def detect_mode(job: Job) -> str:
    blob = norm_text(" ".join([job.location, job.remote_hint, job.title, job.description[:1500]]))
    if "hybrid" in blob or "hibrid" in blob:
        return "Híbrido"
    if "remote" in blob or "remoto" in blob or "work from home" in blob:
        return "Remoto"
    if "on site" in blob or "onsite" in blob or "on-site" in (job.location + job.description).lower():
        return "Presencial"
    return "Presencial" if job.location else "No indicado"


def detect_country(location: str) -> str:
    low = norm_text(location)
    for alias, country in COUNTRY_ALIASES.items():
        a = norm_text(alias)
        if not a:
            continue
        if len(a) <= 3:
            if re.search(rf"(?:^|\s){re.escape(a)}(?:$|\s)", low):
                return country
        elif a in low:
            return country
    return ""


def parse_age_days(posted_at) -> float | None:
    if posted_at is None or posted_at == "":
        return None
    # Some public job APIs expose Unix timestamps as integers (e.g. Arbeitnow).
    if isinstance(posted_at, (int, float)):
        try:
            value = float(posted_at)
            # Also tolerate milliseconds.
            if value > 10_000_000_000:
                value /= 1000.0
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)
        except (ValueError, OSError, OverflowError):
            return None
    text = str(posted_at).strip()
    # Humanized ATS values.
    m = re.search(r"(\d+)\s+day", text.lower())
    if m:
        return float(m.group(1))
    if "today" in text.lower():
        return 0.0
    if "yesterday" in text.lower():
        return 1.0
    try:
        dt = dtparser.parse(text)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 86400)
    except Exception:
        return None


def extract_years_required(description: str) -> int | None:
    d = description.lower()
    vals = []
    for m in re.finditer(r"(?:at least|min(?:imum)?\s*)?(\d{1,2})\+?\s*(?:years?|yrs?|años?)", d):
        v = int(m.group(1))
        if 0 <= v <= 20:
            vals.append(v)
    return min(vals) if vals else None


def language_adjustment(description: str) -> tuple[int, list[str]]:
    d = norm_text(description)
    reasons = []
    score = 0
    if "spanish" in d or "espanol" in d:
        score += 2; reasons.append("español")
    if "french" in d or "francais" in d:
        score += 2; reasons.append("francés")
    mandatory_other = ["native german", "fluent german", "german c1", "native dutch", "fluent dutch", "native italian", "fluent italian"]
    if any(x in d for x in mandatory_other):
        score -= 7; reasons.append("idioma local exigido")
    return score, reasons


def location_score_and_allowed(job: Job, preliminary_score: int, skills: list[str], profile: dict) -> tuple[int, bool, str]:
    mode = detect_mode(job)
    country = detect_country(job.location)
    low = norm_text(job.location + " " + job.remote_hint)
    onsite_allowed = set(profile.get("onsite_hybrid_countries", ["Spain", "Luxembourg", "Switzerland"]))

    if mode == "Remoto":
        if any(norm_text(x) in low for x in BLOCKED_REMOTE_TERMS):
            return -20, False, "remoto restringido fuera de Europa"
        # Explicit Europe / EMEA / global / worldwide postings are in scope.
        if any(norm_text(x) in low for x in EUROPE_TERMS):
            return 15, True, "remoto Europa/EMEA/global"
        # Country-specific remote is accepted anywhere in Europe.
        if country in EUROPE_COUNTRIES:
            return 15, True, f"remoto en {country}"
        # Explicitly detected non-European country is out of scope.
        if country:
            return -20, False, f"remoto restringido a {country}"
        # Some feeds only expose 'Remote' and omit the eligibility region. Keep strong matches,
        # but mark the uncertainty clearly instead of assuming a country.
        allowed = preliminary_score >= 72
        return (8 if allowed else -5), allowed, "remoto; elegibilidad europea no indicada"

    # Onsite/hybrid is deliberately strict: only Spain, Luxembourg or Switzerland.
    if country in onsite_allowed:
        return 15, True, f"{mode.lower()} en {country}"
    if country:
        return -20, False, f"{mode.lower()} fuera de España/Luxemburgo/Suiza"

    # Unknown non-remote location: retain only very strong matches for manual verification.
    allowed = preliminary_score >= 86
    return (2 if allowed else -8), allowed, "ubicación no clara"


def score_job(job: Job, profile: dict, known_company: bool = False) -> tuple[Job, bool]:
    if obvious_non_job_content(job.source_kind, job.title, job.apply_url):
        return job, False
    title_norm = norm_text(job.title)
    if any(x in title_norm for x in HARD_EXCLUDE_TITLE) and not any(k in title_norm for k in ["compliance", "risk", "aml", "kyc", "kyb", "fraud"]):
        return job, False

    role_pts, role_hits = role_relevance(job.title, job.description)
    if role_pts < 12:
        return job, False
    if not financial_context(job, known_company=known_company):
        return job, False

    score = role_pts
    reasons = []
    if role_hits:
        reasons.append("rol: " + ", ".join(role_hits[:3]))

    blob = norm_text(job.title + " " + job.description)
    overlap_terms = [
        "ubo", "beneficial ownership", "ownership structure", "business verification", "corporate", "merchant",
        "onboarding", "periodic review", "high risk", "edd", "pep", "sanctions", "adverse media", "audit",
        "sop", "sla", "regulated payments", "kyb", "cdd",
    ]
    overlap = sum(1 for x in overlap_terms if x in blob)
    overlap_pts = min(25, overlap * 3)
    score += overlap_pts
    if overlap:
        reasons.append(f"skills transferibles {overlap_pts}/25")

    years = extract_years_required(job.description)
    if years is None:
        exp_pts = 10
        reasons.append("años no especificados")
    elif years <= 3:
        exp_pts = 15
        reasons.append(f"experiencia requerida {years}a")
    elif years == 4:
        exp_pts = 11
        reasons.append("4 años: estiramiento razonable")
    elif years == 5:
        exp_pts = 6
        reasons.append("5 años: penalización")
    else:
        exp_pts = 1
        reasons.append(f"{years}+ años: penalización fuerte")
    score += exp_pts

    sector = infer_sector(job, known_company=known_company)
    job.sector = sector
    sector_pts = 10 if sector in {"Payments", "Banca"} else 8
    score += sector_pts

    skills = extract_growth_skills(job)
    growth_pts = min(8, len(skills) * 2)
    score += growth_pts
    if skills:
        reasons.append("compra: " + ", ".join(skills[:3]))

    lang_pts, lang_reasons = language_adjustment(job.description)
    score += lang_pts
    reasons.extend(lang_reasons)

    senior_penalty = 0
    if re.search(r"\b(head|director|vp|vice president|chief|mlro)\b", title_norm):
        senior_penalty -= 25
    elif re.search(r"\bmanager\b", title_norm):
        senior_penalty -= 14
    elif re.search(r"\blead\b", title_norm) and "analyst" not in title_norm:
        senior_penalty -= 8
    score += senior_penalty
    if senior_penalty:
        reasons.append(f"seniority {senior_penalty}")

    preliminary = max(0, min(100, score))
    loc_pts, allowed, loc_reason = location_score_and_allowed(job, preliminary, skills, profile)
    score += loc_pts
    reasons.append(loc_reason)

    age = parse_age_days(job.posted_at)
    max_age = float(profile.get("max_post_age_days", 10))
    if age is not None and age > max_age:
        return job, False
    if age is not None:
        if age <= 3:
            score += 4
        elif age <= 7:
            score += 2
        reasons.append(f"{age:.0f}d de antigüedad")
    else:
        reasons.append("fecha no publicada")

    job.score = max(0, min(100, int(round(score))))
    job.skills_to_buy = skills
    job.location_mode = detect_mode(job)
    job.country = detect_country(job.location)
    job.score_reason = " · ".join(reasons)

    min_score = int(profile.get("minimum_score", 62))
    return job, bool(allowed and job.score >= min_score)
