#!/usr/bin/env python3
"""Run the bundled game with a disposable profile and record DLC startup."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import time

from project import APP, LOGS, ROOT
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seconds", type=int, default=30)
args = parser.parse_args()

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
home = ROOT / "build" / f"runtime-dlc-{stamp}"
settings = home / "Library/Application Support/T-Engine/4.0/settings"
settings.mkdir(parents=True, exist_ok=True)
(settings / "disable_all_connectivity.cfg").write_text("disable_all_connectivity = true\n")
logs = LOGS
system_log = Path("/tmp/te4_log.txt")
old_stat = system_log.stat() if system_log.exists() else None
command = [str(APP / "Contents/MacOS/t-engine"), "--home", str(home),
           "--flush-stdout", "--no-web", "-Mtome", "-n", "-uDLCCheck"]
print(f"Testing DLC character creation for {args.seconds} seconds; profile: {home}", flush=True)
with (logs / "dlc-verified-stderr.log").open("w") as output:
    process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + args.seconds
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.25)
        running = process.poll() is None
        exit_code = process.poll()
        fresh_log = system_log.exists() and (
            old_stat is None or system_log.stat().st_mtime_ns != old_stat.st_mtime_ns
            or system_log.stat().st_size != old_stat.st_size)
        startup = system_log.read_text(errors="replace") if fresh_log else ""
        if fresh_log:
            shutil.copyfile(system_log, logs / "dlc-verified-startup.log")
        checks = {
            "game_running": running,
            "fresh_log": fresh_log,
            "ashes_loaded": "[MODULE LOADER] addon \tashes-urhrok\t MD5" in startup,
            "orcs_loaded": "[MODULE LOADER] addon \torcs\t MD5" in startup,
            "cults_loaded": "[MODULE LOADER] addon \tcults\t MD5" in startup,
            "tome_loaded": "[MODULE LOADER] done loading module\tTales of Maj'Eyal: Age of Ascendancy" in startup,
            "no_lua_errors": bool(startup) and "Lua Error:" not in startup,
            "openal_soft": "OpenAL Soft" in startup,
        }
        report = {"time": stamp, "profile": str(home), "exit_code": exit_code,
                  "checks": checks, "passed": all(checks.values())}
        (logs / "dlc-startup-check.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        print("Test process closed.", flush=True)

raise SystemExit(0 if report["passed"] else 1)
