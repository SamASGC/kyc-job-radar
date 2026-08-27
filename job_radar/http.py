from __future__ import annotations

import asyncio
import httpx

DEFAULT_HEADERS = {
    "User-Agent": "KYCJobRadar/1.0 (+personal job-search dashboard; low-frequency crawler)",
    "Accept": "text/html,application/xhtml+xml,application/json,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.7",
}


class Http:
    def __init__(self, concurrency: int = 24, timeout: float = 18.0):
        self.sem = asyncio.Semaphore(concurrency)
        self.client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            headers=DEFAULT_HEADERS,
            limits=httpx.Limits(max_connections=concurrency + 8, max_keepalive_connections=concurrency),
        )

    async def close(self):
        await self.client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        async with self.sem:
            return await self.client.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        async with self.sem:
            return await self.client.post(url, **kwargs)
