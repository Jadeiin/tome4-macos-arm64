#!/usr/bin/env python3
"""Package the locally built engine and official full game resources."""
import argparse
import json
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from project import APP, PROJECT, ROOT, SOURCE, VERSION

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--without-dlcs", action="store_true", help="Exclude local DLCs for public builds")
parser.add_argument("--build-version", default="4", help="macOS bundle build number (default: 4)")
args = parser.parse_args()
CONTENTS = APP / "Contents"
RESOURCES = CONTENTS / "Resources"
MACOS = CONTENTS / "MacOS"
MACOS.mkdir(parents=True, exist_ok=True)
RESOURCES.mkdir(parents=True, exist_ok=True)
# Replace the inode atomically so an older running process keeps its executable.
shutil.copy2(ROOT / "build/native/t-engine", MACOS / "t-engine.new")
(MACOS / "t-engine.new").replace(MACOS / "t-engine")
for name in ["game", "bootstrap"]:
    ignore = shutil.ignore_patterns("dlcs") if name == "game" and args.without_dlcs else None
    shutil.copytree(SOURCE / name, RESOURCES / name, dirs_exist_ok=True, ignore=ignore)
if args.without_dlcs and (RESOURCES / "game/dlcs").exists():
    shutil.rmtree(RESOURCES / "game/dlcs")
for name in ["COPYING", "COPYING-MEDIA", "CREDITS"]:
    shutil.copy2(SOURCE / name, RESOURCES / name)
shutil.copy2(SOURCE / "mac/te4.icns", RESOURCES / "te4.icns")
config = json.loads((ROOT / "build/native/build-config.json").read_text())
info = {
    "CFBundleName": "Tales of Maj'Eyal",
    "CFBundleDisplayName": "Tales of Maj'Eyal",
    "CFBundleExecutable": "t-engine",
    "CFBundleIdentifier": "org.te4.tome.native",
    "CFBundlePackageType": "APPL",
    "CFBundleShortVersionString": VERSION,
    "CFBundleVersion": args.build_version,
    "CFBundleIconFile": "te4.icns",
    "LSMinimumSystemVersion": config["deployment"],
    "LSArchitecturePriority": ["arm64"],
    "NSHighResolutionCapable": True,
    "LSApplicationCategoryType": "public.app-category.role-playing-games",
    "LSSupportsGameMode": True,
}
(CONTENTS / "PkgInfo").write_bytes(b"APPL????")
subprocess.run([sys.executable, str(ROOT / "scripts/bundle-runtime.py")], check=True)
runtime = json.loads((RESOURCES / "runtime-libraries.json").read_text())
versions = [config["deployment"]] + [record["minimum_macos"] for record in runtime["runtime_libraries"]
                                    if record["minimum_macos"]]
info["LSMinimumSystemVersion"] = max(versions, key=lambda value: tuple(int(part) for part in value.split('.')))
with (CONTENTS / "Info.plist").open("wb") as output:
    plistlib.dump(info, output)
(RESOURCES / "upstream-source.json").write_text(json.dumps(PROJECT, indent=2) + "\n")
subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(APP)], check=True)
subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2", str(APP)], check=True)
APP.touch()
print(APP)
