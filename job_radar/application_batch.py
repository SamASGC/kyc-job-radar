"""Bounded verification of job-specific application pages.

No bypass of vacancy proof, posting age, language or role scoring.
Each provider hostname gets a small independent pool to avoid a burst of
many simultaneous application-page GETs (and avoid amplifying HTTP 429s).
A failed request remains unverified; it is never treated as an open job.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit


async def verify_application_pages(http, jobs, *, max_hours: int = 96,
                                   max_concurrent: int = 8,
                                   per_host: int = 2) -> list:
    """Return one verification result per input job, preserving exceptions.

    Host slots are acquired *before* global slots so one overloaded ATS
    cannot monopolise the shared pool while unrelated providers wait.
    """
    if max_concurrent < 1 or per_host < 1:
        raise ValueError("Verification concurrency limits must be positive")

    from job_radar.v2_quality import verify_application_page

    global_gate = asyncio.Semaphore(max_concurrent)
    host_gates: dict[str, asyncio.Semaphore] = {}

    async def one(job):
        url = str(getattr(job, "apply_url", "") or "")
        try:
            hostname = (urlsplit(url).hostname or "").casefold()
        except ValueError:
            hostname = ""
        gate = host_gates.setdefault(hostname, asyncio.Semaphore(per_host))
        async with gate:
            async with global_gate:
                return await verify_application_page(http, job, max_hours=max_hours)

    return await asyncio.gather(*(one(job) for job in jobs), return_exceptions=True)
