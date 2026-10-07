# LuaJIT runtime compatibility

The native build uses ARM64 LuaJIT 2.1.1788856981. An audit on October 8, 2026
compared its initialized APIs with ToME 1.7.6's bundled Lua 5.1 implementation.
The reference interpreter was compiled as a temporary ARM64 audit library.

## Scope

- 3,548 Lua files: the engine, base game, graphics, bootstrap, bundled addons,
  loose startup/third-party scripts, and the three locally purchased DLCs.
- Actual C initialization through `te4_native_lua_init`, plus archived game
  functions for combat effects, Cookie parsing and debugger path handling.
- 113 exported Lua/Lua auxiliary APIs from the original headers, checked against
  the current library and references in the 97 compiled engine source files.

The scan strips comments and strings before locating direct standard-library
references. Scripts were compiled with both interpreters; API availability and
selected behavior were compared in separate Lua states. This checks runtime
interfaces and parsing; it does not execute every gameplay branch.

## Corrections

| Finding | Correction |
| --- | --- |
| `math.mod` absent; four combat effects and LuaSocket FTP use it | Restore the original `math.fmod` alias in `NativeLua.c` |
| `string.gfind` absent; four remote-designer sites and RemDebug use it | Restore the original `string.gmatch` alias |
| RemDebug's `\/` string escape is rejected by current LuaJIT | Use `/`, preserving the original pattern's meaning |
| Shipped `jit.*` scripts are LuaJIT 2.0.2; loading diagnostic modules fails their version assertion | Package scripts from the same Homebrew LuaJIT installation as the linked library, including the ARM64 disassembler |

Packaging copies the matching `share/luajit-2.1/jit` files into
`Contents/Resources/game/thirdparty/jit`. The game's `jit.bcname` helper remains
available. Loading these files uses the game's existing PhysFS module searcher.
Official engine, game and DLC archives remain unchanged.

## Results

- Original combat probability functions passed with zero, fractional and full
  remaining charges. Signed and fractional modulo behavior matches the reference.
- Original Cookie parsing and Windows/Unix debugger path splitting passed.
- Field-key sorting, explicit varargs with nil values, `module`/`package.seeall`,
  table iteration and length behavior matched the reference in the checked cases.
- Function bytecode and quoted binary-string serialization round trips passed
  within each runtime. LuaJIT's yieldable protected calls remain enabled.
- All runtime scripts compiled after the RemDebug correction. The remote
  designer's Ace editor Lua demo has the same syntax error in both interpreters;
  it is editor sample content.
- The remaining absent standard-library API is `table.setn`, used by legacy
  RemDebug watch handling. Calling it already raises `'setn' is obsolete` in the
  original interpreter. It was not added to the native bridge.
- `lua_setlevel` is the only absent original C export found. None of the compiled
  engine sources calls it.
- `jit.v`, `jit.bc`, `jit.dump`, `jit.bcsave` and `jit.dis_arm64` loaded with the
  matching scripts. Bytecode output and ARM64 trace generation passed.
- The bundled runtime check passed at the original app location and after
  relocation, with all 34 runtime libraries loaded from inside the bundle.

Regression checks are in `scripts/check-luajit-vfs.py` and
`scripts/check-bundled-runtime.py`. Local audit evidence is stored in
`logs/runtime-audit*`, `logs/runtime-c-api-audit.json` and
`logs/bundled-runtime-check*`.
