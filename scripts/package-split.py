#!/usr/bin/env python3
"""Derive the split asset layout from the complete native app."""
import plistlib
import shutil
import subprocess

from project import APP, APPS, SPLIT

if SPLIT.exists():
    shutil.rmtree(SPLIT)
SPLIT.mkdir()
app = APPS["split"]
subprocess.run(["/usr/bin/ditto", str(APP), str(app)], check=True)
for name in ["game", "bootstrap", "COPYING", "COPYING-MEDIA", "CREDITS"]:
    (app / "Contents/Resources" / name).rename(SPLIT / name)
plist = app / "Contents/Info.plist"
with plist.open("rb") as stream:
    info = plistlib.load(stream)
info["TE4AssetLayout"] = "split"
info["CFBundleName"] = "T-Engine"
info["CFBundleDisplayName"] = "T-Engine"
with plist.open("wb") as stream:
    plistlib.dump(info, stream)
subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(app)], check=True)
subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True)
print(SPLIT)
