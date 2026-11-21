#!/usr/bin/env python3
"""Fail-closed history restore for the isolated LIVE 18-employer workflow.

A cooldown-only GitHub Actions run is marked successful although scan and e2e
were skipped. Ignore ONLY proven deferred runs, never a successful full scan
with a lost or expired historical artifact.
"""
from __future__ import annotations
import argparse
import json
import os
import urllib.parse
import restore_experimental_history as previous

PATH=".github/workflows/aml339_live_e2e18_full.yml"
ARTIFACT="aml339-live18-full-state"
GUARD_ARTIFACT="aml339-payabl-cooldown-decision"
SEED_RUN=44937357980
SEED_NAME="aml339-e2e18-isolated-state"
BRANCH="experiment/aml339-http-diagnostic-20261121"
REPO="SamASGC/kyc-job-radar"

def prior_successful_runs(repo,branch,current,token):
    runs=[]
    for page in range(1,11):
        query=urllib.parse.urlencode({"branch":branch,"per_page":100,"page":page})
        data=previous.get_json(f"{previous.API}/repos/{repo}/actions/runs?{query}",token)
        items=data.get("workflow_runs")
        if not isinstance(items,list):raise RuntimeError("GitHub runs listing missing")
        for item in items:
            if (isinstance(item.get("id"),int) and item["id"]<current
                and item.get("path","").split("@")[0]==PATH
                and item.get("status")=="completed" and item.get("conclusion")=="success"):
                runs.append(item)
        if len(items)<100:break
    else:raise RuntimeError("Github run history exceeded 10 pages; no reset")
    return sorted(runs,key=lambda r:r["id"],reverse=True)

def artifact_names(repo,run_id,token):
    data=previous.get_json(
        f"{previous.API}/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100",token)
    items=data.get("artifacts")
    if not isinstance(items,list):raise RuntimeError("Missing GitHub artifact metadata")
    if len(items)>=100:raise RuntimeError("Artifact pagination required; fail closed")
    return items

def safe_deferred_run(repo,run_id,token,artifacts):
    if not any(a.get("name")==GUARD_ARTIFACT for a in artifacts):return False
    data=previous.get_json(
        f"{previous.API}/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100",token)
    jobs=data.get("jobs")
    if not isinstance(jobs,list) or len(jobs)>=100:
        raise RuntimeError("Cannot confirm whether cooldown run was deferred")
    conclusions={}
    for job in jobs:
        name=str(job.get("name",""))
        if name in ("payabl_cooldown","scan","e2e"):
            conclusions[name]=job.get("conclusion")
    return (conclusions.get("payabl_cooldown")=="success"
            and conclusions.get("scan")=="skipped"
            and conclusions.get("e2e")=="skipped")

def previous_run(repo,branch,current,token):
    if repo!=REPO or branch!=BRANCH:raise ValueError("Unexpected repository/branch")
    for run in prior_successful_runs(repo,branch,current,token):
        run_id=run["id"]
        artifacts=artifact_names(repo,run_id,token)
        matching=[a for a in artifacts if a.get("name")==ARTIFACT]
        if len(matching)==1:
            item=matching[0]
            if item.get("expired") is not False or not isinstance(item.get("id"),int):
                raise RuntimeError("Historical alert state expired or malformed: refusing reset")
            return {"run_id":run_id,"artifact_id":item["id"],
                    "artifact_name":ARTIFACT,"source":"previous_successful_live_run"}
        if matching:raise RuntimeError("Ambiguous historical alert artifacts")
        if safe_deferred_run(repo,run_id,token,artifacts):
            print("LIVE_E2E18_SKIP_DEFERRED_HISTORY_RUN",
                  json.dumps({"run_id":run_id,"reason":"cooldown gated"}),
                  flush=True)
            continue
        raise RuntimeError(
            "Successful full-live run without historical state; refusing reset: "+str(run_id))
    previous.ARTIFACT_NAME=SEED_NAME
    try:item=previous.require_artifact(repo,SEED_RUN,token)
    finally:previous.ARTIFACT_NAME="aml339-e2e-isolated-state"
    return {"run_id":SEED_RUN,"artifact_id":item,
            "artifact_name":SEED_NAME,"source":"audited_snapshot_seed"}

def tests():
    assert ARTIFACT!=SEED_NAME and SEED_RUN>0
    old=previous.get_json
    state_artifact={"name":ARTIFACT,"id":777,"expired":False}
    guard_artifact={"name":GUARD_ARTIFACT,"id":999,"expired":False}
    def fake_http(url,token):
        if "/actions/runs?" in url:
            return {"workflow_runs":[
                {"id":300,"path":PATH+"@testing","status":"completed","conclusion":"success"},
                {"id":200,"path":PATH,"status":"completed","conclusion":"success"}]}
        if "/runs/300/artifacts" in url:return {"artifacts":[guard_artifact]}
        if "/runs/300/jobs" in url:
            return {"jobs":[{"name":"payabl_cooldown","conclusion":"success"},
                            {"name":"scan","conclusion":"skipped"},
                            {"name":"e2e","conclusion":"skipped"}]}
        if "/runs/200/artifacts" in url:return {"artifacts":[state_artifact]}
        raise RuntimeError("Unexpected fake API URL "+url)
    previous.get_json=fake_http
    try:
        result=previous_run(REPO,BRANCH,301,"fake-token")
        assert result["run_id"]==200 and result["artifact_id"]==777,result
    finally:previous.get_json=old
    print("LIVE_E2E18_RESTORE_TESTS_PASSED",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    p.add_argument("--branch",required=True)
    p.add_argument("--run-id",type=int,required=True)
    p.add_argument("--github-output",required=True)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    tests()
    if a.self_test:return
    token=os.environ.get("GH_TOKEN","")
    if len(token)<10:raise RuntimeError("Missing read-only GitHub token")
    result=previous_run(a.repo,a.branch,a.run_id,token)
    print("LIVE_E2E18_RESTORE",json.dumps(result),flush=True)
    with open(a.github_output,"a",encoding="utf-8") as out:
        out.write("prior_run_id="+str(result["run_id"])+"\n")
        out.write("prior_artifact_name="+result["artifact_name"]+"\n")

if __name__=="__main__":main()
