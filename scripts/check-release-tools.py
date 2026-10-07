#!/usr/bin/env python3
"""Check archive traversal rejection and release tag validation."""
import importlib.util
import tarfile
import unittest
from pathlib import Path

from project import PROJECT, ROOT, VERSION


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


fetch = module("fetch_source", "fetch-source.py")
release = module("make_release", "make-release.py")


class ReleaseToolsCheck(unittest.TestCase):
    def test_archive_paths_and_types(self):
        safe = tarfile.TarInfo(PROJECT["source_directory"] + "/src/main.c")
        fetch.validate_members([safe])
        for name in ["/etc/passwd", PROJECT["source_directory"] + "/../outside", "another-release/src/main.c"]:
            with self.subTest(name=name), self.assertRaises(RuntimeError):
                fetch.validate_members([tarfile.TarInfo(name)])
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE]:
            linked = tarfile.TarInfo(PROJECT["source_directory"] + "/escape")
            linked.type = kind
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                fetch.validate_members([linked])

    def test_release_tag_version_and_shell_input(self):
        release.validate_tag(f"v{VERSION}-arm64.1")
        for tag in ["v0.0.0-arm64.1", f"v{VERSION}-arm64.0", f"v{VERSION};echo secret", "main"]:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.validate_tag(tag)



if __name__ == "__main__":
    unittest.main(verbosity=2)
