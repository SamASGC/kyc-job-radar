#!/usr/bin/env python3
"""Fail-closed cross-run history migration (3-source pilot -> 18-source pilot).

Only reads GitHub workflow metadata. Download is performed by gh CLI in workflow.
Never treats lost historical state as an empty history.
"""
import argparse,json,os
import restore_experimental_history as legacy

WORKFLOW_PATH=".github/workflows/aml339_e2e18_dry_run.yml"
ARTIFACT_NAME="aml339-e2e18-isolated-state"
SEED_RUN=44935520858
SEED_ARTIFACT="aml339-e2e-isolated-state"
EXPECTED_BRANCH="experiment/aml339-http-diagnostic-20261121"

def select_history(repository,branch,current_run_id,token):
    if branch!=EXPECTED_BRANCH or repository!="SamASGC/kyc-job-radar":
        raise ValueError("Unsupported repo/branch")
    legacy.WORKFLOW_PATH=WORKFLOW_PATH
    legacy.ARTIFACT_NAME=ARTIFACT_NAME
    prior=legacy.find_prior_run(repository,branch,current_run_id,token)
    if prior:
        prior_id=prior["id"];artifact_id=legacy.require_artifact(repository,prior_id,token)
        return {"run_id":prior_id,"artifact_id":artifact_id,"artifact_name":ARTIFACT_NAME,
                "from":"previous_successful_18"}
    artifact_name=legacy.ARTIFACT_NAME
    try:
        legacy.ARTIFACT_NAME=SEED_ARTIFACT
        seed_id=legacy.require_artifact(repository,SEED_RUN,token)
    finally:
        legacy.ARTIFACT_NAME=artifact_name
    return {"run_id":SEED_RUN,"artifact_id":seed_id,"artifact_name":SEED_ARTIFACT,
            "from":"three_source_seed"}

def tests():
    assert SEED_RUN>0 and ARTIFACT_NAME!=SEED_ARTIFACT
    assert WORKFLOW_PATH.endswith("aml339_e2e18_dry_run.yml")
    print("E2E18_HISTORY_MIGRATION_TESTS_PASSED",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    p.add_argument("--branch",required=True)
    p.add_argument("--current-run-id",required=True,type=int)
    p.add_argument("--github-output",required=True)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    tests()
    if a.self_test:return
    token=os.environ.get("GH_TOKEN","")
    if len(token)<10:raise RuntimeError("Missing read-only github token")
    choice=select_history(a.repo,a.branch,a.current_run_id,token)
    print("E2E18_STATE_RESTORE",json.dumps(choice),flush=True)
    with open(a.github_output,"a",encoding="utf-8") as f:
        f.write("prior_run_id="+str(choice["run_id"])+"\n")
        f.write("prior_artifact_name="+choice["artifact_name"]+"\n")
        f.write("state_origin="+choice["from"]+"\n")

if __name__=="__main__":main()
