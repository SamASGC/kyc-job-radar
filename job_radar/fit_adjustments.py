from __future__ import annotations

import re

from job_radar.models import Job, norm_text


GAP_ALIASES = {
    "Transaction Monitoring": ["transaction monitoring", "tm alerts", "transaction-monitoring"],
    "AML investigations": ["aml investigations", "aml investigation", "financial crime investigations", "case investigations"],
    "SAR/STR drafting": ["sar", "str", "suspicious activity report", "suspicious transaction report"],
    "Regulatory reporting": ["regulatory reporting", "regulatory filing", "goaml"],
    "Sanctions investigations": ["sanctions investigations", "sanctions investigation"],
    "Source of Funds (SoF)": ["source of funds", "source-of-funds", "sof review", "sof assessment"],
    "Source of Wealth (SoW)": ["source of wealth", "source-of-wealth", "sow review", "sow assessment"],
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
    "requirement",
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
]


def _required_near(text: str, aliases: list[str], cues: list[str], before: int = 180, after: int = 90) -> bool:
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


def hard_gap_penalty(job: Job, profile: dict) -> tuple[int, list[str]]:
    """Penalise genuine must-have gaps, not skills merely mentioned in responsibilities.

    This keeps 'skills to buy' useful while preventing a role from scoring highly when
    it explicitly requires hands-on experience the profile does not currently have.
    """
    text = norm_text(job.description)
    penalty = 0
    reasons: list[str] = []

    for gap in profile.get("hands_on_gaps", []):
        aliases = GAP_ALIASES.get(str(gap), [str(gap)])
        if _required_near(text, aliases, REQUIREMENT_CUES):
            p = -12 if str(gap) == "Transaction Monitoring" else -10
            penalty += p
            reasons.append(f"{gap} exigido")

    # Jurisdiction-specific knowledge is a separate gap from transferable AML/KYC skills.
    for gap in profile.get("jurisdiction_gaps", []):
        g = norm_text(str(gap))
        if "malt" in g or "fiau" in g or "pmlftr" in g:
            aliases = ["maltese aml", "maltese aml/cft", "pmlftr", "fiau implementing procedures", "fiau"]
            if _required_near(text, aliases, KNOWLEDGE_CUES, before=160, after=80):
                penalty -= 14
                reasons.append("conocimiento AML/CFT Malta exigido")

    # Avoid double-punishing a role into irrelevance because several missing skills are
    # listed in the same requirement bullet. A hard cap still makes the gap material.
    penalty = max(-35, penalty)
    return penalty, reasons


def apply_fit_adjustments(job: Job, profile: dict, originally_ok: bool) -> tuple[Job, bool]:
    penalty, reasons = hard_gap_penalty(job, profile)
    if penalty:
        job.score = max(0, int(job.score) + penalty)
        detail = ", ".join(reasons)
        suffix = f"gaps obligatorios: {detail} ({penalty})"
        job.score_reason = f"{job.score_reason} · {suffix}" if job.score_reason else suffix

    if not originally_ok:
        return job, False
    return job, job.score >= int(profile.get("minimum_score", 62))
