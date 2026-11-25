import datetime as dt
import unittest
from scripts.aml339_schedule_watchdog import decide

NOW=dt.datetime(2026,11,25,1,20,tzinfo=dt.timezone.utc)
def run(mins,status="completed",branch="main",event="schedule"):
    return {"created_at":(NOW-dt.timedelta(minutes=mins)).isoformat(),"status":status,"head_branch":branch,"event":event}
class ScheduleWatchdogTests(unittest.TestCase):
    def test_stale_and_missing(self):
        self.assertEqual(decide([run(300)],NOW,60),"dispatch")
        self.assertEqual(decide([],NOW,15),"dispatch")
    def test_active_run_never_duplicated(self):
        for s in ("queued","in_progress","requested","waiting","pending"):
            self.assertEqual(decide([run(90,s)],NOW,60),"in_flight")
    def test_recent_failed_attempt_throttled(self):
        self.assertEqual(decide([run(20)],NOW,60),"recent_attempt")
    def test_pr_cannot_suppress_recovery(self):
        self.assertEqual(decide([run(1,"in_progress","feature","pull_request")],NOW,60),"dispatch")
    def test_recent_publication_prevents_duplicate(self):
        self.assertEqual(decide([],NOW,60,(NOW-dt.timedelta(minutes=5)).isoformat()),"fresh_report")
    def test_reject_invalid_response(self):
        with self.assertRaises(ValueError):decide(None,NOW,60)
