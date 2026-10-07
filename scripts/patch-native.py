#!/usr/bin/env python3
"""Apply the pinned upstream patch and install native Lua helpers."""
from pathlib import Path
import shutil
import subprocess

from project import ROOT, SOURCE

patch = ROOT / "patches/native-arm64.patch"
originals = ROOT / "patches/upstream"
for line in patch.read_text().splitlines():
    if not line.startswith("--- a/"):
        continue
    relative = Path(line.removeprefix("--- a/"))
    source = SOURCE / relative
    original = originals / relative
    if not original.exists():
        original.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, original)
    shutil.copy2(original, source)

subprocess.run(["/usr/bin/patch", "--batch", "--silent", "-p1", "-i", str(patch)],
               cwd=SOURCE, check=True)
for source, destination in [("lua51-resolvers.lua", "native-lua51.lua"),
                            ("native-display.lua", "native-display.lua")]:
    shutil.copy2(ROOT / "scripts" / source, SOURCE / "game/loader" / destination)
print("Applied native ARM64 patch and Lua helpers.")
