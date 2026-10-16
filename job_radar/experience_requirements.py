"""Extract *required* experience, not employee-benefit tenure or preferred extras.

An ATS description can say both "5-7 years of compliance experience" and
"more vacation after 1 year at the firm".  The latter is not a qualification.
The lower bound of a required range is used, and separate genuine mandatory
requirements use their strictest lower bound.
"""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
from job_radar.models import norm_text

_YEAR = re.compile(r"(?<!\d)(\d{1,2})(?:\s*(?:-|–|—|to)\s*\d{1,2})?\s*\+?\s*(?:years?|yrs?|anos|años)\b", re.I)
_OPTIONAL = re.compile(r"\b(?:preferred|desirable|nice to have|advantage|bonus|ideally|would be a plus|not required|optional)\b", re.I)
_EXPERIENCE = re.compile(r"\b(?:experience|experiencia|track record|professional background|years in|years of|years working)\b", re.I)
_DOMAIN = re.compile(r"\b(?:kyc|kyb|aml|financial crime|compliance|assurance|audit|banking|payments?|financial services|due diligence|regulatory|fraud|sanctions|risk management|regulated)\b", re.I)


def required_experience_years(description: str) -> int | None:
    soup = BeautifulSoup(description or "", "html.parser")
    # Preserve vacancy bullet/paragraph boundaries. Mixing unrelated sections
    # allows a 1-year employee benefit to override 5-7 years required.
    blocks = soup.find_all(["li", "p"])
    if blocks:
        clauses = [
            node.get_text(" ", strip=True)
            for node in blocks
            if not (node.name == "p" and node.find_parent("li"))
        ]
    else:
        clauses = re.split(r"[;\n]+|(?<=[.!?])\s+", soup.get_text(" ", strip=True))
    required = []
    for clause in clauses:
        if _OPTIONAL.search(clause):
            continue
        for match in _YEAR.finditer(clause):
            minimum = int(match.group(1))
            if not 1 <= minimum <= 20:
                continue
            before = clause[max(0, match.start() - 105):match.start()]
            after = clause[match.end():match.end() + 105]
            context = before + " " + after
            # Mandatory role experience, not "after being with the company
            # for one year" or "we have 10 years of company history".
            if _EXPERIENCE.search(context) or (
                _DOMAIN.search(after) and
                re.search(r"\b(?:at least|minimum|requires?|must have|expected)\b", before, re.I)
            ):
                required.append(minimum)
    return max(required) if required else None


def hard_experience_gap(description: str, max_required_years: int = 4) -> bool:
    years = required_experience_years(description)
    return years is not None and years > max_required_years
