#!/usr/bin/env python3
"""Download, verify and extract the official full source release."""
import argparse
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from project import ARCHIVE, PROJECT, ROOT, SOURCE, verify_source_archive


def validate_members(members):
    prefix = PROJECT["source_directory"]
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != prefix:
            raise RuntimeError(f"Unsafe archive path: {member.name}")
        if not (member.isfile() or member.isdir()):
            # The pinned official archive does not need links or special files.
            raise RuntimeError(f"Unexpected archive member type: {member.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE, help="Use an already downloaded archive")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--destination", type=Path, default=SOURCE)
    args = parser.parse_args()
    archive = args.archive.resolve()
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        partial = archive.with_suffix(archive.suffix + ".part")
        subprocess.run(["curl", "--fail", "--location", "--retry", "5", "--retry-all-errors",
                        "--connect-timeout", "20", "--output", str(partial), PROJECT["source_url"]], check=True)
        verify_source_archive(partial)
        partial.replace(archive)
    verify_source_archive(archive)
    print(f"Verified official source SHA-256: {archive}", flush=True)
    if args.verify_only:
        return
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit(f"Source directory already exists; kept unchanged: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="source-extract-", dir=destination.parent) as temporary:
        with tarfile.open(archive, "r|bz2") as source:
            for member in source:
                validate_members([member])
                source.extract(member, temporary)
        shutil.move(str(Path(temporary) / PROJECT["source_directory"]), str(destination))
    print(f"Extracted source: {destination}")


if __name__ == "__main__":
    main()
