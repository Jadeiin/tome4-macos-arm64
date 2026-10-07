#!/usr/bin/env python3
"""Commit the native port, create a GitHub repo, push a release tag and inspect CI with forge."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from forge_client import Forge
from project import LOGS, ROOT, VERSION

CORE_PATHS = [".gitignore", "README.md", "LICENSE", "Brewfile", "project.json", ".github", "scripts", "patches/native-arm64.patch"]
TOP_FILES = {path for path in CORE_PATHS if '/' not in path and not path.startswith('scripts') and path != '.github'}
REPORT = LOGS / "github-publish.json"


def git(*arguments, capture=False):
    environment = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git", *map(str, arguments)], cwd=ROOT, env=environment,
                            text=True, capture_output=capture, timeout=300)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or f"git {' '.join(arguments)} failed").strip())
    return result.stdout.strip() if capture else None


def allowed(path):
    return path in TOP_FILES or path == "patches/native-arm64.patch" or path.startswith(("scripts/", ".github/"))


def write_report(report):
    REPORT.write_text(json.dumps(report, indent=2) + "\n")


def inspect_run(forge, repository, commit, tag, minutes, report):
    deadline = time.monotonic() + minutes * 60
    latest = None
    while time.monotonic() < deadline:
        runs = forge.api(f"repos/{repository}/actions/runs?per_page=50")["workflow_runs"]
        matching = [run for run in runs if run["head_sha"] == commit and run["head_branch"] == tag
                    and run["event"] == "push" and run["path"].split('@')[0] == ".github/workflows/build.yml"]
        if matching:
            latest = max(matching, key=lambda run: run["id"])
            report["action"] = {key: latest[key] for key in ["id", "html_url", "status", "conclusion", "head_sha"]}
            write_report(report)
            print(f"Actions: {latest['status']} ({latest['conclusion'] or 'in progress'}) — {latest['html_url']}", flush=True)
            if latest["status"] == "completed":
                print(forge.run("ci", "view", latest["id"]), flush=True)
                jobs = forge.api(f"repos/{repository}/actions/runs/{latest['id']}/jobs?per_page=100")["jobs"]
                log_directory = LOGS / "actions"
                log_directory.mkdir(exist_ok=True)
                report["job_logs"] = []
                for job in jobs:
                    if job["status"] != "completed" or job["conclusion"] == "skipped":
                        continue
                    path = log_directory / f"{latest['id']}-{job['id']}.log"
                    try:
                        log = forge.run("ci", "log", job["id"])
                    except RuntimeError as error:
                        log = f"Unable to fetch this job log: {error}\n"
                    path.write_text(log)
                    report["job_logs"].append(str(path.relative_to(ROOT)))
                    print(f"Job {job['name']}: {job['conclusion']}; log: {path}", flush=True)
                    if job["conclusion"] == "failure":
                        print('\n'.join(log.splitlines()[-60:]), flush=True)
                write_report(report)
                if latest["conclusion"] != "success":
                    raise RuntimeError(f"Actions failed; job logs saved under {log_directory}")
                release = forge.api(f"repos/{repository}/releases/tags/{tag}")
                names = {asset["name"] for asset in release["assets"]}
                complete = ("SHA256SUMS" in names and "build-info.json" in names
                            and any(name.endswith('.dmg') for name in names)
                            and any(name.endswith('-source.tar.gz') for name in names))
                if release["draft"] or not complete:
                    raise RuntimeError("Actions passed but the public DMG release is missing.")
                print(forge.run("release", "view", tag), flush=True)
                report["release"] = {"url": release["html_url"], "tag": tag,
                                     "assets": [{key: asset[key] for key in ["name", "size", "browser_download_url", "digest"]}
                                                for asset in release["assets"]]}
                report["passed"] = True
                write_report(report)
                return
        else:
            print("Waiting for the tag's Actions run...", flush=True)
        time.sleep(30)
    raise RuntimeError(f"CI wait timed out; repository/tag are preserved. Rerun to continue monitoring. Latest run: {latest and latest['html_url']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="tome4-macos-arm64")
    parser.add_argument("--visibility", choices=["private", "public"], default="private")
    parser.add_argument("--tag", default=f"v{VERSION}-arm64.1")
    parser.add_argument("--proxy", help="Optional HTTP proxy, e.g. http://127.0.0.1:20122")
    parser.add_argument("--ssh", action="store_true", help="Use your existing GitHub SSH key for git push")
    parser.add_argument("--wait-minutes", type=int, default=60)
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.name):
        parser.error("Use a plain GitHub repository name.")
    if not re.fullmatch(r"v" + re.escape(VERSION) + r"-arm64\.[1-9][0-9]*", args.tag):
        parser.error(f"Tag must be v{VERSION}-arm64.N (N >= 1).")
    if not shutil.which("forge"):
        parser.error("The forge CLI is required (brew install git-pkgs-forge).")
    if args.proxy:
        for name in ["HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"]:
            os.environ[name] = args.proxy
    report = {"repository_name": args.name, "visibility": args.visibility, "tag": args.tag, "passed": False}
    write_report(report)
    try:
        probe = Forge(f"placeholder/{args.name}")
        account = probe.api("user")
        owner = account["login"]
        repository = f"{owner}/{args.name}"
        forge = Forge(repository)
        report["repository"] = f"https://github.com/{repository}"
        if not (ROOT / ".git").exists():
            git("init", "-b", "main")
        git("config", "--local", "user.name", owner)
        git("config", "--local", "user.email", f"{account['id']}+{owner}@users.noreply.github.com")
        if Path(git("rev-parse", "--show-toplevel", capture=True)).resolve() != ROOT.resolve():
            raise RuntimeError("This directory is inside a different Git repository; kept unchanged.")
        if git("symbolic-ref", "--short", "HEAD", capture=True) != "main":
            raise RuntimeError("Use the main branch before publishing; no branches were changed.")
        git("add", "--", *CORE_PATHS)
        tracked = git("ls-files", capture=True).splitlines()
        if any(not allowed(path) for path in tracked):
            raise RuntimeError("The index contains files outside the native port; review it before publishing.")
        if git("diff", "--cached", "--name-only", capture=True):
            git("commit", "-m", f"Build ToME {VERSION} natively for Apple Silicon and publish DMGs with CI")
        commit = git("rev-parse", "HEAD", capture=True)
        report["commit"] = commit
        write_report(report)
        remote = forge.api(f"repos/{repository}", allow_missing=True)
        if remote is None:
            print(f"Creating {args.visibility} repository {repository}", flush=True)
            print(forge.run("repo", "create", args.name, f"--{args.visibility}",
                            "--default-branch", "main", "--description", "Native Apple Silicon build of Tales of Maj'Eyal with bundled runtime libraries and DMG releases"), flush=True)
        elif remote["private"] != (args.visibility == "private"):
            raise RuntimeError("Existing repository visibility differs; kept unchanged.")
        https_url = f"https://github.com/{repository}.git"
        ssh_url = f"git@github.com:{repository}.git"
        selected_url = ssh_url if args.ssh else https_url
        remotes = git("remote", capture=True).splitlines()
        if "origin" in remotes:
            existing = git("remote", "get-url", "origin", capture=True)
            if existing not in [https_url, ssh_url]:
                raise RuntimeError(f"origin already points elsewhere; kept unchanged: {existing}")
            if existing != selected_url:
                git("remote", "set-url", "origin", selected_url)
        else:
            git("remote", "add", "origin", selected_url)
        if args.tag in git("tag", "--list", capture=True).splitlines():
            if git("rev-parse", args.tag + "^{commit}", capture=True) != commit:
                raise RuntimeError("Existing release tag points to another commit; choose a new tag.")
        else:
            git("tag", args.tag, commit)
        git("push", "-u", "origin", "main", f"refs/tags/{args.tag}")
        print(f"Repository: https://github.com/{repository}", flush=True)
        print(f"Inspecting tag {args.tag} with forge...", flush=True)
        write_report(report)
        if not args.no_wait:
            inspect_run(forge, repository, commit, args.tag, args.wait_minutes, report)
        print(json.dumps(report, indent=2), flush=True)
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        report["error"] = str(error)
        write_report(report)
        print(f"Stopped: {error}\nProgress saved in {REPORT}", file=sys.stderr, flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
