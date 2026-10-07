#!/usr/bin/env python3
"""Copy native non-system libraries into the app and rewrite their load paths."""
import json
import shutil
import subprocess
from pathlib import Path

from macho import inspect, resolve, system_library

from project import APP, LOGS, ROOT
EXECUTABLE = APP / "Contents/MacOS/t-engine"
FRAMEWORKS = APP / "Contents/Frameworks"
STAGING = APP / "Contents/Frameworks.new"
LICENSES = APP / "Contents/Resources/ThirdPartyLicenses"
SDL3 = Path("/opt/homebrew/opt/sdl3/lib/libSDL3.dylib").resolve()

# Read the original link graph even when this helper is repeated on a bundled app.
executable = (ROOT / "build/native/t-engine").resolve()
queue = [executable, SDL3]
graph = {}
while queue:
    binary = queue.pop()
    if binary in graph:
        continue
    info = inspect(binary)
    edges = {}
    for name in info["dependencies"]:
        if system_library(name):
            continue
        dependency = resolve(name, binary, executable, info["rpaths"], homebrew=True)
        edges[name] = dependency
        queue.append(dependency)
    graph[binary] = {**info, "edges": edges}

names = {}
occupied = {}
for binary, info in graph.items():
    if binary == executable:
        continue
    name = Path(info["id"]).name
    if name in occupied and occupied[name] != binary:
        raise RuntimeError(f"Library filename collision: {name}")
    occupied[name] = binary
    names[binary] = name

if STAGING.exists():
    shutil.rmtree(STAGING)
STAGING.mkdir()
if LICENSES.exists():
    shutil.rmtree(LICENSES)
LICENSES.mkdir(parents=True)
formulae = {}
records = []
for binary, name in names.items():
    destination = STAGING / name
    architectures = subprocess.check_output(["/usr/bin/lipo", "-archs", str(binary)], text=True).split()
    if architectures == ["arm64"]:
        shutil.copy2(binary, destination)
    else:
        subprocess.run(["/usr/bin/lipo", str(binary), "-thin", "arm64", "-output", str(destination)], check=True)
    command = ["/usr/bin/install_name_tool", "-id", f"@rpath/{name}"]
    for original, dependency in graph[binary]["edges"].items():
        command.extend(["-change", original, f"@loader_path/{names[dependency]}"])
    for rpath in graph[binary]["rpaths"]:
        if rpath.startswith("/") and not system_library(rpath):
            command.extend(["-delete_rpath", rpath])
    subprocess.run([*command, str(destination)], check=True, capture_output=True)
    subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(destination)],
                   check=True, capture_output=True)
    records.append({"name": name, "source": str(binary), "bytes": destination.stat().st_size,
                    "minimum_macos": graph[binary]["minimum_macos"]})
    cellar = Path("/opt/homebrew/Cellar")
    if binary.is_relative_to(cellar):
        relative = binary.relative_to(cellar)
        formula = relative.parts[0]
        prefix = cellar / formula / relative.parts[1]
        formulae[formula] = prefix

# sdl2-compat dlopens this name relative to its own library rather than
# declaring SDL3 with LC_LOAD_DYLIB. Keep the alias in the same directory.
sdl3_name = names[SDL3]
if sdl3_name != "libSDL3.dylib":
    (STAGING / "libSDL3.dylib").symlink_to(sdl3_name)

license_records = []
for formula, prefix in sorted(formulae.items()):
    copied = []
    for path in sorted(prefix.rglob("*")):
        if not path.is_file():
            continue
        if not path.name.lower().startswith(("license", "licence", "copying", "copyright", "notice")):
            continue
        relative = path.relative_to(prefix)
        destination = LICENSES / formula / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied.append(str(relative))
    formula_file = prefix / ".brew" / f"{formula}.rb"
    destination = LICENSES / formula / "homebrew-formula.rb"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(formula_file, destination)
    license_records.append({"formula": formula, "version": prefix.name, "license_files": copied})

if FRAMEWORKS.exists():
    shutil.rmtree(FRAMEWORKS)
STAGING.replace(FRAMEWORKS)
command = ["/usr/bin/install_name_tool"]
for original, dependency in graph[executable]["edges"].items():
    command.extend(["-change", original, f"@executable_path/../Frameworks/{names[dependency]}"])
for rpath in graph[executable]["rpaths"]:
    if rpath.startswith("/") and not system_library(rpath):
        command.extend(["-delete_rpath", rpath])
subprocess.run([*command, str(EXECUTABLE)], check=True, capture_output=True)
manifest = {"runtime_libraries": sorted(records, key=lambda item: item["name"]),
            "sdl3_alias": "libSDL3.dylib", "licenses": license_records,
            "runtime_requires_homebrew": False,
            "total_library_bytes": sum(record["bytes"] for record in records)}
(APP / "Contents/Resources/runtime-libraries.json").write_text(json.dumps(manifest, indent=2) + "\n")
(ROOT / "logs/bundled-runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Bundled {len(records)} libraries ({manifest['total_library_bytes'] / 1024**2:.1f} MiB), including SDL3 and license records.")
