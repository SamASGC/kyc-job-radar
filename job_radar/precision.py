from __future__ import annotations

import re

from job_radar.models import Job, norm_text


# The matcher works on normalized text (letters/numbers/spaces only). Padding with
# spaces gives reliable token/phrase boundaries: "aml" must be AML, not the letters
# inside "seamless"; "edd" must be EDD, not the tail of "embedded".
def contains_term(text: str, term: str) -> bool:
    haystack = f" {norm_text(text)} "
    needle = norm_text(term)
    return bool(needle and f" {needle} " in haystack)


def contains_any(text: str, terms: list[str] | tuple[str, ...] | set[str]) -> bool:
    return any(contains_term(text, term) for term in terms)


def required_near(text: str, aliases: list[str], cues: list[str], before: int = 150, after: int = 90) -> bool:
    normalized = norm_text(text)
    for alias in aliases:
        a = norm_text(alias)
        if not a:
            continue
        pattern = re.compile(rf"(?:^| ){re.escape(a)}(?: |$)")
        for match in pattern.finditer(normalized):
            window = normalized[max(0, match.start() - before): min(len(normalized), match.end() + after)]
            if contains_any(window, cues):
                return True
    return False


# Clear non-target professions. JD-first discovery is intentionally broad, so a
# payments company can expose technical/commercial jobs whose descriptions mention
# transactions, risk, controls, etc. Those are not the user's target career family.
HARD_NON_TARGET_TITLE_TERMS = {
    "engineer",
    "engineering",
    "developer",
    "architect",
    "data scientist",
    "data engineer",
    "software engineer",
    "site reliability",
    "devops",
    "technical support",
    "production support",
    "it support",
    "customer support",
    "product designer",
    "account executive",
    "sales manager",
    "business development",
    "marketing",
    "recruiter",
    "talent acquisition",
    "customer success manager",
}

# For a generic title to be admitted on JD content alone, require at least two genuinely
# financial-crime/KYC signals. Broad words such as "onboarding", "screening" or
# "investigations" are useful corroboration but are too generic to open the gate alone.
STRONG_JD_TERMS = {
    "kyc",
    "kyb",
    "aml",
    "anti money laundering",
    "financial crime",
    "fincrime",
    "customer due diligence",
    "client due diligence",
    "cdd",
    "enhanced due diligence",
    "edd",
    "beneficial ownership",
    "source of funds",
    "source of wealth",
    "pep",
    "sanctions",
    "transaction monitoring",
    "customer verification",
    "business verification",
}


def irrelevant_profession_title(title: str) -> bool:
    return contains_any(title, HARD_NON_TARGET_TITLE_TERMS)



# Technical regulatory-compliance roles can be genuine IC careers without the
# acronyms AML/KYC in the TITLE. Permit discovery only when both the regulated-
# financial context and hands-on compliance duties are explicit in the JD.
REGULATORY_IC_TITLES = (
    "regulatory compliance analyst", "regulatory compliance specialist",
    "regulatory compliance officer", "compliance analyst", "compliance specialist",
    "compliance officer", "compliance monitoring analyst",
    "compliance monitoring specialist", "compliance assurance analyst",
    "compliance control analyst", "compliance testing analyst",
    "regulatory affairs analyst", "regulatory reporting analyst",
)
REGULATED_DOMAIN_SIGNALS = (
    "financial services", "banking", "bank", "payments", "payment services",
    "e money", "electronic money", "fintech", "regulated financial",
    "financial regulation", "mifid", "psd2", "psd3", "eba",
    "cssf", "finma", "fca", "european banking", "investment services",
)
REGULATORY_HANDS_ON_SIGNALS = (
    "compliance monitoring", "compliance testing", "control testing",
    "compliance assurance", "compliance risk assessment",
    "regulatory reporting", "regulatory obligations", "regulatory change",
    "regulatory requirements", "regulatory examinations",
    "compliance controls", "risk assessment", "risk assessments",
    "monitoring plan", "control framework", "remediation actions",
    "regulatory policies", "regulatory framework", "internal controls",
    "compliance reviews", "conduct risk",
)


def qualifies_regulatory_ic(title: str, description: str) -> bool:
    if not contains_any(title, REGULATORY_IC_TITLES):
        return False
    if not contains_any(description, REGULATED_DOMAIN_SIGNALS):
        return False
    return sum(contains_term(description, p) for p in REGULATORY_HANDS_ON_SIGNALS) >= 2


def safe_role_relevance(title: str, description: str, role_terms: dict[str, int]) -> tuple[int, list[str]]:
    hits: list[str] = []
    best = 0
    for term, pts in role_terms.items():
        if contains_term(title, term):
            hits.append(term)
            best = max(best, pts)

    desc_hits = [term for term in role_terms if contains_term(description, term)]
    if best == 0:
        strong_hits = {term for term in STRONG_JD_TERMS if contains_term(description, term)}
        if len(strong_hits) >= 2:
            best = min(20, 8 + len(desc_hits) * 2)
            hits.extend(desc_hits[:5])
        elif qualifies_regulatory_ic(title, description):
            # Admissible ROLE family, not automatic eligibility. Existing
            # min-score, experience, language, freshness and apply gates stay.
            best = 22
            hits.append("technical regulatory compliance")
    elif desc_hits:
        best = min(30, best + min(8, len(set(desc_hits))))
        for term in desc_hits:
            if term not in hits:
                hits.append(term)
    return best, hits


def safe_extract_growth_skills(job: Job, growth_skills: list[tuple[str, list[str]]], current_skills: set[str]) -> list[str]:
    blob = f"{job.title} {job.description}"
    out: list[str] = []
    normalized_current = {norm_text(x) for x in current_skills}
    for label, aliases in growth_skills:
        if contains_any(blob, aliases) and norm_text(label) not in normalized_current:
            out.append(label)
    return out[:5]


def safe_financial_context(job: Job, known_company: bool, finance_terms: list[str]) -> bool:
    if known_company:
        return True
    blob = " ".join([job.company, job.title, job.description])
    return contains_any(blob, finance_terms)


def safe_infer_sector(job: Job, known_company: bool = False) -> str:
    if known_company and job.sector in {"Fintech", "Banca", "Payments"}:
        return job.sector
    blob = " ".join([job.company, job.title, job.description])
    if contains_any(blob, ["payment", "payments", "acquiring", "merchant", "remittance", "money transfer", "card issuing", "open banking", "fx", "foreign exchange"]):
        return "Payments"
    if contains_any(blob, ["bank", "banking", "neobank", "lending", "savings", "wealth bank"]):
        return "Banca"
    return "Fintech"
