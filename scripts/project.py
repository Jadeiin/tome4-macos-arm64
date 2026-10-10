"""Shared paths and the pinned official source release."""
import hashlib
import json
import plistlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECT = json.loads((ROOT / "project.json").read_text())
VERSION = PROJECT["version"]
SOURCE = ROOT / PROJECT["source_directory"]
ARCHIVE = ROOT / "downloads" / PROJECT["source_archive"]
APP = ROOT / "dist" / "Tales of Maj'Eyal.app"
SPLIT = ROOT / "dist" / "Tales of Maj'Eyal"
APPS = {"bundled": APP, "split": SPLIT / "T-Engine.app"}
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)


def game_resources(app):
    with (app / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    return app.parent if info["TE4AssetLayout"] == "split" else app / "Contents/Resources"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_source_archive(path=ARCHIVE):
    actual = sha256(path)
    if actual != PROJECT["source_sha256"]:
        raise RuntimeError(f"Official source checksum mismatch: {path}: {actual}")

