#include <stdio.h>
#include <stdlib.h>
#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"
#include "physfs.h"
#include "NativeLua.h"

static int exists(lua_State *L)
{
    lua_pushboolean(L, PHYSFS_exists(luaL_checkstring(L, 1)));
    return 1;
}

int main(int argc, char **argv)
{
    if (argc != 4 || !PHYSFS_init(argv[0]) || !PHYSFS_mount(argv[1], "/", 1) || !PHYSFS_mount(argv[2], "/", 1)) return 2;
    lua_State *L = luaL_newstate();
    if (!L) return 2;
    luaL_openlibs(L);
    lua_newtable(L);
    lua_pushcfunction(L, exists);
    lua_setfield(L, -2, "exists");
    lua_setglobal(L, "fs");
    te4_native_lua_init(L);
    int result = te4_physfs_loadfile(L, argv[3]);
    if (!result) result = lua_pcall(L, 0, 0, 0);
    if (result) fprintf(stderr, "%s\n", lua_tostring(L, -1));
    lua_close(L);
    PHYSFS_deinit();
    return result ? 1 : 0;
}
