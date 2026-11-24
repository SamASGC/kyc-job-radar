#!/usr/bin/env python3
"""Recover exact official per-employer job evidence from a completed Actions run.

GitHub's actions/download-artifact@v4 cross-run pattern search only retrieves
its FIRST 100 artifacts. Run 45434801153 retained 147 source artifacts +
one publisher audit artifact; naive pattern replay lost 5/18 original core
sources. Paginate all GitHub Actions artifact pages, enforce exact source names
and per-source JSON IDs, and never contact any employer jobs service here.

This script NEVER invokes the real employer parsers, sends job applications,
changes the existing history, or claims company names are licensed/employing.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from scripts.aml339_source_manifest import (
    CORE, EXPANSION, REGULATED, REGULATOR50, REG100_LIVE,
)
from batch50_sources import BATCH50
from growth_wave50_sources import WAVE50_B

RUN_ID=45434801153
MAX_ARCHIVE_BYTES=20_000_000
SOURCE_GROUPS=(
    ("aml339-main18-source-",CORE,True),
    ("aml339-expansion-source-",EXPANSION,False),
    ("aml339-regulated-source-",REGULATED,False),
    ("aml339-wave50-source-",BATCH50,False),
    ("aml339-growth50-live-source-",WAVE50_B,False),
    ("aml339-regulator50-live-source-",REGULATOR50,False),
    ("aml339-reg100-live-",REG100_LIVE,False),
)


def expected_artifacts():
    out={}
    for prefix,ids,is_core in SOURCE_GROUPS:
        for sid in ids:
            name=prefix+sid
            if name in out:
                raise ValueError("Duplicated artifact name")
            out[name]=(sid,is_core)
    if len(out)!=147 or sum(1 for sid,core in out.values() if core)!=18:
        raise RuntimeError("Pinned official source set no longer 147 with 18 original core")
    return out


def api_json(url, token):
    req=urllib.request.Request(url,headers={
       "Authorization":"Bearer "+token,
       "Accept":"application/vnd.github+json",
       "X-GitHub-Api-Version":"2022-11-28",
       "User-Agent":"AML339-secure-source-artifact-recovery"})
    with urllib.request.urlopen(req,timeout=30) as response:
        data=response.read(3_000_000)
        if len(data)>=3_000_000:
            raise ValueError("GitHub artifact metadata exceeds expected size")
    return json.loads(data)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def read_zip_bytes(url, token):
    """Use auth only with api.github.com, NEVER on signed Azure blob redirect."""
    parts=urllib.parse.urlsplit(url)
    if parts.scheme!="https" or parts.hostname!="api.github.com":
        raise ValueError("Unexpected GitHub artifact download endpoint")
    req=urllib.request.Request(url,headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "User-Agent":"AML339-secure-source-artifact-recovery"})
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=30) as response:
            raise ValueError("Unexpected unredirected artifact download")
    except urllib.error.HTTPError as error:
        if error.code not in (302,303,307,308):
            raise
        signed=error.headers.get("Location") or ""
    remote=urllib.parse.urlsplit(signed)
    if (remote.scheme!="https" or not remote.hostname or
        not (remote.hostname.endswith(".blob.core.windows.net")
             or remote.hostname.endswith(".actions.githubusercontent.com"))):
        raise ValueError("Unexpected artifact signed archive redirect host")
    # A second request deliberately carries NO GitHub access token.
    with urllib.request.urlopen(urllib.request.Request(
        signed,headers={"User-Agent":"AML339-source-artifacts"}),timeout=35) as response:
        archive=response.read(MAX_ARCHIVE_BYTES+1)
    if len(archive)>MAX_ARCHIVE_BYTES:
        raise ValueError("Source archive larger than allowed size")
    return archive


def list_complete_run_artifacts(repo, token, run_id=RUN_ID):
    if run_id!=RUN_ID:
        raise ValueError("Historical evidence run must match pinned audit")
    base=f"https://api.github.com/repos/{repo}/actions/runs/{RUN_ID}/artifacts"
    found={}
    expected_total=None
    for page in range(1,6):
        payload=api_json(base+f"?per_page=100&page={page}",token)
        items=payload.get("artifacts")
        total=payload.get("total_count")
        if not isinstance(total,int) or not isinstance(items,list):
            raise ValueError("Malformed GitHub Actions artifact listing")
        if expected_total is None:
            expected_total=total
        if total!=expected_total or total>400:
            raise ValueError("GitHub artifact listing changed or exceeded limit")
        for item in items:
            name=item.get("name")
            if not isinstance(name,str) or name in found:
                raise ValueError("Duplicate or invalid Actions artifact")
            found[name]=item
        if len(found)>=total:
            break
        if not items:
            raise ValueError("Missing a GitHub artifact metadata page")
    if len(found)!=expected_total:
        raise ValueError("Incomplete GitHub artifact listing, probable pagination issue")
    return found


def materialize(repo, token, core_dir, optional_dir):
    required=expected_artifacts()
    artifacts=list_complete_run_artifacts(repo,token)
    missing=set(required)-set(artifacts)
    if missing:
        raise RuntimeError("Missing old scan artifacts: "+repr(sorted(missing)))
    core_dir.mkdir(parents=True,exist_ok=True)
    optional_dir.mkdir(parents=True,exist_ok=True)
    processed=0
    for name,(sid,is_core) in required.items():
        info=artifacts[name]
        if info.get("expired") is True or info.get("size_in_bytes",0)>MAX_ARCHIVE_BYTES:
            raise RuntimeError("Expired or oversized original job source artifact: "+sid)
        archive=read_zip_bytes(info["archive_download_url"],token)
        digest=info.get("digest")
        if digest and digest.startswith("sha256:"):
            actual=hashlib.sha256(archive).hexdigest()
            if actual!=digest.removeprefix("sha256:"):
                raise RuntimeError("GitHub source artifact checksum mismatch: "+sid)
        filename=("source_" if is_core else "candidate_")+sid+".json"
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            members=[x for x in z.namelist() if not x.endswith("/")]
            if members!=[filename]:
                raise ValueError("Unexpected source archive content: "+name)
            raw=z.read(filename)
        data=json.loads(raw)
        if (data.get("total_configured_sources")!=339
                or data.get("mode")!="READ_ONLY_ISOLATED_NO_PRODUCTION_DATA"
                or len(data.get("sources",[]))!=1
                or data["sources"][0].get("source_id")!=sid):
            raise ValueError("Corrupted or mismatched official employer artifact: "+name)
        parent=core_dir if is_core else optional_dir
        dest=parent/name
        dest.mkdir(exist_ok=True)
        (dest/filename).write_bytes(raw)
        processed+=1
    print("AML339_REPLAY_PAGINATED_ARTIFACTS",json.dumps({
        "source_run":RUN_ID,
        "artifacts_seen":len(artifacts),
        "validated_source_reports":processed,
        "original_core_reports":len(CORE),
        "independent_optional_reports":processed-len(CORE),
        "employer_jobs_requeried":0,
    }),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY"))
    p.add_argument("--core-dir",type=Path,default=Path("sources"))
    p.add_argument("--optional-dir",type=Path,default=Path("extras"))
    p.add_argument("--run-id",type=int,default=RUN_ID)
    args=p.parse_args()
    token=os.environ.get("GH_TOKEN")
    if not token or not args.repo or "/" not in args.repo:
        raise SystemExit("Missing repository or read-only artifact token")
    if args.run_id!=RUN_ID:
        raise SystemExit("Refusing artifacts from a different GitHub scan")
    materialize(args.repo,token,args.core_dir,args.optional_dir)


if __name__=="__main__":
    main()
