from __future__ import annotations

import re

from job_radar.models import Job, norm_text


GAP_ALIASES = {
    "Transaction Monitoring": ["transaction monitoring", "tm alerts", "transaction-monitoring"],
    "AML investigations": ["aml investigations", "aml investigation", "financial crime investigations", "case investigations"],
    "SAR/STR drafting": ["sar drafting", "str drafting", "suspicious activity report", "suspicious transaction report", "sar filing", "str filing"],
    "Regulatory reporting": ["regulatory reporting", "regulatory filing", "goaml"],
    "Sanctions investigations": ["sanctions investigations", "sanctions investigation"],
    "Source of Funds (SoF)": ["source of funds", "source-of-funds", "sof review", "sof assessment"],
    "Source of Wealth (SoW)": ["source of wealth", "source-of-wealth", "sow review", "sow assessment"],
}

# Signals we actively want to see in the DAY-TO-DAY of a role. Some are already current
# strengths and some are growth skills; this list is about job content, not CV claims.
DAY_TO_DAY_ALIASES = {
    "KYC/KYB": ["kyc", "kyb", "know your customer", "know your business"],
    "CDD/EDD": ["customer due diligence", "client due diligence", "enhanced due diligence", "cdd", "edd"],
    "PEP screening": ["pep screening", "politically exposed person", "politically exposed persons"],
    "Adverse media": ["adverse media", "negative news"],
    "Sanctions screening": ["sanctions screening", "sanction screening"],
    "Transaction Monitoring": GAP_ALIASES["Transaction Monitoring"],
    "AML investigations": GAP_ALIASES["AML investigations"],
    "Source of Funds (SoF)": GAP_ALIASES["Source of Funds (SoF)"],
    "Source of Wealth (SoW)": GAP_ALIASES["Source of Wealth (SoW)"],
    "SAR/STR drafting": GAP_ALIASES["SAR/STR drafting"],
    "Regulatory reporting": GAP_ALIASES["Regulatory reporting"],
}

REQUIREMENT_CUES = [
    "practical experience",
    "hands on experience",
    "hands-on experience",
    "proven experience",
    "previous experience",
    "prior experience",
    "experience in",
    "experience with",
    "experience of",
    "must have",
    "required",
    "essential",
]

KNOWLEDGE_CUES = [
    "good knowledge",
    "strong knowledge",
    "sound knowledge",
    "working knowledge",
    "deep knowledge",
    "detailed knowledge",
    "knowledge of",
    "must know",
    "required",
    "essential",
]

RESPONSIBILITY_HEADINGS = [
    "responsibilities",
    "key responsibilities",
    "your responsibilities",
    "what you will do",
    "what you ll do",
    "what you will be doing",
    "what you ll be doing",
    "what you do",
    "the role",
    "your role",
    "day to day",
    "day to day responsibilities",
    "duties",
    "key duties",
    "what you will work on",
]

REQUIREMENT_HEADINGS = [
    "requirements",
    "job requirements",
    "qualifications",
    "required qualifications",
    "what we are looking for",
    "what we re looking for",
    "what you bring",
    "about you",
    "skills and experience",
    "experience and qualifications",
    "must have",
    "essential skills",
]


def _contains_any(text: str, aliases: list[str]) -> bool:
    return any(norm_text(alias) in text for alias in aliases)


def _required_near(text: str, aliases: list[str], cues: list[str], before: int = 150, after: int = 90) -> bool:
    for alias in aliases:
        a = norm_text(alias)
        start = 0
        while True:
            idx = text.find(a, start)
            if idx < 0:
                break
            window = text[max(0, idx - before): idx + len(a) + after]
            if any(norm_text(cue) in window for cue in cues):
                return True
            start = idx + len(a)
    return False


def _section_buckets(description: str) -> tuple[str, str, bool]:
    """Split a JD approximately into responsibilities and requirements.

    ATS feeds often flatten HTML into text. Headings generally survive, so this gives us
    enough structure to tell "you will perform SoF reviews" from "SoF experience required".
    If no useful headings survive, callers fall back to conservative proximity checks.
    """
    text = norm_text(description)
    markers: list[tuple[int, str, int]] = []

    for kind, headings in (("resp", RESPONSIBILITY_HEADINGS), ("req", REQUIREMENT_HEADINGS)):
        for heading in headings:
            h = norm_text(heading)
            start = 0
            while h:
                idx = text.find(h, start)
                if idx < 0:
                    break
                markers.append((idx, kind, len(h)))
                start = idx + len(h)

    if not markers:
        return "", "", False

    # Prefer longer headings when two start at the same point (e.g. requirements/job requirements).
    markers.sort(key=lambda x: (x[0], -x[2]))
    filtered: list[tuple[int, str, int]] = []
    occupied = -1
    for marker in markers:
        if marker[0] < occupied:
            continue
        filtered.append(marker)
        occupied = marker[0] + marker[2]

    resp_parts: list[str] = []
    req_parts: list[str] = []
    for i, (pos, kind, length) in enumerate(filtered):
        end = filtered[i + 1][0] if i + 1 < len(filtered) else len(text)
        segment = text[pos + length:end].strip()
        if len(segment) < 12:
            continue
        if kind == "resp":
            resp_parts.append(segment)
        else:
            req_parts.append(segment)

    return " ".join(resp_parts), " ".join(req_parts), bool(resp_parts or req_parts)


def _gap_placement(job: Job, profile: dict) -> tuple[int, int, list[str], list[str], set[str]]:
    """Return (bonus, penalty, duty reasons, requirement reasons, req-only skill labels)."""
    full = norm_text(job.description)
    resp, req, structured = _section_buckets(job.description)
    bonus = 0
    penalty = 0
    duty_reasons: list[str] = []
    requirement_reasons: list[str] = []
    req_only: set[str] = set()

    # Reward target content specifically when it appears in the responsibilities/day-to-day section.
    if resp:
        for label, aliases in DAY_TO_DAY_ALIASES.items():
            if _contains_any(resp, aliases):
                duty_reasons.append(label)
        bonus = min(16, len(duty_reasons) * 3)

    for gap in profile.get("hands_on_gaps", []):
        label = str(gap)
        aliases = GAP_ALIASES.get(label, [label])
        in_resp = bool(resp and _contains_any(resp, aliases))
        in_req = bool(req and _contains_any(req, aliases))

        if in_req:
            # Being listed under Requirements/Qualifications is already meaningful. Explicit
            # prior/practical/hands-on experience language makes the penalty stronger.
            explicit = _required_near(req, aliases, REQUIREMENT_CUES, before=130, after=80)
            if label == "Transaction Monitoring":
                p = -12 if explicit else -9
            else:
                p = -10 if explicit else -7
            penalty += p
            requirement_reasons.append(f"{label} exigido")
            if not in_resp:
                req_only.add(label)
        elif not structured and _required_near(full, aliases, REQUIREMENT_CUES):
            # Conservative fallback for feeds where headings were stripped completely.
            p = -12 if label == "Transaction Monitoring" else -10
            penalty += p
            requirement_reasons.append(f"{label} exigido")

    # Jurisdiction-specific knowledge: only punish if it is actually a qualification/must-have.
    for gap in profile.get("jurisdiction_gaps", []):
        g = norm_text(str(gap))
        if "malt" in g or "fiau" in g or "pmlftr" in g:
            aliases = ["maltese aml", "maltese aml cft", "pmlftr", "fiau implementing procedures", "fiau"]
            in_req = bool(req and _contains_any(req, aliases))
            if in_req or (not structured and _required_near(full, aliases, KNOWLEDGE_CUES, before=160, after=80)):
                penalty -= 14
                requirement_reasons.append("conocimiento AML/CFT Malta exigido")

    return bonus, max(-35, penalty), duty_reasons, requirement_reasons, req_only


def apply_fit_adjustments(job: Job, profile: dict, originally_ok: bool) -> tuple[Job, bool]:
    bonus, penalty, duty_reasons, requirement_reasons, req_only = _gap_placement(job, profile)

    # "Skills que comprarías" should describe likely learning in the job, not a skill that
    # appears only as an entry requirement. Keep it when it also appears in responsibilities.
    if job.skills_to_buy and req_only:
        req_norm = {norm_text(x) for x in req_only}
        job.skills_to_buy = [x for x in job.skills_to_buy if norm_text(x) not in req_norm]

    if bonus:
        job.score = min(100, int(job.score) + bonus)
        labels = ", ".join(duty_reasons[:5])
        suffix = f"contenido diario objetivo: {labels} (+{bonus})"
        job.score_reason = f"{job.score_reason} · {suffix}" if job.score_reason else suffix

    if penalty:
        job.score = max(0, int(job.score) + penalty)
        detail = ", ".join(requirement_reasons)
        suffix = f"gaps obligatorios: {detail} ({penalty})"
        job.score_reason = f"{job.score_reason} · {suffix}" if job.score_reason else suffix

    # Preserve the base matcher's hard gates (location, age, domain relevance). The section
    # adjustment refines fit; it must not resurrect an otherwise out-of-scope vacancy.
    if not originally_ok:
        return job, False
    return job, job.score >= int(profile.get("minimum_score", 62))
