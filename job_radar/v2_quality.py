"""Conservative, evidence-first admission rules for v2.

Unknown != fresh; a date from an aggregator or updated_at is not the
original publication date. These rules run in addition to the existing
role/fit scoring, never in place of it.
"""
from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

from dateutil import parser as dateparser

from job_radar.matching import detect_country, detect_mode
from job_radar.models import Job, norm_text
from job_radar.experience_requirements import hard_experience_gap


def original_posted_at(value) -> datetime | None:
    """Parse an absolute posting date; reject relative/indexed/unknown dates."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        epoch = float(value)
        if epoch > 10_000_000_000:
            epoch /= 1000.0
        try:
            return datetime.fromtimestamp(epoch, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    raw = str(value).strip()
    if not raw or re.search(r"\b(today|yesterday|ago|posted|updated|hours?|days?)\b", raw, re.I):
        return None
    if raw.isdigit():
        return original_posted_at(int(raw))
    # No loose/fuzzy dateparser fallbacks ("October" alone, locale ambiguity).
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[Tt ][0-9:.+Zz-]+)?", raw):
        return None
    try:
        dt = dateparser.isoparse(raw)
    except (ValueError, TypeError, OverflowError):
        return None
    return dt.replace(tzinfo=timezone.utc) if not dt.tzinfo else dt.astimezone(timezone.utc)


def within_new_window(value, max_hours: int = 96, now: datetime | None = None) -> bool:
    dt = original_posted_at(value)
    if dt is None:
        return False
    now = now or datetime.now(timezone.utc)
    age = (now - dt).total_seconds()
    return 0 <= age <= max_hours * 3600


def location_allowed(job: Job) -> bool:
    """Require explicit Spain eligibility for remote; narrow relocation shortlist."""
    mode = detect_mode(job)
    loc = norm_text(job.location or "")
    hint = norm_text(job.remote_hint or "")
    if mode == "Remoto":
        if "hybrid" in loc or "hibrid" in loc or "hybrid" in hint:
            return False
        # Spain-wide can still exclude the Canary Islands in employment terms.
        eligibility_text = norm_text(" ".join((job.location or "", job.remote_hint or "",
                                                 job.description or "")))
        excluded_islands = (
            r"(?:excluding|except|not available in|cannot be based in|"
            r"not permitted in|outside) (?:the )?(?:canary islands|canarias)"
        )
        if re.search(excluded_islands, eligibility_text) or any(
            x in eligibility_text for x in (
                "mainland spain only", "peninsular spain only",
                "spain mainland only", "solo peninsula",
            )
        ):
            return False
        # Europe, EMEA, Global and Worldwide alone do NOT establish ability
        # to reside and be paid from the Canary Islands.
        return bool(re.search(r"\b(spain|espana|canary islands|canarias)\b", loc + " " + hint))

    if "barcelona" in loc:
        return False
    return detect_country(job.location) in {
        "Spain", "Estonia", "Lithuania", "Luxembourg", "Switzerland",
    }


def could_verify_spain_from_job_page(job: Job) -> bool:
    """A generic Europe/EMEA remote ATS listing may specify Spain in JobPosting.

    These are only *pre-check* candidates, never alerts. Location must be
    upgraded by matching structured source evidence on the job detail page.
    """
    if detect_mode(job) != "Remoto":
        return False
    scope = norm_text((job.location or "") + " " + (job.remote_hint or ""))
    return any(x in scope for x in (
        "europe", "emea", "worldwide", "global", "european union", "eu remote",
    ))


def jobposting_spain_remote_verified(soup, expected_title: str) -> bool:
    """Require explicit Spain / ES applicantLocationRequirements for this job."""
    expected = norm_text(expected_title)
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            payload = json.loads(script.string or script.get_text() or "")
        except (ValueError, TypeError):
            continue
        queue = [payload]
        while queue:
            obj = queue.pop()
            if isinstance(obj, list):
                queue.extend(obj)
                continue
            if not isinstance(obj, dict):
                continue
            types = obj.get("@type") or []
            types = types if isinstance(types, list) else [types]
            if "JobPosting" in types and norm_text(str(obj.get("title") or "")) == expected:
                requirements = obj.get("applicantLocationRequirements") or []
                requirements = requirements if isinstance(requirements, list) else [requirements]
                for requirement in requirements:
                    if not isinstance(requirement, dict):
                        continue
                    identifiers = [
                        str(requirement.get("name") or ""),
                        str(requirement.get("identifier") or ""),
                    ]
                    address = requirement.get("address") or {}
                    if isinstance(address, dict):
                        identifiers.append(str(address.get("addressCountry") or ""))
                    if any(norm_text(x) in {"es", "spain", "espana"} for x in identifiers):
                        return True
            queue.extend(value for key, value in obj.items()
                         if key in {"@graph", "mainEntity", "itemListElement"})
    return False


def official_active_listing(job: Job) -> bool:
    """Admit verifiable employer postings, not aggregators or general careers indexes.

    A specific job linked from the employer's own careers page is legitimate
    first-party evidence even when the firm doesn't use a supported ATS.
    Its original date and visible application action are separately verified.
    """
    if job.source_kind not in {"official ATS", "official career page"}:
        return False
    url = urlsplit(job.apply_url or "")
    if url.scheme != "https" or not url.netloc:
        return False
    path = (url.path or "").rstrip("/")
    from urllib.parse import parse_qsl
    from job_radar.models import JOB_SELECTOR_PARAMS
    has_job_selector = any(
        key.casefold() in JOB_SELECTOR_PARAMS and value
        for key, value in parse_qsl(url.query)
    )
    if not path and not has_job_selector:
        return False
    if path in {"/careers", "/jobs", "/join-us"} and not has_job_selector:
        return False
    return True



# A hard stop only for *explicit* language requirements, never for nationality,
# the location of clients, or a language merely described as advantageous.
# A conservative matcher is preferable to discarding valid roles silently.
LANGUAGES = (
    "lithuanian", "estonian", "latvian", "german", "italian", "dutch",
    "polish", "portuguese", "finnish", "swedish", "danish", "norwegian",
    "czech", "slovak", "hungarian", "romanian", "greek", "turkish",
    "arabic", "russian", "ukrainian", "french", "spanish", "english",
)
_LANGUAGE_PATTERN = re.compile(r"\b(?:" + "|".join(LANGUAGES) + r")\b", re.I)
_MANDATORY_CUE = re.compile(r"\b(required|mandatory|essential|must|necessar(?:y|ily)|obligator(?:y|io|ia)|exig(?:e|ido|ida)|erforderlich|erforderliche)\b", re.I)
_OPTIONAL_CUE = re.compile(
    r"\b(preferred|advantage|advantageous|plus|nice to have|optional|"
    r"desirable|not required|not mandatory|nicht erforderlich|wunschenswert)\b", re.I
)
_LANGUAGE_SKILL_CUE = re.compile(
    r"\b(fluent|fluency|fluently|native|proficien(?:t|cy)|bilingual|"
    r"speak|speaking|spoken|written|communication|language|linguistic|"
    r"kenntnisse|sprachkenntnisse|sprache|idioma|nivel|niveau|level|"
    r"command of|knowledge of|kenntnis|verbal)\b", re.I
)
_LANGUAGE_DIRECT_REQUIREMENT = re.compile(
    r"\b(?:" + "|".join(LANGUAGES) +
    r")(?:\s+(?:[abc][12]\s*(?:level|niveau)?|language|skills|kenntnisse))?"
    r"\s+(?:is|are|(?:would be))?\s*(?:required|mandatory|essential|"
    r"erforderlich|exigido|obligatorio)\b", re.I
)


def _unmet_language_groups(clause: str, present: set[str], known: set[str]) -> set[str]:
    """An 'or' only makes its own language alternatives optional.

    'English AND (Latvian, Lithuanian OR Estonian)' is NOT satisfied by
    English. Use the nearest conjunction boundaries around each OR group.
    """
    missing = present - known
    for conjunction in re.finditer(r"\b(?:or|either|ou|oder|o)\b", clause):
        prior_and = clause.rfind(" and ", 0, conjunction.start())
        first = prior_and + 5 if prior_and >= 0 else 0
        following_and = re.search(r"\band\b", clause[conjunction.end():])
        last = (conjunction.end() + following_and.start()
                if following_and else len(clause))
        group = set(_LANGUAGE_PATTERN.findall(clause[first:last]))
        if len(group) >= 2 and group & known:
            missing.difference_update(group)
    return missing


def _required_section_language_gaps(description: str, known: set[str]) -> set[str]:
    """The Qualifications/What We Expect bullet list conveys mandatory status.

    Do not require the literal word 'required' inside every separate bullet:
    e.g. 'Excellent Latvian, Lithuanian or Estonian language skills' under
    'What We Expect' is an explicit must-have, not a geographic reference.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(description or "", "html.parser")
    in_requirements = False
    missing: set[str] = set()
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "li"]):
        if node.name != "li":
            header = norm_text(node.get_text(" ", strip=True))
            in_requirements = bool(re.search(
                r"\b(?:what we expect|what you bring|your profile|"
                r"requirements|qualifications|essential skills|"
                r"must have|who you are|required skills)\b", header
            )) and not bool(re.search(r"\b(?:preferred|optional|nice to have)\b", header))
            continue
        if not in_requirements:
            continue
        clause = norm_text(node.get_text(" ", strip=True))
        if _OPTIONAL_CUE.search(clause) or re.search(r"\bnot\s+(?:a\s+)?requirement\b", clause):
            continue
        present = set(_LANGUAGE_PATTERN.findall(clause))
        if not present or not (_LANGUAGE_SKILL_CUE.search(clause)
                               or _LANGUAGE_DIRECT_REQUIREMENT.search(clause)):
            continue
        if re.search(r"\b(?:no|not)\s+(?:language\s+)?(?:is\s+)?required\b", clause):
            continue
        missing.update(_unmet_language_groups(clause, present, known))
    return missing


def _title_mandatory_languages(title: str, known: set[str]) -> set[str]:
    """'Italian-speaking AML Specialist' names a required language.

    Some Workday requisitions make their language mandatory in the title
    but not in a machine-labelled Requirements section. Treat explicit
    'speaking/speaker/fluent/language' title signals as role requirements.
    Alternative 'German OR Spanish' title groups remain satisfiable by
    Spanish (also French OR German by French). Mere geography isn't a
    mandatory language requirement.
    """
    value = norm_text(title)
    mentions = set(_LANGUAGE_PATTERN.findall(value))
    if not mentions:
        return set()
    if not re.search(
        r"\b(?:speaking|speaker|fluency|fluent|bilingual|language|"
        r"native|mother tongue)\b", value
    ):
        return set()
    return _unmet_language_groups(value, mentions, known)


def unmet_mandatory_languages(job: Job, known_languages) -> list[str]:
    """Languages unequivocally required but absent from the configured CV.

    A 'German OR French' requirement is satisfied by French; 'Lithuanian
    AND English' requires both. Unknown/optional wording stays in review
    rather than becoming an automatic rejection. No language is inferred
    from residence or citizenship.
    """
    if known_languages is None:
        return []
    known = {norm_text(str(x)) for x in known_languages}
    if not known:
        return []
    from bs4 import BeautifulSoup
    desc = BeautifulSoup(job.description or "", "html.parser").get_text(" ; ", strip=True)
    verified_text = getattr(job, "_verified_page_text", "")
    clauses = re.split(r"[.;\n,]+", desc + " ; " + verified_text)
    missing = set()
    for clause in clauses:
        clause = norm_text(clause)
        if not _MANDATORY_CUE.search(clause) or _OPTIONAL_CUE.search(clause):
            continue
        present = set(_LANGUAGE_PATTERN.findall(clause))
        if not present:
            continue
        if not (_LANGUAGE_SKILL_CUE.search(clause)
                or _LANGUAGE_DIRECT_REQUIREMENT.search(clause)):
            continue
        if re.search(r"\b(?:no|not)\s+(?:language\s+)?(?:is\s+)?required\b", clause):
            continue
        # Alternative languages: one proven language satisfies this clause.
        missing.update(_unmet_language_groups(clause, present, known))
    missing.update(_required_section_language_gaps(job.description or "", known))
    missing.update(_title_mandatory_languages(job.title or "", known))
    return sorted(missing)


def passes_strict_gate(job: Job, max_hours: int = 96, now: datetime | None = None,
                       known_languages=None) -> bool:
    return (
        official_active_listing(job)
        and within_new_window(job.posted_at, max_hours=max_hours, now=now)
        and location_allowed(job)
        and not unmet_mandatory_languages(job, known_languages)
        and not hard_experience_gap(job.description)
    )


def previously_presented(job: Job, seen: dict) -> bool:
    """Avoid re-alerting same role after job URL, title suffix, or location shifts.

    Explicit *different* ATS IDs permit separate requisitions. Legacy seen
    entries often have no ID; with insufficient evidence prefer no repeat.
    """
    company = norm_text(job.company)
    title = norm_text(job.title)
    jid = str(job.external_id or "").strip()
    for rec in seen.values():
        if not isinstance(rec, dict):
            continue
        if norm_text(rec.get("company")) != company:
            continue
        prior_id = str(rec.get("external_id") or "").strip()
        if jid and prior_id and jid == prior_id:
            return True
        if norm_text(rec.get("title")) == title:
            prior_vendor = norm_text(str(rec.get("source") or "").split(":", 1)[0])
            new_vendor = norm_text(str(job.source or "").split(":", 1)[0])
            distinct_requisitions_same_ats = (
                bool(jid and prior_id and jid != prior_id)
                and prior_vendor == new_vendor
                and prior_vendor in {
                    "greenhouse", "lever", "ashby", "workable", "personio",
                    "smartrecruiters", "recruitee", "workday", "breezy",
                }
            )
            if distinct_requisitions_same_ats:
                continue
            # Different IDs on *different* platforms do not establish that
            # this is a different role: a career-page URL and ATS ID often
            # refer to the same requisition.
            return True
    return False


def extract_original_jobposting_date(soup, expected_title: str) -> str:
    """Only schema.org JobPosting.datePosted for THIS exact role is trusted."""
    title_expected = norm_text(expected_title)
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            document = json.loads(script.string or script.get_text() or "")
        except (ValueError, TypeError):
            continue
        queue = [document]
        while queue:
            item = queue.pop()
            if isinstance(item, list):
                queue.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            types = item.get("@type", [])
            types = types if isinstance(types, list) else [types]
            if "JobPosting" in types:
                actual_title = norm_text(str(item.get("title") or ""))
                if actual_title and actual_title == title_expected:
                    date = item.get("datePosted") or ""
                    if original_posted_at(date) is not None:
                        return str(date)
            queue.extend(v for k, v in item.items() if k in {"@graph", "mainEntity", "itemListElement"})
    return ""




def has_job_application_form(soup) -> bool:
    """Do not confuse cookies, login or newsletter forms with job applications.

    A real candidate form has a submit control plus applicant-specific fields.
    An email-only newsletter/contact form, or password-based login, is not
    evidence that an application can be submitted for this requisition.
    """
    for form in soup.find_all("form"):
        inputs = form.find_all("input")
        controls = form.find_all(["input", "textarea"])
        if any(str(field.get("type", "")).casefold() == "password" for field in inputs):
            continue
        has_submit = any(
            (field.name == "button" and str(field.get("type", "submit")).casefold() == "submit")
            or (field.name == "input" and str(field.get("type", "")).casefold() == "submit")
            for field in form.find_all(["button", "input"])
        )
        if not has_submit:
            continue
        field_names = norm_text(" ".join(
            " ".join(str(field.get(key) or "") for key in ("name", "id", "aria-label", "placeholder"))
            for field in controls
        ))
        has_resume = (
            any(str(field.get("type", "")).casefold() == "file" for field in inputs)
            or bool(re.search(r"\b(?:resume|curriculum vitae|cv|cover letter)\b", field_names))
        )
        has_email = (
            any(str(field.get("type", "")).casefold() == "email" for field in inputs)
            or bool(re.search(r"\b(?:e mail|email)\b", field_names))
        )
        has_person_name = bool(re.search(
            r"\b(?:first name|last name|full name|firstname|lastname|fullname)\b",
            field_names,
        ))
        action_path = urlsplit(str(form.get("action") or "")).path.casefold()
        has_application_action = bool(re.search(
            r"/(?:apply|application|candidate)(?:/|$)", action_path
        ))
        if has_resume or (has_email and has_person_name and has_application_action):
            return True
    return False


async def verify_application_page(http, job: Job, max_hours: int = 96) -> bool:
    """Check the exact ATS application page; attach a diagnostic reason.

    Conservative: failed HTML verification is NOT evidence the position is
    closed. We record a reason instead of hiding that uncertainty.
    """
    job.verification_reason = "not_checked"
    if not official_active_listing(job):
        job.verification_reason = "non_official_or_generic_url"
        return False
    try:
        response = await http.get(job.apply_url)
        if not 200 <= response.status_code < 300:
            job.verification_reason = f"http_{response.status_code}"
            return False
        page = response.text[:350_000]
    except Exception as exc:
        job.verification_reason = f"request_error_{type(exc).__name__}"
        return False
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page, "html.parser")
    # Genuine Remote Europe jobs sometimes specify Spain in JobPosting but
    # not in their ATS-list location field. Accept only structured evidence.
    if not location_allowed(job) and could_verify_spain_from_job_page(job):
        if jobposting_spain_remote_verified(soup, job.title):
            job.location = "Spain - Remote / " + (job.location or "Europe")
            job.fingerprint = ""
            job.finalize()
    exact_date = extract_original_jobposting_date(soup, job.title)
    ats_date = original_posted_at(job.posted_at)
    page_date = original_posted_at(exact_date)
    if page_date is not None and (ats_date is None or page_date < ats_date):
        job.posted_at = exact_date
    if not within_new_window(job.posted_at, max_hours=max_hours):
        job.verification_reason = "original_publication_missing_or_older_than_96h"
        return False
    visible_text = soup.get_text(" ", strip=True).casefold()
    # Transient, job-specific page evidence; not a persistent Job/state field.
    job._verified_page_text = visible_text[:35_000]
    closed = (
        "no longer accepting applications", "applications are closed",
        "this job is no longer available", "this position has been filled",
        "this posting has expired", "job is closed",
    )
    if any(phrase in visible_text for phrase in closed):
        job.verification_reason = "explicitly_closed"
        return False
    ctas = ("apply for this job", "apply for this position", "apply now",
            "submit application", "apply for this role",
            "apply to this job", "start your application")
    has_form = has_job_application_form(soup)
    has_cta = any(p in visible_text for p in ctas)
    if not has_cta:
        for a in soup.find_all(["a", "button"]):
            label = a.get_text(" ", strip=True).casefold()
            if label in {"apply", "apply now", "apply here", "apply for this job"}:
                has_cta = True
                break
    if not (has_form or has_cta):
        # Some ATS application forms are hydrated only after JavaScript runs.
        # The provider's *job-specific* published application record can prove
        # they are still available, but a generic board HTTP 200 cannot.
        from job_radar.native_apply import native_application_evidence
        try:
            if await native_application_evidence(http, job):
                job.verification_reason = "native_ats_application_confirmed"
                return True
        except Exception:
            # Network errors or unexpected provider schemas are inconclusive,
            # not evidence of either an open or closed application.
            pass
        job.verification_reason = "page_200_but_no_visible_apply_action"
        return False
    job.verification_reason = "official_live_page_with_apply_action"
    return True
