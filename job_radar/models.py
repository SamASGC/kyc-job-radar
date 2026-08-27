from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def norm_text(value: str | None) -> str:
    value = value or ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.lower()
    value = re.sub(r"[^a-z0-9+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def canonical_url(url: str) -> str:
    try:
        p = urlsplit(url)
        # Drop tracking query/fragment for dedupe, preserve path.
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))
    except Exception:
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

    def finalize(self) -> "Job":
        if not self.discovered_at:
            self.discovered_at = utcnow_iso()
        if not self.fingerprint:
            # Cross-source dedupe intentionally prefers merging identical role/company/location.
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
