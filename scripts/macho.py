"""Read and resolve macOS library load commands for packaging and verification."""
import re
import subprocess
from pathlib import Path


def system_library(name):
    return name.startswith(("/System/", "/usr/lib/"))


def inspect(binary):
    links = subprocess.check_output(["/usr/bin/otool", "-arch", "arm64", "-L", str(binary)], text=True)
    commands = subprocess.check_output(["/usr/bin/otool", "-arch", "arm64", "-l", str(binary)], text=True)
    library_id = re.search(r"cmd LC_ID_DYLIB\s+cmdsize \d+\s+name (.*?) \(offset", commands)
    library_id = library_id.group(1) if library_id else None
    dependencies = [re.split(r"\s+\(compatibility", line.strip(), maxsplit=1)[0]
                    for line in links.splitlines()[1:]]
    minimums = re.findall(r"\bminos (\d+(?:\.\d+)*)", commands)
    minimums += re.findall(r"cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version (\d+(?:\.\d+)*)", commands)
    minimum = max(minimums, key=lambda value: tuple(int(part) for part in value.split('.'))) if minimums else None
    return {"id": library_id, "dependencies": [name for name in dependencies if name != library_id],
            "rpaths": re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset", commands),
            "minimum_macos": minimum}


def expand(path, binary, executable):
    return Path(path.replace("@loader_path", str(binary.parent))
                .replace("@executable_path", str(executable.parent)))


def resolve(name, binary, executable, rpaths=(), homebrew=False):
    if name.startswith("@rpath/"):
        suffix = name[len("@rpath/"):]
        candidates = [expand(path, binary, executable) / suffix for path in rpaths]
        candidates.append(binary.parent / suffix)
        if homebrew:
            candidates.append(Path("/opt/homebrew/lib") / suffix)
    else:
        candidates = [expand(name, binary, executable)]
    for candidate in candidates:
        if candidate.is_absolute() and candidate.exists():
            return candidate.resolve()
    raise RuntimeError(f"Cannot resolve {name} in {binary}")
