import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from hourly_http_guard import Guard,PausedHost,load,save,merge,until_from
UTC=dt.timezone.utc
STAMP=dt.datetime(2026,11,24,20,0,tzinfo=UTC)
class HourlyHTTPGuardTests(unittest.TestCase):
    def test_retry_after_seconds_http_date_and_unknown(self):
        self.assertEqual(until_from({"Retry-After":"63364"},STAMP),STAMP+dt.timedelta(seconds=63374))
        self.assertEqual(until_from({"Retry-After":"Wed, 25 Nov 2026 10:00:00 GMT"},STAMP),dt.datetime(2026,11,25,10,0,10,tzinfo=UTC))
        self.assertEqual(until_from({},STAMP),STAMP+dt.timedelta(hours=24))
    def test_no_second_request_and_persistent_pause(self):
        with tempfile.TemporaryDirectory() as tmp,patch("hourly_http_guard.now",return_value=STAMP):
            out=Path(tmp)/"receipt.json";g=Guard({},out);calls=[]
            def blocked(url,*a,**kw):
                calls.append(url)
                raise HTTPError(url,429,"rate limited",{"Retry-After":"7200"},None)
            for _ in range(2):
                with self.assertRaises(PausedHost):g.request(blocked,"https://example.com/jobs")
            self.assertEqual(len(calls),1)
            saved=load(out)
            self.assertEqual(saved["example.com"]["until"],(STAMP+dt.timedelta(seconds=7210)).isoformat())
            g2=Guard(saved,out)
            with self.assertRaises(PausedHost):g2.request(blocked,"https://example.com/next")
            self.assertEqual(len(calls),1)
            self.assertEqual(g2.request(lambda url:"ok","https://different.example/jobs"),"ok")
    def test_merge_keeps_longest_future_deadline(self):
        def rec(h):return {"until":(STAMP+dt.timedelta(hours=h)).isoformat(),"status":429}
        data=merge({"a":rec(4),"b":rec(-1)},[{"a":rec(2),"c":rec(3)},{"a":rec(6)}],STAMP)
        self.assertEqual(data,{"a":rec(6),"c":rec(3)})
    def test_workflow_schedules_and_cooldowns(self):
        s=Path(".github/workflows/aml339_main18.yml").read_text()
        self.assertIn('cron: "23 0-6,8-23 * * *"',s)
        self.assertIn('cron: "23 7 * * *"',s)
        self.assertIn('"$SOURCE" == "payabl" && "$EVENT_SCHEDULE" != "23 7 * * *"',s)
        self.assertEqual(s.count('hourly_http_guard.py" run'),12)
        self.assertIn("needs.persist_cooldowns.result == 'success'",s)
        self.assertIn("always() && needs.prepare_cooldowns.result == 'success'",s)
