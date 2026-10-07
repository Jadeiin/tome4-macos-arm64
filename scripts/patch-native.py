#!/usr/bin/env python3
"""Apply small, idempotent macOS ARM64 compatibility fixes to ToME 1.7.6."""
import difflib
from pathlib import Path

from project import ROOT, SOURCE, VERSION
ORIGINALS = ROOT / "patches" / "upstream"
patches = []


def replace(relative, old, new):
    path = SOURCE / relative
    original = path.read_text()
    if new in original and (old not in original or old in new):
        return
    if old not in original:
        if new in original:
            return
        raise RuntimeError(f"Expected source text missing: {relative}")
    modified = original.replace(old, new, 1)
    upstream = ORIGINALS / relative
    if not upstream.exists():
        upstream.parent.mkdir(parents=True, exist_ok=True)
        upstream.write_text(original)
    path.write_text(modified)
    patches.extend(difflib.unified_diff(
        original.splitlines(True), modified.splitlines(True),
        fromfile=f"a/{relative}", tofile=f"b/{relative}"))


replace("src/tSDL.h", "#include <SDL2_ttf/SDL_ttf.h>", "#include <SDL2/SDL_ttf.h>")
replace("src/tSDL.h", "#include <SDL2_image/SDL_image.h>", "#include <SDL2/SDL_image.h>")
replace("src/music.h", "#include <OpenAL/al.h>\n#include <OpenAL/alc.h>",
        "#include <AL/al.h>\n#include <AL/alc.h>")
replace("src/music.c", "\talDistanceModel(AL_NONE);\n\treturn 1;",
        "\talDistanceModel(AL_NONE);\n"
        "\tprintf(\"OpenAL vendor: %s; renderer: %s; version: %s\\n\",\n"
        "\t\talGetString(AL_VENDOR), alGetString(AL_RENDERER), alGetString(AL_VERSION));\n"
        "\treturn 1;")
replace("src/core_lua.c", "#include <libpng/png.h>", "#include <png.h>")
replace("src/lpeg/lptypes.h", '#include "lua.h"', '#include <limits.h>\n#include "lua.h"')
replace("src/lxp/lxplib.c", "lua_unref(L, xpu->tableref);", "luaL_unref(L, LUA_REGISTRYINDEX, xpu->tableref);")
replace("src/lxp/lxplib.c", "lua_getref(L, xpu->tableref);  /* child uses the same table of its father */",
        "lua_rawgeti(L, LUA_REGISTRYINDEX, xpu->tableref);  /* child uses the same table of its father */")
replace("src/lxp/lxplib.c", "lua_getref(L, xpu->tableref);  /* to be used by handlers */",
        "lua_rawgeti(L, LUA_REGISTRYINDEX, xpu->tableref);  /* to be used by handlers */")
replace("src/lxp/lxplib.c", "static const struct luaL_reg lxp_meths[]", "static const luaL_Reg lxp_meths[]")
replace("src/lxp/lxplib.c", "static const struct luaL_reg lxp_funcs[]", "static const luaL_Reg lxp_funcs[]")
replace("src/lua/lstrlib.c", "static int str_format (lua_State *L) {",
        "/* Match LuaJIT's %s conversion, which ToME uses during character creation. */\n"
        "static const char *format_tostring (lua_State *L, int arg, size_t *len) {\n"
        "  if (lua_type(L, arg) == LUA_TSTRING)\n"
        "    return lua_tolstring(L, arg, len);\n"
        "  if (luaL_callmeta(L, arg, \"__tostring\"))\n"
        "    lua_replace(L, arg);\n"
        "  switch (lua_type(L, arg)) {\n"
        "    case LUA_TNUMBER: case LUA_TSTRING:\n"
        "      return lua_tolstring(L, arg, len);\n"
        "    case LUA_TNIL:\n"
        "      lua_pushliteral(L, \"nil\");\n"
        "      break;\n"
        "    case LUA_TBOOLEAN:\n"
        "      lua_pushstring(L, lua_toboolean(L, arg) ? \"true\" : \"false\");\n"
        "      break;\n"
        "    default:\n"
        "      lua_pushfstring(L, \"%s: %p\", luaL_typename(L, arg), lua_topointer(L, arg));\n"
        "      break;\n"
        "  }\n"
        "  lua_replace(L, arg);\n"
        "  return lua_tolstring(L, arg, len);\n"
        "}\n\n"
        "static int str_format (lua_State *L) {")
replace("src/lua/lstrlib.c", "        case 's': {\n          size_t l;\n          const char *s = luaL_checklstring(L, arg, &l);",
        "        case 's': {\n          size_t l;\n          const char *s = format_tostring(L, arg, &l);")
replace("src/zlib/zutil.h", "#if defined(MACOS) || defined(TARGET_OS_MAC)",
        "#if (defined(MACOS) || defined(TARGET_OS_MAC)) && !defined(__APPLE__)")
replace("src/main.c", "\t\tif (os_autoflush) setlinebuf(logfile);", "\t\tif (logfile) setlinebuf(logfile);")
replace("src/main.c", "/* @see main.h#do_resize */",
        "/* OpenGL windows cannot also have an SDL software window surface.\n"
        " * The legacy screen object is only used for dimensions and pixel format. */\n"
        "static void updateScreenInfo(void)\n"
        "{\n"
        "\tint width, height;\n"
        "\tSDL_GetWindowSize(window, &width, &height);\n"
        "\tSDL_FreeSurface(screen);\n"
        "\tscreen = SDL_CreateRGBSurface(0, width, height, 32, 0, 0, 0, 0);\n"
        "\tif (!screen) { fprintf(stderr, \"Screen allocation failed: %s\\n\", SDL_GetError()); exit(1); }\n"
        "}\n\n"
        "/* @see main.h#do_resize */")
replace("src/main.c", "\t\twindow = 0;\n\t\tscreen = 0;",
        "\t\twindow = 0;\n\t\tSDL_FreeSurface(screen);\n\t\tscreen = 0;")
replace("src/main.c", "\t\tscreen = SDL_GetWindowSurface(window);\n\t\tmaincontext = SDL_GL_CreateContext(window);\n\t\tSDL_GL_MakeCurrent(window, maincontext);\n\t\tglewInit();",
        "\t\tupdateScreenInfo();\n"
        "\t\tmaincontext = SDL_GL_CreateContext(window);\n"
        "\t\tif (!maincontext || SDL_GL_MakeCurrent(window, maincontext) != 0) {\n"
        "\t\t\tfprintf(stderr, \"OpenGL context creation failed: %s\\n\", SDL_GetError());\n"
        "\t\t\texit(1);\n"
        "\t\t}\n"
        "\t\tGLenum glew_status = glewInit();\n"
        "\t\tif (glew_status != GLEW_OK) {\n"
        "\t\t\tfprintf(stderr, \"GLEW initialization failed: %s\\n\", glewGetErrorString(glew_status));\n"
        "\t\t\texit(1);\n"
        "\t\t}")
replace("src/main.c", "\t\t/* Finally, update the screen info */\n\t\tscreen = SDL_GetWindowSurface(window);",
        "\t\t/* Finally, update the screen info */\n\t\tupdateScreenInfo();")
replace("src/main.c", "#ifdef SELFEXE_MACOSX\n\tfclose(stdout);\n#endif\n}",
        "#ifdef SELFEXE_MACOSX\n\tfclose(stdout);\n#endif\n\treturn 0;\n}")
replace("src/particles.c", '#include "types.h"', '#include "types.h"\n#include "lua_externs.h"')
replace("src/physfs/archivers/bind_physfs.c", "void *(*openFunc)(const char *filename)",
        "PHYSFS_File *(*openFunc)(const char *filename)")
replace("src/getself.c", "#include \"getself.h\"", "#include \"getself.h\"\n#include <stdlib.h>\n#include <stdint.h>")
replace("src/physfs/physfs_platforms.h", "#if (defined __HAIKU__)",
        "#if defined(TE4_NATIVE_MACOS)\n"
        "/* Use the existing POSIX implementation instead of obsolete Carbon APIs. */\n"
        "#  define PHYSFS_PLATFORM_UNIX\n"
        "#  define PHYSFS_PLATFORM_POSIX\n"
        "#  define PHYSFS_NO_CDROM_SUPPORT\n"
        "#elif (defined __HAIKU__)")
replace("src/getself.c", "\tsize_t sz = 0;", "\tuint32_t sz = 0;")
replace("src/getself.c", "\t*(sl + 1) = '\\0';\n\treturn buf;",
        "\tif (!sl) { free(buf); return NULL; }\n"
        "\t*(sl + 1) = '\\0';\n"
        "\t/* Keep the complete game inside the application bundle. */\n"
        "\tconst char *suffix = \"/Contents/MacOS/\";\n"
        "\tsize_t len = strlen(buf), suffix_len = strlen(suffix);\n"
        "\tif (len >= suffix_len && !strcmp(buf + len - suffix_len, suffix)) {\n"
        "\t\tchar *resources = realloc(buf, len + 5);\n"
        "\t\tif (!resources) { free(buf); return NULL; }\n"
        "\t\tbuf = resources;\n"
        "\t\tstrcpy(buf + len - suffix_len, \"/Contents/Resources/\");\n"
        "\t}\n"
        "\treturn buf;")
replace("bootstrap/boot.lua",
        '\t\tdir = dir:gsub("(.*"..fs.getPathSeparator()..").+", "%1"):gsub("(.*"..fs.getPathSeparator()..").+", "%1"):gsub("(.*"..fs.getPathSeparator()..").+", "%1")',
        "\t\t-- The native macOS core already returns Contents/Resources/.\n"
        "\t\tdir = dir")

# Apply the Lua 5.1 fix while loading Entity, before subclasses copy its methods.
# Official engine/module/DLC archives stay byte-for-byte unchanged.
if '\tif bname == "engine.Entity" and not jit then' in (SOURCE / "game/loader/init.lua").read_text():
    replace("game/loader/init.lua", '\tif bname == "engine.Entity" and not jit then',
            '\tif bname == "engine.Entity" then')
replace("game/loader/init.lua", "\treturn prev\nend\n\ntable.insert(package.loaders, 2, te4_loader)",
        "\tif bname == \"engine.Entity\" then\n"
        "\t\tlocal original = prev\n"
        "\t\tprev = function(...)\n"
        "\t\t\tlocal result = original(...)\n"
        "\t\t\tlocal install, err = loadfile(\"/loader/native-lua51.lua\")\n"
        "\t\t\tassert(install, err)\n"
        "\t\t\tinstall()(package.loaded[bname])\n"
        "\t\t\treturn result\n"
        "\t\tend\n"
        "\tend\n"
        "\treturn prev\nend\n\ntable.insert(package.loaders, 2, te4_loader)")
native_lua_relative = Path("game/loader/native-lua51.lua")
(SOURCE / native_lua_relative).write_text((ROOT / "scripts/lua51-resolvers.lua").read_text())
replace("src/physfs.c", '#include "main.h"', '#include "main.h"\n#include "NativeLua.h"')
replace("src/physfs.c", '\tluaL_openlib(L, "fs", fslib, 0);',
        '\tluaL_openlib(L, "fs", fslib, 0);\n\tte4_native_lua_init(L);')

if patches:
    print("Applied native macOS patches.")
if ORIGINALS.exists():
    consolidated = []
    for upstream in sorted(ORIGINALS.rglob("*")):
        if not upstream.is_file() or upstream.name.startswith('.'):
            continue
        relative = upstream.relative_to(ORIGINALS)
        consolidated.extend(difflib.unified_diff(
            upstream.read_text().splitlines(True), (SOURCE / relative).read_text().splitlines(True),
            fromfile=f"a/{relative}", tofile=f"b/{relative}"))
    consolidated.extend(difflib.unified_diff(
        [], (SOURCE / native_lua_relative).read_text().splitlines(True),
        fromfile="/dev/null", tofile=f"b/{native_lua_relative}"))
    (ROOT / "patches/native-arm64.patch").write_text("".join(consolidated))
