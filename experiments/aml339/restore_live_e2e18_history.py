#!/usr/bin/env python3
"""Fail-closed state recovery for isolated live 18-source E2E dry-runs.

First run seeds from last successful 18-source snapshot E2E, future runs
use latest successful run of this live workflow. No production state used.
"""
from __future__ import annotations
import argparse,json,os
import restore_experimental_history as previous

PATH=".github/workflows/aml339_live_e2e18_full.yml"
ARTIFACT="aml339-live18-full-state"
SEED_RUN=44937357980
SEED_NAME="aml339-e2e18-isolated-state"
BRANCH="experiment/aml339-http-diagnostic-20261121"

def previous_run(repo,branch,current,token):
    if repo!="SamASGC/kyc-job-radar" or branch!=BRANCH:
        raise ValueError("Unexpected repository or branch")
    previous.WORKFLOW_PATH=PATH
    previous.ARTIFACT_NAME=ARTIFACT
    run=previous.find_prior_run(repo,branch,current,token)
    if run:
        item=previous.require_artifact(repo,run["id"],token)
        return {"run_id":run["id"],"artifact_id":item,"artifact_name":ARTIFACT,
                "source":"previous_successful_live_run"}
    previous.ARTIFACT_NAME=SEED_NAME
    try:item=previous.require_artifact(repo,SEED_RUN,token)
    finally:previous.ARTIFACT_NAME=ARTIFACT
    return {"run_id":SEED_RUN,"artifact_id":item,"artifact_name":SEED_NAME,
            "source":"audited_snapshot_seed"}

def tests():
    assert ARTIFACT!=SEED_NAME and SEED_RUN>0
    print("LIVE_E2E18_RESTORE_TESTS_PASSED",flush=True)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--repo",required=True)
    a.add_argument("--branch",required=True)
    a.add_argument("--run-id",type=int,required=True)
    a.add_argument("--github-output",required=True)
    a.add_argument("--self-test",action="store_true")
    args=a.parse_args()
    tests()
    if args.self_test:return
    token=os.environ.get("GH_TOKEN","")
    if len(token)<10:raise RuntimeError("Read-only token missing")
    state=previous_run(args.repo,args.branch,args.run_id,token)
    print("LIVE_E2E18_RESTORE",json.dumps(state),flush=True)
    with open(args.github_output,"a",encoding="utf-8") as f:
        f.write("prior_run_id="+str(state["run_id"])+"\n")
        f.write("prior_artifact_name="+state["artifact_name"]+"\n")

if __name__=="__main__":main()
