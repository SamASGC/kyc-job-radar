from __future__ import annotations

import re

from job_radar.models import Job, norm_text


# The matcher works on normalized text (letters/numbers/spaces only).  Padding with
# spaces gives us cheap, reliable token/phrase boundaries: "aml" must be AML, not the
# letters inside "seamless"; "edd" must be EDD, not the tail of "embedded".
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


# Clear non-target professions.  JD-first discovery is intentionally broad, so a
# payments company can expose lots of technical/commercial jobs whose descriptions
# mention transactions, risk, compliance controls, etc.  Those are not the user's goal.
HARD_NON_TARGET_TITLE_TERMS = {
    "engineer",
    "developer",
    "architect",
    "data scientist",
    "data engineer",
    "software engineer",
    "site reliability",
    "devops",
    "product designer",
    "account executive",
    "sales manager",
    "business development",
    "marketing",
    "recruiter",
    "talent acquisition",
    "customer success manager",
}


def irrelevant_profession_title(title: str) -> bool:
    return contains_any(title, HARD_NON_TARGET_TITLE_TERMS)


def safe_role_relevance(title: str, description: str, role_terms: dict[str, int]) -> tuple[int, list[str]]:
    hits: list[str] = []
    best = 0
    for term, pts in role_terms.items():
        if contains_term(title, term):
            hits.append(term)
            best = max(best, pts)

    desc_hits = [term for term in role_terms if contains_term(description, term)]
    if best == 0:
        if len(desc_hits) >= 2:
            best = min(20, 8 + len(desc_hits) * 2)
            hits.extend(desc_hits[:5])
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
