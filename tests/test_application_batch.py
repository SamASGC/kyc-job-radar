"""Regression coverage for bounded, fail-closed application verification."""
import asyncio
import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from job_radar.application_batch import verify_application_pages


class ApplicationBatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_host_and_global_limits_preserve_job_order(self):
        jobs = [
            SimpleNamespace(apply_url=f"https://{host}/jobs/{i}", idx=i)
            for i, host in enumerate(["careers.example.org"] * 12
                                     + ["ats.example.net"] * 7
                                     + ["recruit.example.com"] * 7)
        ]
        active = 0
        peak_total = 0
        active_hosts = Counter()
        peak_hosts = Counter()

        async def fake_verify(http, job, *, max_hours):
            nonlocal active, peak_total
            host = urlsplit(job.apply_url).hostname
            self.assertEqual(max_hours, 96)
            active += 1
            active_hosts[host] += 1
            peak_total = max(peak_total, active)
            peak_hosts[host] = max(peak_hosts[host], active_hosts[host])
            try:
                await asyncio.sleep(0.006)
                return job.idx
            finally:
                active -= 1
                active_hosts[host] -= 1

        with patch("job_radar.v2_quality.verify_application_page", new=fake_verify):
            results = await verify_application_pages(None, jobs, max_concurrent=6, per_host=2)
        self.assertEqual(results, list(range(len(jobs))))
        self.assertLessEqual(peak_total, 6)
        self.assertGreater(peak_total, 2)
        self.assertTrue(all(n <= 2 for n in peak_hosts.values()), peak_hosts)

    async def test_errors_are_returned_as_unverified_not_silently_accepted(self):
        jobs = [SimpleNamespace(apply_url=f"https://test.example.org/jobs/{i}", idx=i)
                for i in range(3)]

        async def fake_verify(http, job, *, max_hours):
            if job.idx == 1:
                raise RuntimeError("HTTP 429 / incomplete verification")
            return job.idx == 0

        with patch("job_radar.v2_quality.verify_application_page", new=fake_verify):
            results = await verify_application_pages(None, jobs)
        self.assertEqual(results[0], True)
        self.assertIsInstance(results[1], RuntimeError)
        self.assertEqual(results[2], False)

    async def test_empty_and_invalid_limits(self):
        self.assertEqual(await verify_application_pages(None, []), [])
        with self.assertRaises(ValueError):
            await verify_application_pages(None, [], per_host=0)
        with self.assertRaises(ValueError):
            await verify_application_pages(None, [], max_concurrent=0)


if __name__ == "__main__":
    unittest.main()
