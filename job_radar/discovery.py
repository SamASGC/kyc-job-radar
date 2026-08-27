from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup

ATS_PATTERNS = [
    ("greenhouse", re.compile(r"https?://(?:job-boards(?:\.eu)?\.greenhouse\.io|boards\.greenhouse\.io)/([A-Za-z0-9_-]+)", re.I)),
    ("lever_eu", re.compile(r"https?://jobs\.eu\.lever\.co/([A-Za-z0-9_-]+)", re.I)),
    ("lever", re.compile(r"https?://jobs\.lever\.co/([A-Za-z0-9_-]+)", re.I)),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/([A-Za-z0-9_-]+)", re.I)),
    ("smartrecruiters", re.compile(r"https?://careers\.smartrecruiters\.com/([A-Za-z0-9_-]+)", re.I)),
    ("workable", re.compile(r"https?://apply\.workable\.com/([A-Za-z0-9_-]+)", re.I)),
    ("recruitee", re.compile(r"https?://([A-Za-z0-9_-]+)\.recruitee\.com", re.I)),
    ("breezy", re.compile(r"https?://([A-Za-z0-9_-]+)\.breezy\.hr", re.I)),
    ("personio", re.compile(r"https?://([A-Za-z0-9_-]+)\.jobs\.personio\.(?:com|de)", re.I)),
]

WORKDAY_RE = re.compile(r"https?://[^\s\"'<>]+\.myworkdayjobs\.com/[^\s\"'<>]+", re.I)


def detect_ats(html: str, final_url: str = "") -> list[dict]:
    hay = final_url + "\n" + html
    out = []
    seen = set()
    for kind, rx in ATS_PATTERNS:
        for m in rx.finditer(hay):
            slug = m.group(1)
            key = (kind, slug.lower())
            if key not in seen:
                seen.add(key)
                out.append({"kind": kind, "slug": slug})
    for m in WORKDAY_RE.finditer(hay):
        url = m.group(0).replace("&amp;", "&")
        key = ("workday", url)
        if key not in seen:
            seen.add(key)
            out.append({"kind": "workday", "url": url})
    return out


def generic_job_links(html: str, base_url: str, max_links: int = 120) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen = set()
    strong = re.compile(r"\b(kyc|kyb|aml|fincrime|financial crime|compliance|sanction|fraud|risk|onboarding|due diligence|cdd|edd|screening|investigat|transaction monitoring)\b", re.I)
    jobish = re.compile(r"(job|career|position|opening|vacanc|apply)", re.I)
    non_job_path = re.compile(r"/(?:learn|blog|resources?|glossary|academy|guides?|whitepapers?|webinars?|podcasts?|events?|customers?|case-stud(?:y|ies)|docs?|documentation|regulations?)(?:/|$)", re.I)
    non_job_title = re.compile(r"\b(?:glossary|whitepaper|webinar|podcast|case study|regulations? directory|resource library|knowledge base|blog post|research report|guide to|handbook)\b", re.I)
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a.get("href", ""))
        text = " ".join(a.stripped_strings).strip()
        if not text:
            text = a.get("aria-label", "") or a.get("title", "") or ""
        if not href.startswith("http"):
            continue
        p = urlsplit(href)
        # Career pages often contain navigation/resources using AML/KYC words.
        # Do not mistake those content pages for vacancies.
        if non_job_path.search(p.path) or non_job_title.search(text):
            continue
        blob = f"{text} {href}"
        if not (strong.search(blob) or (jobish.search(href) and 3 <= len(text) <= 180)):
            continue
        key = (p.netloc.lower(), p.path.rstrip('/').lower())
        if key in seen:
            continue
        seen.add(key)
        jobs.append({"title": text[:220] or "Job opening", "url": href})
        if len(jobs) >= max_links:
            break
    return jobs
