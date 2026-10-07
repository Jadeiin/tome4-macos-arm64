#!/usr/bin/env python3
"""Verify native ARM64 architecture and that runtime links stay inside the app."""
import json
import platform
import subprocess
from pathlib import Path

from macho import inspect, resolve, system_library

from project import APP, LOGS, ROOT
EXECUTABLE = APP / "Contents/MacOS/t-engine"
FRAMEWORKS = APP / "Contents/Frameworks"
game = inspect(EXECUTABLE)
if any("OpenAL.framework" in name for name in game["dependencies"]):
    raise RuntimeError("The game must use bundled OpenAL Soft instead of Apple's OpenAL framework.")
for required in ["libopenal.", "libluajit-5.1"]:
    if not any(required in name for name in game["dependencies"]):
        raise RuntimeError(f"Missing required runtime library: {required}")
queue = [EXECUTABLE, FRAMEWORKS / "libSDL3.dylib"]
checked = {}
while queue:
    binary = queue.pop().resolve()
    if str(binary) in checked:
        continue
    if not binary.is_relative_to(APP.resolve()):
        raise RuntimeError(f"Runtime library is outside the app: {binary}")
    archs = subprocess.check_output(["/usr/bin/lipo", "-archs", str(binary)], text=True).strip().split()
    if archs != ["arm64"]:
        raise RuntimeError(f"Expected native ARM64 only: {binary}: {archs}")
    checked[str(binary)] = archs
    info = inspect(binary)
    if info["id"] and not info["id"].startswith("@rpath/"):
        raise RuntimeError(f"Unexpected absolute library ID in {binary}: {info['id']}")
    for rpath in info["rpaths"]:
        if rpath.startswith("/") and not system_library(rpath):
            raise RuntimeError(f"External search path in {binary}: {rpath}")
    for name in info["dependencies"]:
        if system_library(name):
            continue
        if not name.startswith(("@loader_path/", "@executable_path/", "@rpath/")):
            raise RuntimeError(f"External runtime dependency in {binary}: {name}")
        queue.append(resolve(name, binary, EXECUTABLE, info["rpaths"]))
manifest = json.loads((APP / "Contents/Resources/runtime-libraries.json").read_text())
actual = {Path(path).name for path in checked if Path(path) != EXECUTABLE.resolve()}
expected = {record["name"] for record in manifest["runtime_libraries"]}
if actual != expected:
    raise RuntimeError(f"Runtime manifest differs from the resolved graph: {actual ^ expected}")
subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(APP)], check=True)
report = {"host_architecture": platform.machine(), "macOS": platform.mac_ver()[0],
          "executable": str(EXECUTABLE), "runtime_requires_homebrew": False,
          "runtime_binaries": checked}
(ROOT / "logs/native-architectures.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"Verified native ARM64 game and {len(checked) - 1} bundled runtime libraries; all non-system links stay inside the app.")
