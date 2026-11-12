"""Create one reviewable PR. Never merge, force-push, or write to main."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.request import Request, urlopen
from .common import ROOT


def git(*args: str) -> str:
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()


def github(path: str, data: dict | None = None):
    request=Request("https://api.github.com"+path,data=json.dumps(data).encode() if data is not None else None,headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},method="POST" if data is not None else "GET")
    with urlopen(request,timeout=30) as response:return json.load(response)


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--kind",required=True,choices=["workload","model","platform","recovery"])
    parser.add_argument("--change-id",required=True)
    args=parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{7,63}",args.change_id):raise ValueError("Invalid change ID")
    repo=os.environ["GITHUB_REPOSITORY"]
    branch=f"release/{args.kind}-{args.change_id}"
    pulls=github(f"/repos/{repo}/pulls?state=open&per_page=100")
    existing=[p for p in pulls if p["head"]["ref"]==branch]
    if existing:
        print(existing[0]["html_url"]);return
    if any(p["head"]["ref"].startswith("release/") for p in pulls):
        raise ValueError("Another managed desired-state PR is open; rebase/retry after it is resolved")
    base=git("rev-parse","HEAD")
    remote=git("ls-remote","origin","refs/heads/main").split()[0]
    if remote!=base:raise ValueError("Authoritative main changed during preparation; retry from current main")
    changed=git("status","--porcelain")
    if not changed:
        print("No desired-state changes");return
    subprocess.run(["git","switch","-c",branch],cwd=ROOT,check=True)
    subprocess.run(["git","config","user.name","MaintAI GitOps Automation"],cwd=ROOT,check=True)
    subprocess.run(["git","config","user.email","maintai-gitops@users.noreply.github.com"],cwd=ROOT,check=True)
    subprocess.run(["git","add","state","workloads","applications","platform","environments"],cwd=ROOT,check=True)
    subprocess.run(["git","commit","-m",f"{args.kind}: {args.change_id}"],cwd=ROOT,check=True)
    # Askpass keeps short-lived credentials out of the remote URL and command arguments.
    with tempfile.TemporaryDirectory() as directory:
        askpass=Path(directory)/"askpass"
        askpass.write_text('#!/bin/sh\ncase "$1" in *Username*) printf "%s" "x-access-token" ;; *) printf "%s" "$GH_TOKEN" ;; esac\n')
        askpass.chmod(0o700)
        env={**os.environ,"GIT_ASKPASS":str(askpass),"GIT_TERMINAL_PROMPT":"0"}
        subprocess.run(["git","push","origin",f"HEAD:refs/heads/{branch}"],cwd=ROOT,env=env,check=True)
    body=(f"Updates {args.kind} desired state using versioned release contracts.\n\n"
          "Images are immutable digests; model objects retain S3 versions and checksums. "
          "Review compatibility, migrations and rollback before merging. "
          "This receiver does not deploy to the cluster or merge this PR.\n\n"
          f"Prepared from main `{base}`. Validation results come from this PR's checks.")
    result=github(f"/repos/{repo}/pulls",{"title":f"{args.kind}: {args.change_id}","head":branch,"base":"main","body":body})
    print(result["html_url"])

if __name__=="__main__":main()
