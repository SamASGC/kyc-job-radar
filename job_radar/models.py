from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm_text(value: str | None) -> str:
    value = value or ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.lower()
    value = re.sub(r"[^a-z0-9+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


# Keep job selectors: some companies host all vacancies at /careers?gh_jid=...
# Removing those parameters turns a working Apply link into a generic page.
JOB_SELECTOR_PARAMS = frozenset({
    "gh_jid", "job", "jobid", "job_id", "job-id", "jid", "id",
    "requisition", "requisitionid", "requisition_id", "reqid", "req_id",
    "position", "positionid", "position_id", "postingid", "posting_id",
    "opening", "openingid", "roleid", "ashby_jid", "oid", "rid",
})


def canonical_url(url: str) -> str:
    try:
        p = urlsplit(url)
        # Drop ad/campaign tracking, NOT requisition selectors needed to apply.
        selectors = [
            (key, value) for key, value in parse_qsl(p.query, keep_blank_values=True)
            if key.casefold() in JOB_SELECTOR_PARAMS and value
        ]
        return urlunsplit((
            p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"),
            urlencode(sorted(selectors)), ""
        ))
    except (ValueError, TypeError):
        return url


@dataclass
class Job:
    source: str
    source_kind: str
    company: str
    sector: str
    title: str
    location: str
    description: str
    apply_url: str
    external_id: str = ""
    posted_at: str = ""
    salary_text: str = ""
    remote_hint: str = ""
    employment_type: str = ""
    discovered_at: str = ""
    score: int = 0
    score_reason: str = ""
    skills_to_buy: list[str] | None = None
    location_mode: str = "Unknown"
    country: str = ""
    salary_display: str = ""
    fingerprint: str = ""
    apply_verified_at: str = ""

    def finalize(self) -> "Job":
        if not self.discovered_at:
            self.discovered_at = utcnow_iso()
        if not self.fingerprint:
            # Cross-source dedupe intentionally prefers merging identical role/company/location.
            # Separate genuine ATS requisitions with distinct stable IDs,
            # while preserving legacy role-level identity when an ID is absent.
            # Cross-source never-repeat checks still compare company/title.
            if self.source_kind == "official ATS" and self.external_id:
                ats_family = norm_text((self.source or "").split(":")[0])
                basis = "|".join([
                    norm_text(self.company), "official-ats", ats_family,
                    norm_text(str(self.external_id)),
                ])
            else:
                basis = "|".join([
                    norm_text(self.company),
                    norm_text(self.title),
                    norm_text(self.location),
                ])
            self.fingerprint = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
        self.apply_url = canonical_url(self.apply_url)
        if self.skills_to_buy is None:
            self.skills_to_buy = []
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        return cls(**data)
