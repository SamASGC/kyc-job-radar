#!/usr/bin/env python3
"""Wait for GitHub Actions API visibility of an uploaded Pages artifact.

The upload-pages-artifact step can finish before deploy-pages sees the
artifact through GitHub's API. This read-only gate prevents spurious failures.
It cannot bypass source, data, or historical integrity checks.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request


def has_current_pages_artifact(payload: dict) -> bool:
    if not isinstance(payload, dict) or not isinstance(payload.get("artifacts"), list):
        raise ValueError("Malformed GitHub Actions artifacts response")
    if not isinstance(payload.get("total_count"), int):
        raise ValueError("Missing GitHub artifacts total")
    if payload["total_count"] >= 100:
        raise ValueError("Artifact pagination needed; refuse to guess which Pages artifact is current")
    matching = [
        item for item in payload["artifacts"]
        if isinstance(item, dict) and item.get("name") == "github-pages"
        and item.get("expired") is False and isinstance(item.get("id"), int)
    ]
    if len(matching) > 1:
        raise ValueError("Ambiguous duplicate current Pages artifacts")
    return len(matching) == 1


def wait_for_upload(repo: str, run_id: str, token: str,
                    attempts: int = 15, interval: int = 4) -> None:
    if not (repo and run_id.isdecimal() and len(token) >= 10):
        raise ValueError("Missing repository, GitHub run ID or token")
    if attempts < 1 or not 1 <= interval <= 20:
        raise ValueError("Invalid API poll controls")
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    for i in range(attempts):
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "User-Agent": "AML339-Pages-artifact-readiness",
        })
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.load(response)
        if has_current_pages_artifact(payload):
            print("AML339_PAGES_ARTIFACT_VISIBLE", json.dumps({
                "repo": repo, "run_id": run_id, "api_check_number": i + 1
            }), flush=True)
            return
        if i + 1 < attempts:
            time.sleep(interval)
    raise RuntimeError("Pages artifact still not visible after bounded verification; refuse early deployment")


def main():
    wait_for_upload(
        os.environ.get("GITHUB_REPOSITORY", ""),
        os.environ.get("GITHUB_RUN_ID", ""),
        os.environ.get("GH_TOKEN", ""),
    )


if __name__ == "__main__":
    main()
