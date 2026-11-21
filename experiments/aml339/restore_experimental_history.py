#!/usr/bin/env python3
"""Locate last successful experimental E2E run before current one.

Never treat a missing/expired prior artifact as a fresh history. Fail closed.
Only reads GitHub metadata; gh CLI downloads the named artifact.
"""
from __future__ import annotations
import argparse
import json
import os
import urllib.parse
import urllib.request

WORKFLOW_PATH=".github/workflows/aml339_e2e_dry_run.yml"
ARTIFACT_NAME="aml339-e2e-isolated-state"
API="https://api.github.com"

def get_json(url, token):
    req=urllib.request.Request(url,headers={
      "Authorization":"Bearer "+token,
      "Accept":"application/vnd.github+json",
      "X-GitHub-Api-Version":"2022-11-28",
      "User-Agent":"aml339-isolated-state-restore/1.0"},method="GET")
    with urllib.request.urlopen(req,timeout=20) as response:
        if response.status!=200:raise RuntimeError("GitHub API non-200")
        return json.loads(response.read(5_000_000))

def find_prior_run(repository,branch,current_run_id,token):
    # Use workflow name AND path: repo-wide workflows may have identical names.
    matches=[]
    for page in range(1,11):
        params=urllib.parse.urlencode({"branch":branch,"per_page":100,"page":page})
        d=get_json(f"{API}/repos/{repository}/actions/runs?{params}",token)
        runs=d.get("workflow_runs",[])
        if not isinstance(runs,list):raise RuntimeError("Unexpected GitHub API response")
        for run in runs:
            if (run.get("id",0)<current_run_id and
                run.get("path","").split("@")[0]==WORKFLOW_PATH and
                run.get("conclusion")=="success" and
                run.get("status")=="completed"):
                matches.append(run)
        if len(runs)<100:break
    else:
        raise RuntimeError("10-page listing limit reached: refuse to reset history")
    if not matches:return None
    return max(matches,key=lambda r:r["id"])

def require_artifact(repository,run_id,token):
    d=get_json(f"{API}/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",token)
    arts=d.get("artifacts")
    if not isinstance(arts,list):raise RuntimeError("Missing artifact metadata")
    matches=[a for a in arts if a.get("name")==ARTIFACT_NAME]
    if len(matches)!=1 or matches[0].get("expired") is not False:
        raise RuntimeError("Prior history artifact unavailable/expired; refusing duplicate alerts")
    return matches[0]["id"]

def tests():
    assert WORKFLOW_PATH.endswith("aml339_e2e_dry_run.yml")
    assert ARTIFACT_NAME.startswith("aml339-e2e")
    print("E2E_RESTORE_TESTS_PASSED",flush=True)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--repo",required=True)
    a.add_argument("--branch",required=True)
    a.add_argument("--current-run-id",required=True,type=int)
    a.add_argument("--github-output",required=True)
    a.add_argument("--self-test",action="store_true")
    args=a.parse_args()
    tests()
    if args.self_test:return
    expected_branch="experiment/aml339-http-diagnostic-20261121"
    if args.branch!=expected_branch or not args.repo.endswith("/kyc-job-radar"):
        raise SystemExit("Isolated experimental repo/branch only")
    token=os.environ.get("GH_TOKEN") or ""
    if len(token)<10:raise SystemExit("Missing read-only GitHub token")
    match=find_prior_run(args.repo,args.branch,args.current_run_id,token)
    if match:
        artifact_id=require_artifact(args.repo,match["id"],token)
        print("E2E_PRIOR_SUCCESS_STATE",json.dumps({
            "run_id":match["id"],"artifact_id":artifact_id,
            "created_at":match.get("created_at")}),flush=True)
        run_id=str(match["id"])
    else:
        print("E2E_FIRST_RUN_NO_PRIOR_HISTORY",flush=True)
        run_id=""
    with open(args.github_output,"a",encoding="utf-8") as output:
        output.write("prior_run_id="+run_id+"\n")

if __name__=="__main__":main()
