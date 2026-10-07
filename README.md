# Tales of Maj’Eyal — Native Apple Silicon Build

English | [简体中文](README.zh-CN.md)

A community ARM64 macOS build of ToME **1.7.6**, using the complete official source and resources with LuaJIT 2.1, the SDL2/SDL3 compatibility layer, and OpenAL Soft.
The game and all bundled dynamic libraries are ARM64. Homebrew and Rosetta are not required to run it.

## Download and install

Download the `.dmg` from this repository’s [Releases](https://github.com/Jadeiin/tome4-macos-arm64/releases), open it, and drag `Tales of Maj’Eyal.app` to Applications.
See the release notes and `build-info.json` for the minimum macOS version. CI uses an ARM64 `macos-15` runner, and packaging checks the macOS versions required by the bundled libraries.

The app is ad hoc signed and is not notarized by Apple. If macOS blocks it, verify the download source and allow it to open under System Settings → Privacy & Security.
Public builds include the base game. Purchased DLC can be imported locally.

Fullscreen opens a native macOS Space without changing the monitor’s resolution or minimizing the game during app switching. Game Mode can activate on supported macOS versions. On a 2× Retina display, set Screen Zoom to 200% for the usual interface size.

## Build from source

You need an Apple Silicon Mac, Apple Command Line Tools, and native Homebrew.
Run these commands from the repository directory:

```sh
/opt/homebrew/bin/brew bundle install --file=Brewfile --no-upgrade
/usr/bin/python3 scripts/fetch-source.py
/usr/bin/python3 scripts/build-native.py
/usr/bin/python3 scripts/package-native.py
/usr/bin/python3 scripts/verify-native.py
/usr/bin/python3 scripts/check-bundled-runtime.py
open "dist/Tales of Maj'Eyal.app"
```

`project.json` pins the official source version, download URL, and SHA-256. The downloader verifies the complete archive before extracting it; if the source directory already exists, it preserves the directory and exits.
For subsequent builds with existing sources, start with `build-native.py`.

The Brewfile declares nine direct dependencies: `pkgconf`, `sdl2-compat`, `sdl2_image`, `sdl2_ttf`, `libpng`, `libogg`, `libvorbis`, `openal-soft`, and `luajit`. Homebrew installs their transitive dependencies.
OpenAL Soft is keg-only; the build script sets its pkg-config path.
The deployment target defaults to the build host’s macOS version. Set `TOME_MACOS_MIN` to choose the engine’s target, but the app’s final minimum version cannot be lower than the requirements of its bundled libraries.

Packaging copies runtime libraries other than system libraries into `Contents/Frameworks`, rewrites their paths to relative references, and signs the app again. SDL3, which SDL2 loads dynamically, is also bundled.
The library manifest and provenance are recorded in `Contents/Resources/runtime-libraries.json`; license files and Homebrew formula metadata are in `ThirdPartyLicenses`.
`Info.plist` declares the role-playing game category and Game Mode support. `--build-version` sets a numeric native bundle revision independently of the game version; CI uses its run number.
macOS provides system libraries and frameworks. Repackaging after a Homebrew update uses the versions currently installed; the Brewfile does not pin versions.

## Native compatibility code

Version control tracks:

- `scripts/build-native.py`: native builds with Apple Clang, excluding the old Lua runtime, Steam integration, and legacy embedded browser.
- `scripts/NativeMain.m`: Cocoa startup, app resource directory handling, and native macOS fullscreen Spaces. See the [fullscreen and Game Mode notes](docs/macos-native-fullscreen.md).
- `scripts/native-display.lua`: retains the upstream Fullscreen / Borderless / Windowed controls. Windowed and Borderless use the complete upstream resolution list and restart handling; native fullscreen shows the desktop rendering size. Retina rendering keeps window and mouse coordinates consistent.
- `scripts/NativeLua.c`: loading through the PhysFS virtual filesystem, the original `table.sort(list, "field")` extension, and the original `math.mod` / `string.gfind` aliases. See the [runtime compatibility audit](docs/luajit-runtime.md).
- `scripts/lua51-resolvers.lua`: runs instant resolvers that can be handled at the current stage first, avoiding unresolved inscription dependencies. The filename comes from the original diagnostic version; the current runtime uses LuaJIT.
- `scripts/patch-native.py` and `patches/native-arm64.patch`: the canonical upstream patch and its repeatable installer. The installer restores cached upstream originals before applying the patch and copies the Lua helpers.
- Packaging, verification, and release scripts, the Brewfile, source metadata, and GitHub Actions.

Official downloads, extracted sources, build caches, apps, logs, DLC, settings, and saves are excluded from Git.
The build script applies patches after source extraction; official game and DLC archives remain unchanged.
This build uses ARM64 LuaJIT 2.1 and does not convert saves containing old Lua 5.1 bytecode.

## Checks

Checks that do not open a game window:

```sh
/usr/bin/python3 scripts/check-release-tools.py
/usr/bin/python3 scripts/check-luajit-vfs.py
/usr/bin/python3 scripts/check-lua51-resolvers.py
/usr/bin/python3 scripts/check-talent-coroutines.py
/usr/bin/python3 scripts/verify-native.py
/usr/bin/python3 scripts/check-bundled-runtime.py
```

These cover source archive and release file validation, virtual filesystem loading, inscription resolution, coroutine suspension and cleanup in actual talent code, app architecture, dynamic linking, signing, and library loading after relocating the app.
Run the full game check from a local terminal or macOS runner with a graphical session:

```sh
/usr/bin/python3 scripts/check-first-floor.py --talents
```

It uses an isolated profile to create a Dwarf Bulwark, enter the first floor, generate 100 inscriptions, and cancel and complete Shield Pummel targeting, then closes the test game.
If the app includes DLC, the check also verifies that its modules load. Add `--require-dlcs` to require all three purchased DLC packs: Ashes of Urh’Rok, Embers of Rage, and Forbidden Cults.
Check results are saved in `logs/`. Default settings and saves are under `~/Library/Application Support/T-Engine/4.0/`; isolated test profiles are under `build/`.
These checks do not cover a full campaign or long sessions.

## GitHub Actions and releases

The [workflow](.github/workflows/build.yml) runs on updates to `main`, pull requests, manual dispatch, and pushes of `v*` tags:

1. Install Homebrew dependencies on a native ARM64 `macos-15` runner.
2. Download and verify the complete official sources, apply patches, and compile.
3. Run LuaJIT regression checks, architecture and signature checks, library loading checks after relocation, and the actual first floor and talent targeting checks.
4. Create and verify a DMG with `hdiutil`, accompanied by a source archive, build information, and SHA-256 checksums.
5. For `v1.7.6-arm64.N` tags, verify file checksums in a separate release job, then publish a release in a single `run` step using the runner’s bundled **GitHub CLI**.

Branch and pull request builds provide Actions artifacts; successful tag builds publish releases.
Public packaging explicitly excludes locally purchased DLC. CI game checks use OpenAL Soft’s null audio backend, so they do not depend on the runner’s audio hardware.
The release source archive contains the build code from the corresponding commit and the complete official source archive verified against its SHA-256.
Build and test logs are uploaded even on failure. The build job has only `contents: read`; the release job receives `contents: write`.

### Publish a new version

Push a new version tag to build and publish it automatically through GitHub Actions:

```sh
git tag v1.7.6-arm64.4
git push origin v1.7.6-arm64.4
```

Build progress and logs are available on the repository’s Actions page; published files are on the Releases page.

### Create release files locally

Complete the build and checks above, then run:

```sh
/usr/bin/python3 scripts/package-native.py --without-dlcs
/usr/bin/python3 scripts/make-release.py --tag v1.7.6-arm64.4
```

Output is written to `dist/release/`. Rebuilding the same version replaces its generated files.
Regular local builds retain imported DLC; public DMG packaging rejects apps containing DLC files.

## Import purchased DLC

```sh
/usr/bin/python3 scripts/import-dlcs.py "/path/to/SteamLibrary/steamapps/common/TalesMajEyal/game/dlcs"
/usr/bin/python3 scripts/package-native.py
```

DLC archives come from your own Steam installation; their integrity is checked before copying them locally. Class and race unlocks still follow the game’s rules.

## Sources and licenses

Official game and source: <https://te4.org/>. Official download URLs and hashes are recorded in `project.json`.
The engine and this repository’s native compatibility code are licensed under GPL-3.0; see [LICENSE](LICENSE). Media is covered by the upstream `COPYING-MEDIA` and is for use only with Tales of Maj’Eyal.
The app retains upstream licenses and credits, along with license and provenance information for third-party runtime libraries. This is a community build, separate from the official distribution.
