/* Headless entry point for the real archived Lua resolver regression. */
#include <stdio.h>
#include <stdlib.h>
#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"

static int checked_percent(lua_State *L)
{
    int chance = luaL_checknumber(L, 1);
    /* Deterministic test RNG; retain the game's real numeric argument check. */
    lua_pushboolean(L, 0 < chance);
    return 1;
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    FILE *file = fopen(argv[1], "rb");
    if (!file) return 2;
    if (fseek(file, 0, SEEK_END)) return 2;
    long size = ftell(file);
    if (size < 0 || fseek(file, 0, SEEK_SET)) return 2;
    char *source = malloc((size_t)size + 1);
    if (!source || fread(source, 1, (size_t)size, file) != (size_t)size) return 2;
    source[size] = 0;
    fclose(file);
    lua_State *state = luaL_newstate();
    if (!state) return 2;
    luaL_openlibs(state);
    lua_pushcfunction(state, checked_percent);
    lua_setglobal(state, "checked_percent");
    int result = luaL_loadbuffer(state, source, (size_t)size, argv[1]);
    if (!result) result = lua_pcall(state, 0, 0, 0);
    if (result) fprintf(stderr, "%s\n", lua_tostring(state, -1));
    lua_close(state);
    free(source);
    return result ? 1 : 0;
}
