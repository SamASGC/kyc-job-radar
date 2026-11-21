#!/usr/bin/env python3
"""Controlled changes regression for AML339 E2E historical alert behavior.

All URLs/roles here are fixtures; no employer HTTP requests and NO real alerts.
Actual first-published timestamp verification remains required in live scans.
"""
import datetime as dt
from alert_history import blank_history,select_and_merge
from two_lane_alert_preview import role_template

UTC=dt.timezone.utc
def fresh_date():
    return (dt.datetime.now(UTC)-dt.timedelta(minutes=45)).isoformat()

def verified_new_role(title,url,**kwargs):
    fields={"class":"possible_match_confirmed_recent",
            "publication_status":"fresh",
            "original_posting_date":fresh_date(),
            "date_field":"Vinted.GH.first_published",
            "geography":"target","functions":["PEP","Sanctions screening"],
            "explicit_duties":["PEP","Sanctions screening"],
            "application_verified":True,"barriers":[],"uncertainties":[]}
    fields.update(kwargs)
    return role_template(title=title,url=url,evaluation=fields)

def tests():
    known=[role_template(url="https://mock.employer.invalid/jobs/0001",title="AML Specialist"),
           role_template(url="https://mock.employer.invalid/jobs/0002",title="Junior AML")]
    history,initial=select_and_merge([("mock",r) for r in known],blank_history())
    assert initial["new_counts"]=={"confirmed_recent":0,"promising_date_unconfirmed":2}
    newcomer=verified_new_role("PEP and Sanctions Analyst",
        "https://mock.employer.invalid/jobs/0003")
    next_state,change=select_and_merge(
        [("mock",r) for r in known]+[("mock",newcomer)],history)
    assert change["new_counts"]=={"confirmed_recent":1,"promising_date_unconfirmed":0},change
    _,repeated=select_and_merge(
        [("mock",r) for r in known]+[("mock",newcomer)],next_state)
    assert repeated["new_counts"]=={"confirmed_recent":0,"promising_date_unconfirmed":0},repeated
    # A first-published timestamp from long ago is not 'new' just because we
    # noticed the posting today.
    stale=verified_new_role("Old SAN Analyst","https://mock.employer.invalid/jobs/0004",
        **{"class":"manual_review","publication_status":"old",
           "original_posting_date":"2025-10-01T00:00:00+00:00"})
    _,old_report=select_and_merge([("mock",stale)],next_state)
    assert old_report["new_counts"]=={"confirmed_recent":0,"promising_date_unconfirmed":0}
    # Merely changing a last-updated/Ashby publication timestamp must not
    # produce a 'confirmed-recent' alert.
    edited=verified_new_role("Edited AML Role","https://mock.employer.invalid/jobs/0005",
        **{"class":"manual_review","date_field":"Ashby.publishedAt",
           "uncertainties":["Might be a republication"]})
    uncertain_state,uncertain=select_and_merge([("mock",edited)],next_state)
    assert uncertain["new_counts"]=={"confirmed_recent":0,"promising_date_unconfirmed":1}
    # The same undated role may be promoted once when its actual original
    # publication date becomes verified, with no repeat afterwards.
    promoted=verified_new_role("Edited AML Role","https://mock.employer.invalid/jobs/0005")
    promoted_state,promotion=select_and_merge([("mock",promoted)],uncertain_state)
    assert promotion["new_counts"]=={"confirmed_recent":1,"promising_date_unconfirmed":0}
    _,second_promotion=select_and_merge([("mock",promoted)],promoted_state)
    assert second_promotion["new_counts"]=={"confirmed_recent":0,"promising_date_unconfirmed":0}
    # A new role under an entirely new original first-published date may be
    # eligible even though the source has been observed in earlier scans.
    print("LIVE_E2E18_CONTROLLED_CHANGE_TESTS_PASSED",flush=True)

if __name__=="__main__":
    tests()
