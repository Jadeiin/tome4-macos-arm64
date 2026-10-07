#!/usr/bin/env python3
"""Check pinned source checksums and release tag validation."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from project import PROJECT, ROOT, VERSION, verify_source_archive


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


release = module("make_release", "make-release.py")


class ReleaseToolsCheck(unittest.TestCase):
    def test_source_checksum(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(PROJECT, source_sha256=
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"):
            archive = Path(directory) / "source.tar.bz2"
            archive.write_bytes(b"abc")
            verify_source_archive(archive)
            archive.write_bytes(b"abd")
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                verify_source_archive(archive)

    def test_release_tag_version_and_shell_input(self):
        release.validate_tag(f"v{VERSION}-arm64.1")
        for tag in ["v0.0.0-arm64.1", f"v{VERSION}-arm64.0", f"v{VERSION};echo secret", "main"]:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.validate_tag(tag)



if __name__ == "__main__":
    unittest.main(verbosity=2)
