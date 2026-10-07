#!/usr/bin/env python3
"""Build ToME with Apple Clang and ARM Homebrew dependencies, without premake."""
import os
import json
import platform
import shlex
import subprocess
import sys
from pathlib import Path

from project import ROOT, SOURCE, VERSION
BUILD = ROOT / "build" / "native"
PKG_CONFIG = Path("/opt/homebrew/bin/pkg-config")
PACKAGES = ["sdl2", "SDL2_image", "SDL2_ttf", "vorbisfile", "libpng", "openal", "luajit"]

if platform.machine() != "arm64":
    sys.exit("Run this script from an ARM64 terminal. Rosetta is not supported.")
if not PKG_CONFIG.exists():
    sys.exit("Install Homebrew dependencies listed in README.md first.")
openal_pc = Path("/opt/homebrew/opt/openal-soft/lib/pkgconfig/openal.pc")
if not openal_pc.exists():
    sys.exit("Install the ARM64 audio dependency: /opt/homebrew/bin/brew install openal-soft")
if not Path("/opt/homebrew/opt/luajit/lib/pkgconfig/luajit.pc").exists():
    sys.exit("Install the ARM64 Lua runtime: /opt/homebrew/bin/brew install luajit")
# Homebrew keeps OpenAL Soft keg-only because macOS supplies OpenAL.framework.
pkg_environment = dict(os.environ)
pkg_environment["PKG_CONFIG_PATH"] = str(openal_pc.parent) + os.pathsep + os.environ.get("PKG_CONFIG_PATH", "")
subprocess.run([sys.executable, str(ROOT / "scripts/patch-native.py")], check=True)
BUILD.mkdir(parents=True, exist_ok=True)
sdk = subprocess.check_output(["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True).strip()
deployment = os.environ.get("TOME_MACOS_MIN", ".".join(platform.mac_ver()[0].split('.')[:2]))
external_cflags = shlex.split(subprocess.check_output(
    [str(PKG_CONFIG), "--cflags", *PACKAGES], text=True, env=pkg_environment))
external_libs = shlex.split(subprocess.check_output(
    [str(PKG_CONFIG), "--libs", *PACKAGES], text=True, env=pkg_environment))
external_libs = [flag for flag in external_libs if flag != "-lSDL2main"]
includes = ["src", "src/luasocket", "src/fov", "src/expat",
            "src/lxp", "src/libtcod_import", "src/physfs", "src/zlib", "src/bzip2"]
flags = ["-arch", "arm64", "-isysroot", sdk, f"-mmacosx-version-min={deployment}",
         "-O2", "-g", "-fno-strict-aliasing", "-Wno-deprecated-declarations",
         "-Wno-deprecated-non-prototype", "-DGLEW_STATIC", "-DNDEBUG=1",
         "-DPHYSFS_SUPPORTS_ZIP", "-DHAVE_MEMMOVE", "-DHAVE_UNISTD_H=1", "-DTE4CORE_VERSION=17",
         "-DTE4_NATIVE_MACOS", "-DSELFEXE_MACOSX", "-DUSE_TENGINE_MAIN",
         "-DSDL_MAIN_HANDLED", '-DTENGINE_HOME_PATH="/Library/Application Support/T-Engine/"',
         "-DluaL_loadfile=te4_physfs_loadfile",
         "-D_DEFAULT_VIDEOMODE_FLAGS_=SDL_HWSURFACE|SDL_DOUBLEBUF"]
flags += [f"-I{ROOT / 'scripts'}"] + [f"-I{SOURCE / relative}" for relative in includes] + external_cflags

sources = list((SOURCE / "src").glob("*.c"))
for directory in ["fov", "lpeg", "luaprofiler", "libtcod_import", "expat",
                  "lxp", "luamd5", "lzlib", "bzip2", "physfs", "zlib"]:
    sources += list((SOURCE / "src" / directory).glob("*.c"))
sources += list((SOURCE / "src/physfs/archivers").glob("*.c"))
sources += [SOURCE / f"src/physfs/platform/{name}.c" for name in ["unix", "posix"]]
sources += [SOURCE / "src/utf8proc/utf8proc.c"]
sources += list((SOURCE / "src/wfc").glob("*.cpp"))
sources += [SOURCE / f"src/luasocket/{name}.c" for name in
            ["buffer", "except", "inet", "io", "luasocket", "options",
             "select", "tcp", "timeout", "udp", "usocket", "mime"]]
sources += [ROOT / "scripts/NativeMain.m", ROOT / "scripts/NativeLua.c"]
sources = sorted(set(sources))
# The engine's src/auxiliar.c supplies LuaSocket's auxiliar functions too.
config = BUILD / "build-config.json"
config_text = json.dumps({"flags": flags, "libs": external_libs, "deployment": deployment}, indent=2)
if not config.exists() or config.read_text() != config_text:
    config.write_text(config_text)
objects = []
lines = [".DEFAULT_GOAL := all", ".DELETE_ON_ERROR:", ""]
for source in sources:
    relative = source.relative_to(ROOT)
    obj = BUILD / "obj" / relative.with_suffix(".o")
    obj.parent.mkdir(parents=True, exist_ok=True)
    objects.append(obj)
    compiler = "/usr/bin/clang++" if source.suffix == ".cpp" else "/usr/bin/clang"
    language = "-std=c++11" if source.suffix == ".cpp" else "-std=gnu99"
    command = [compiler, *flags, language, "-MMD", "-MP", "-c", str(source), "-o", str(obj)]
    lines += [f"{obj}: {source} {config}", f"\t{shlex.join(command)}", ""]
executable = BUILD / "t-engine"
link = ["/usr/bin/clang++", "-arch", "arm64", "-isysroot", sdk,
        f"-mmacosx-version-min={deployment}", "-Wl,-headerpad_max_install_names", "-o", str(executable)]
link += [str(obj) for obj in objects] + external_libs
link += ["-framework", "Cocoa", "-framework", "OpenGL", "-lm"]
lines += [f"all: {executable}", f"{executable}: " + " ".join(map(str, objects)),
          "\t" + shlex.join(link), "", "-include " + " ".join(str(obj.with_suffix('.d')) for obj in objects)]
(BUILD / "Makefile").write_text("\n".join(lines) + "\n")
print(f"Compiling {len(sources)} files for arm64 with Homebrew LuaJIT 2.1.", flush=True)
subprocess.run(["/usr/bin/make", "--no-print-directory", "-s", "-C", str(BUILD), f"-j{os.environ.get('TOME_BUILD_JOBS', '8')}"], check=True)
subprocess.run(["file", str(executable)], check=True)
