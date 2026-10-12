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


    async def test_realistic_workday_26_jobs_paginated_in_20_item_batches(self):
        from datetime import datetime, timezone
        date = datetime.now(timezone.utc).date().isoformat()
        responses = []
        for index in range(26):
            responses.append({
                "title": f"Compliance Analyst {index}",
                "locationsText": "Luxembourg",
                "externalPath": f"/job/Luxembourg/Compliance-Analyst-{index}_R{index:04}",
                "postedOn": date,
            })

        class Http:
            def __init__(self):
                self.calls = []

            async def post(self, endpoint, json=None, headers=None):
                self.calls.append((endpoint, dict(json or {})))
                if json["limit"] > 20:
                    return Response(400)
                start = json["offset"]
                return Response(200, {"jobPostings": responses[start:start+20]})

        http = Http()
        jobs = await fetch_workday(
            http, {"name": "Aztec Group", "sector": "Fintech"},
            "https://aztecgroup.wd103.myworkdayjobs.com/External",
        )
        self.assertEqual(len(jobs), 26)
        self.assertEqual([x[1]["offset"] for x in http.calls], [0, 20])
        self.assertTrue(all(x[1]["limit"] == 20 for x in http.calls))
        self.assertTrue(all(j.source_kind == "official ATS" for j in jobs))
        self.assertEqual(len({j.external_id for j in jobs}), 26)


if __name__ == "__main__":
    unittest.main()
