#!/usr/bin/env python3
"""Create a DLC-free DMG, corresponding project sources and release checksums."""
import argparse
import io
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from project import APP, ARCHIVE, LOGS, PROJECT, ROOT, VERSION, sha256, verify_source_archive


def validate_tag(tag):
    if not re.fullmatch(r"v" + re.escape(VERSION) + r"-arm64\.[1-9][0-9]*", tag):
        raise ValueError(f"Release tag must be v{VERSION}-arm64.N (N >= 1): {tag}")
    return tag


def make_sources(destination, commit, stem):
    verify_source_archive()
    snapshot = subprocess.check_output(["git", "archive", "--format=tar", f"--prefix={stem}/", commit], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(snapshot), mode="r:") as files, tarfile.open(destination, "w:gz", compresslevel=1) as output:
        for member in files:
            output.addfile(member, files.extractfile(member) if member.isfile() else None)
        output.add(ARCHIVE, arcname=f"{stem}/downloads/{PROJECT['source_archive']}", recursive=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help=f"Public release tag, e.g. v{VERSION}-arm64.1")
    args = parser.parse_args()
    if platform.machine() != "arm64" or platform.system() != "Darwin":
        parser.error("Create the DMG on native ARM64 macOS.")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    tag = args.tag
    if not tag and os.environ.get("GITHUB_REF", "").startswith("refs/tags/"):
        tag = os.environ["GITHUB_REF"][len("refs/tags/"):]
    build_id = validate_tag(tag) if tag else f"v{VERSION}-arm64-dev-{commit[:12]}"
    dlcs = APP / "Contents/Resources/game/dlcs"
    if any(path.is_file() for path in dlcs.rglob("*")):
        raise RuntimeError("Public DMGs must use package-native.py --without-dlcs.")
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(APP)], check=True)
    with (APP / "Contents/Info.plist").open("rb") as stream:
        minimum_macos = plistlib.load(stream)["LSMinimumSystemVersion"]
    directory = ROOT / "dist/release"
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"Tales-of-MajEyal-{build_id.removeprefix('v')}"
    dmg = directory / f"{stem}.dmg"
    with tempfile.TemporaryDirectory(prefix="dmg-stage-", dir=ROOT / "build") as temporary:
        stage = Path(temporary)
        subprocess.run(["/usr/bin/ditto", str(APP), str(stage / APP.name)], check=True)
        (stage / "Applications").symlink_to("/Applications")
        (stage / "Install.txt").write_text(
            f"Tales of Maj'Eyal {VERSION} — native Apple Silicon\n\n"
            f"Requires macOS {minimum_macos} or newer. Drag the app to Applications.\n"
            "Runtime libraries are bundled; Homebrew and Rosetta are not required.\n"
            "This community build uses ad hoc signing and is not notarized.\n"
            "Paid DLCs are not included. See the repository README for local import.\n")
        subprocess.run(["/usr/bin/hdiutil", "create", "-ov", "-volname", f"ToME {VERSION} ARM64",
                        "-srcfolder", str(stage), "-fs", "HFS+", "-format", "UDZO", str(dmg)], check=True)
    subprocess.run(["/usr/bin/hdiutil", "verify", str(dmg)], check=True)
    sources = directory / f"{stem}-source.tar.gz"
    make_sources(sources, commit, stem + "-source")
    runtime = json.loads((APP / "Contents/Resources/runtime-libraries.json").read_text())
    manifest = {"version": VERSION, "build_id": build_id, "commit": commit,
                "architecture": "arm64", "minimum_macos": minimum_macos,
                "runtime_requires_homebrew": False, "paid_dlcs_included": False,
                "signing": "ad hoc; not notarized", "upstream": PROJECT,
                "runtime_libraries": runtime}
    (directory / "build-info.json").write_text(json.dumps(manifest, indent=2) + "\n")
    files = [dmg, sources, directory / "build-info.json"]
    records = [(path.name, sha256(path)) for path in sorted(files)]
    (directory / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in records))
    (directory / "release-notes.md").write_text(
        f"Native Apple Silicon build of Tales of Maj'Eyal {VERSION}.\n\n"
        f"- Requires macOS **{minimum_macos}+**; ARM64 only.\n"
        "- Bundled LuaJIT 2.1, SDL and OpenAL Soft; no Homebrew or Rosetta needed.\n"
        "- Includes a DMG, corresponding project sources with the verified official source archive, and SHA-256 checksums.\n"
        "- CI verifies native links/signatures, relocated library loading, Lua compatibility, first-floor generation and skill targeting.\n"
        "- Paid DLCs are excluded. Signing is ad hoc; this build is not notarized.\n\n"
        f"Build commit: `{commit}`.\n")
    (LOGS / "release-build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Release files: {directory}")


if __name__ == "__main__":
    main()
