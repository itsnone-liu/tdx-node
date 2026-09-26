#!/usr/bin/env python3
"""Create a private GitHub repo for tdx-node using the stored git credential.
Never prints the token itself. Only prints login, scopes, and repo creation result.
"""
import json
import subprocess
import sys

import requests

REPO_NAME = "tdx-node"


def get_stored_credential() -> dict:
    inp = "protocol=https\nhost=github.com\n\n"
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input=inp,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    cred = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            cred[k] = v
    return cred


def main() -> int:
    cred = get_stored_credential()
    token = cred.get("password", "")
    username = cred.get("username", "")
    if not token:
        print("NO_STORED_TOKEN")
        return 2

    sess = requests.Session()
    sess.headers["Authorization"] = f"token {token}"
    sess.headers["Accept"] = "application/vnd.github+json"
    sess.headers["User-Agent"] = "tdx-node-setup"

    r = sess.get("https://api.github.com/user", timeout=30)
    if r.status_code != 200:
        print("AUTH_CHECK_FAILED", r.status_code, r.text[:300])
        return 3
    login = r.json().get("login", "")
    scopes = r.headers.get("x-oauth-scopes", "")
    print("LOGIN=", login)
    print("STORED_USERNAME=", username)
    print("SCOPES=", scopes)
    if "repo" not in scopes and "workflow" not in scopes:
        print("MISSING_REPO_SCOPE")
        return 4

    # Does the repo already exist?
    r = sess.get(f"https://api.github.com/repos/{login}/{REPO_NAME}", timeout=30)
    if r.status_code == 200:
        info = r.json()
        print("REPO_EXISTS", info.get("full_name"), "private=", info.get("private"))
        return 0

    r = sess.post(
        "https://api.github.com/user/repos",
        json={
            "name": REPO_NAME,
            "description": "TongdaXin local data node capability audit: probes, manifests, sanitized evidence",
            "private": True,
            "has_issues": True,
            "auto_init": False,
        },
        timeout=30,
    )
    if r.status_code == 201:
        info = r.json()
        print("REPO_CREATED", info.get("full_name"), "private=", info.get("private"))
        print("HTML_URL=", info.get("html_url"))
        return 0
    print("REPO_CREATE_FAILED", r.status_code, r.text[:500])
    return 5


if __name__ == "__main__":
    sys.exit(main())
