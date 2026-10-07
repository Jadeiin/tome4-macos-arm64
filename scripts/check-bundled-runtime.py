#!/usr/bin/env python3
"""Load every bundled dylib and exercise SDL/LuaJIT before and after relocation."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from project import APP, LOGS, ROOT
FRAMEWORKS = APP / "Contents/Frameworks"
BUILD = ROOT / "build/native/checks"
BUILD.mkdir(parents=True, exist_ok=True)
manifest = json.loads((APP / "Contents/Resources/runtime-libraries.json").read_text())
names = [record["name"] for record in manifest["runtime_libraries"]]
runner = BUILD / "bundled-runtime"
subprocess.run(["/usr/bin/clang", "-arch", "arm64", str(ROOT / "scripts/check-bundled-runtime.c"),
                "-o", str(runner)], check=True)
reports = []
outputs = []


def check(label, executable, directory):
    result = subprocess.run([str(executable), str(directory), *names], text=True, capture_output=True)
    outputs.append(label + "\n" + result.stdout + result.stderr)
    (ROOT / "logs/bundled-runtime-check.log").write_text("\n".join(outputs))
    if result.returncode:
        print(result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    images = [Path(line.split("\t", 1)[1]).resolve()
              for line in result.stdout.splitlines() if line.startswith("IMAGE\t")]
    external = [str(path) for path in images if path != executable.resolve()
                and not str(path).startswith(("/System/", "/usr/lib/"))
                and not path.is_relative_to(directory.resolve())]
    bundled = sorted({path.name for path in images if path.is_relative_to(directory.resolve())})
    if external or set(bundled) != set(names):
        raise RuntimeError(f"Runtime escaped the bundle or libraries are missing: {external}; {set(names) - set(bundled)}")
    reports.append({"label": label, "loaded_bundled_libraries": bundled,
                    "external_non_system_images": external, "sdl3_backend": True,
                    "arm64_jit_trace": True, "passed": True})
    print(f"{label}: loaded all {len(bundled)} bundled libraries; SDL3 and ARM64 JIT passed.")


check("original location", runner, FRAMEWORKS)
with tempfile.TemporaryDirectory(prefix="bundle-relocated-", dir=ROOT / "build") as temporary:
    contents = Path(temporary) / "Runtime Check.app/Contents"
    moved = contents / "Frameworks"
    shutil.copytree(FRAMEWORKS, moved, symlinks=True)
    binary = contents / "MacOS/runtime-check"
    binary.parent.mkdir()
    shutil.copy2(runner, binary)
    check("relocated bundle", binary, moved)
report = {"checks": reports, "temporary_bundle_cleaned": True, "passed": all(item["passed"] for item in reports)}
(ROOT / "logs/bundled-runtime-check.json").write_text(json.dumps(report, indent=2) + "\n")
