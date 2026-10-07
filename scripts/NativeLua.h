#ifndef TE4_NATIVE_LUA_H
#define TE4_NATIVE_LUA_H
#include "lua.h"

int te4_physfs_loadfile(lua_State *L, const char *filename);
void te4_native_lua_init(lua_State *L);
#endif
