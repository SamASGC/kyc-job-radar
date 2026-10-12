"""A failed Workday API is not a genuinely empty job board."""
from __future__ import annotations
import unittest
from job_radar.sources.workday import fetch_workday


class Response:
    def __init__(self, status, data=None):
        self.status_code = status
        self._data = data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._data


class WorkdayStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_page_403_is_error_not_zero_success(self):
        class Http:
            async def post(self, *args, **kwargs):
                return Response(403)
        with self.assertRaisesRegex(RuntimeError, "403"):
            await fetch_workday(Http(), {"name": "Fund Admin"},
                                "https://fundadmin.wd103.myworkdayjobs.com/External")

    async def test_legitimate_empty_list_stays_empty(self):
        class Http:
            async def post(self, *args, **kwargs):
                return Response(200, {"jobPostings": []})
        rows = await fetch_workday(
            Http(), {"name": "Fund Admin"},
            "https://fundadmin.wd103.myworkdayjobs.com/External",
        )
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
