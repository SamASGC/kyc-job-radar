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

# Company-homepage discovery: find ONE prominent official careers link.
# Without this step a company's registered website is merely fetched as a
# homepage and its careers vacancies are often invisible to the scanner.
def candidate_careers_links(html: str, base_url: str, max_links: int = 2) -> list[str]:
    from urllib.parse import urlsplit, urljoin
    from ipaddress import ip_address
    base = urlsplit(base_url)
    home_host = (base.hostname or "").lower().removeprefix("www.")
    if not home_host or "." not in home_host:
        return []
    destinations = {}
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        href = urljoin(base_url, str(a["href"]).strip())
        try:
            p = urlsplit(href)
            host = (p.hostname or "").lower()
            if p.scheme != "https" or not host or p.username or p.password:
                continue
            try:
                ip_address(host)
                continue
            except ValueError:
                pass
            same_company = (
                host.removeprefix("www.") == home_host or
                host.removeprefix("www.").endswith("." + home_host)
            )
            ats_link = bool(detect_ats("", href))
            if not same_company and not ats_link:
                continue
            label = " ".join(a.stripped_strings).casefold()
            label += " " + (a.get("aria-label") or "").casefold()
            path = (p.path or "").casefold()
            if not (
                any(x in label for x in ("careers", "career", "jobs", "vacancies",
                                       "join our team", "work with us", "open positions",
                                       "trabaja con", "empleo", "join us"))
                or any(x in path for x in ("/careers", "/jobs", "/join-us",
                                           "/work-with-us", "/vacancies", "/career"))
            ):
                continue
            score = (20 if ats_link else 0) + (8 if "career" in path or "jobs" in path else 0)
            score += (5 if "career" in label or "jobs" in label else 0)
            url = p._replace(query="", fragment="").geturl()
            if url == base_url:
                continue
            destinations[url] = max(destinations.get(url, 0), score)
        except (TypeError, ValueError):
            continue
    return [u for u, _ in sorted(destinations.items(),
                                 key=lambda x: (-x[1], x[0]))[:max_links]]
