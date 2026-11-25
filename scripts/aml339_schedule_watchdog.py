#!/usr/bin/env python3
"""Recover missed AML339 schedules using the independently running original radar.
Only dispatch known workflows on main, never change code, source history, or alerts.
A dispatch receipt does not establish a successful scan."""
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

UTC=dt.timezone.utc
TARGETS={
    "aml339_main18.yml": (60,"public/aml339/summary.json","checked_at_utc"),
    "aml339_autonomous_growth.yml": (15,None,None),
}
BUSY={"queued","in_progress","requested","waiting","pending"}
def timestamp(s):
    return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
def decide(runs,now,interval,stamp=None):
    """Never duplicate an in-flight main scan; throttle failed as well as good runs."""
    if not isinstance(runs,list):raise ValueError("Missing workflow run list")
    runs=[r for r in runs if r.get("head_branch")=="main" and r.get("event") in ("push","schedule","workflow_dispatch")]
    if any(r.get("status") in BUSY for r in runs):
        return "in_flight"
    if runs:
        latest=max(timestamp(r["created_at"]) for r in runs)
        if now-latest<dt.timedelta(minutes=interval):return "recent_attempt"
    if stamp and now-timestamp(stamp)<dt.timedelta(minutes=interval):return "fresh_report"
    return "dispatch"
def api(path,token,body=None):
    base="https://api.github.com/repos/"+os.environ["GITHUB_REPOSITORY"]+"/actions/workflows/"
    req=urllib.request.Request(base+path,headers={
      "Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
      "X-GitHub-Api-Version":"2022-11-28","User-Agent":"AML339-schedule-recovery",
      "Content-Type":"application/json"},
      data=json.dumps(body).encode() if body is not None else None,
      method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req,timeout=20) as r:
        if body is not None:
            if r.status!=204:raise RuntimeError("Unexpected dispatch status "+str(r.status))
            return None
        return json.load(r)
def main():
    token=os.environ["GH_TOKEN"]
    now=dt.datetime.now(UTC)
    out={"checked_at_utc":now.isoformat(),"targets":{}}
    failed=False
    for name,(interval,path,key) in TARGETS.items():
        try:
            stamp=json.loads(Path(path).read_text())[key] if path else None
            # GitHub's server-side branch filter avoids PR canaries masking missed main scans.
            data=api(name+"/runs?branch=main&per_page=30",token)
            decision=decide(data["workflow_runs"],now,interval,stamp)
            record={"decision":decision,"latest_published":stamp}
            if decision=="dispatch":
                api(name+"/dispatches",token,{"ref":"main"})
                record["decision"]="dispatch_accepted"
            out["targets"][name]=record
        except Exception as e:
            out["targets"][name]={"decision":"error","error":type(e).__name__+": "+str(e)[:220]}
            failed=True
    Path("aml339-watchdog.json").write_text(json.dumps(out,indent=2)+"\n")
    print("AML339_WATCHDOG",json.dumps(out),flush=True)
    if failed:raise SystemExit("At least one recovery check failed")
if __name__=="__main__":main()
