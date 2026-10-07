#!/usr/bin/env python3
"""Copy purchased DLC archives from a local Steam installation."""
import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

from project import ROOT, SOURCE, sha256

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("steam_dlcs", type=Path, help="DLC directory of your purchased Steam installation")
args = parser.parse_args()
STEAM_DLCS = args.steam_dlcs
TARGET = SOURCE / "game/dlcs"
archives = sorted(STEAM_DLCS.glob("*.teaac"))
if not archives:
    sys.exit(f"No DLC archives found in {STEAM_DLCS}")
TARGET.mkdir(parents=True, exist_ok=True)
manifest = []
for source in archives:
    with zipfile.ZipFile(source) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Damaged archive: {source}: {bad}")
        entries = len(archive.infolist())
    destination = TARGET / source.name
    shutil.copy2(source, destination)
    source_hash = sha256(source)
    manifest.append({"file": source.name, "source": str(source),
                     "bytes": source.stat().st_size, "entries": entries,
                     "sha256": source_hash})
    print(f"Imported {source.name}: {entries} entries; SHA-256 {source_hash}.")
(ROOT / "logs/dlc-import.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Run scripts/package-native.py to include these DLCs in the app.")
