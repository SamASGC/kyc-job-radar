#!/usr/bin/env python3
"""Payabl/Workable rate-limit safeguard for the isolated AML339 GitHub workflow.

Never probes the provider to determine whether the cooldown has expired.
Only computes a conservative UTC not-before time from the actual HTTP 429
observed by GitHub Actions on 2026-11-21.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path

UTC = dt.timezone.utc
# GitHub Actions scan(payabl) observed HTTP 429 on 2026-11-21 18:52:40 UTC
# with an explicit 64472-second delay. See run 44937777439.
RATE_LIMIT_OBSERVED = dt.datetime(2026, 11, 21, 18, 52, 40, tzinfo=UTC)
RETRY_AFTER_SECONDS = 64_472
SAFETY_BUFFER_SECONDS = 20 * 60
ALLOW_AT = RATE_LIMIT_OBSERVED + dt.timedelta(
    seconds=RETRY_AFTER_SECONDS + SAFETY_BUFFER_SECONDS
)

def check(now: dt.datetime):
    if now.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    now = now.astimezone(UTC)
    seconds_remaining = max(0, int((ALLOW_AT-now).total_seconds()+0.999))
    return {"state":"PERMITTED" if now>=ALLOW_AT else "DEFERRED",
            "allowed":now>=ALLOW_AT,
            "checked_at_utc":now.isoformat(),
            "rate_limit_observed_at_utc":RATE_LIMIT_OBSERVED.isoformat(),
            "retry_after_seconds":RETRY_AFTER_SECONDS,
            "extra_safety_seconds":SAFETY_BUFFER_SECONDS,
            "not_before_utc":ALLOW_AT.isoformat(),
            "seconds_remaining":seconds_remaining,
            "provider_requests_made":0}

def tests():
    release=RATE_LIMIT_OBSERVED+dt.timedelta(seconds=RETRY_AFTER_SECONDS)
    assert release==dt.datetime(2026,11,22,12,47,12,tzinfo=UTC),release
    assert ALLOW_AT==dt.datetime(2026,11,22,13,7,12,tzinfo=UTC),ALLOW_AT
    assert not check(RATE_LIMIT_OBSERVED)["allowed"]
    assert not check(ALLOW_AT-dt.timedelta(microseconds=1))["allowed"]
    assert check(ALLOW_AT)["allowed"]
    assert check(ALLOW_AT+dt.timedelta(minutes=1))["seconds_remaining"]==0
    try:
        check(dt.datetime(2026,11,22,13,0))
    except ValueError:
        pass
    else:
        raise AssertionError("Naive timestamp incorrectly accepted")
    print("PAYABL_429_COOLDOWN_UNIT_TESTS_PASSED",flush=True)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--self-test",action="store_true")
    a.add_argument("--status-out")
    args=a.parse_args()
    tests()
    if args.self_test:
        return
    status=check(dt.datetime.now(UTC))
    print("PAYABL_429_GATE",json.dumps(status,ensure_ascii=False),flush=True)
    github_output=os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output,"a",encoding="utf-8") as f:
            f.write("allowed="+str(status["allowed"]).lower()+"\n")
            f.write("not_before_utc="+status["not_before_utc"]+"\n")
    summary=os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as f:
            f.write("## Payabl / Workable cooldown check\n\n")
            f.write("State: **"+status["state"]+"**. Zero provider requests from this gate.\n\n")
            f.write("Not before UTC: "+status["not_before_utc"]+
                    " (based on observed 429 plus 20 minutes safety).\n\n")
            f.write("A deferred run will skip all 18 HTTP scans, not reset history.\n")
    if args.status_out:
        Path(args.status_out).write_text(
            json.dumps(status,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
