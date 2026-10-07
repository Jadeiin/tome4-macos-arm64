/* Restore ToME's math, sorting and PhysFS loading APIs for system LuaJIT. */
#include <stddef.h>
#include <string.h>
#include "lua.h"
#include "lauxlib.h"
#include "physfs.h"
#include "NativeLua.h"

typedef struct {
    PHYSFS_File *file;
    int failed;
    char buffer[LUAL_BUFFERSIZE];
} FileReader;

static const char *read_chunk(lua_State *L, void *data, size_t *size)
{
    (void)L;
    FileReader *reader = data;
    PHYSFS_sint64 count = PHYSFS_read(reader->file, reader->buffer, 1, sizeof(reader->buffer));
    if (count < 0) reader->failed = 1;
    *size = count > 0 ? (size_t)count : 0;
    return *size ? reader->buffer : NULL;
}

int te4_physfs_loadfile(lua_State *L, const char *filename)
{
    FileReader reader = {0};
    reader.file = filename ? PHYSFS_openRead(filename) : NULL;
    if (!reader.file) {
        const char *error = PHYSFS_getLastError();
        lua_pushfstring(L, "cannot open %s: %s", filename ? filename : "(nil)", error ? error : "file unavailable");
        return LUA_ERRFILE;
    }
    int name_index = lua_gettop(L) + 1;
    lua_pushfstring(L, "@%s", filename);
    int result = lua_load(L, read_chunk, &reader, lua_tostring(L, name_index));
    PHYSFS_close(reader.file);
    lua_remove(L, name_index);
    if (reader.failed) {
        lua_pop(L, 1);
        lua_pushfstring(L, "cannot read %s", filename);
        return LUA_ERRFILE;
    }
    return result;
}

static int native_loadfile(lua_State *L)
{
    const char *filename = luaL_checkstring(L, 1);
    if (!te4_physfs_loadfile(L, filename)) return 1;
    lua_pushnil(L);
    lua_insert(L, -2);
    return 2;
}

void te4_native_lua_init(lua_State *L)
{
    int top = lua_gettop(L);
    lua_pushcfunction(L, native_loadfile);
    lua_setglobal(L, "loadfile");
    /* Preserve ToME's field-key table.sort extension. Lua dofile keeps talent
     * coroutines yieldable; the module searcher must use the virtual filesystem. */
    const char *bridge =
        "math.mod = math.fmod\n"
        "local sort = table.sort\n"
        "function table.sort(list, compare)\n"
        " if compare ~= nil and type(compare) ~= 'function' then\n"
        "  local key = compare\n"
        "  compare = function(a, b) return a[key] < b[key] end\n"
        " end\n"
        " return sort(list, compare)\n"
        "end\n"
        "function dofile(filename)\n"
        " local chunk, err = loadfile(filename)\n"
        " if not chunk then error(err, 2) end\n"
        " return chunk()\n"
        "end\n"
        "package.loaders[2] = function(name)\n"
        " local filename = name:gsub('%.' , '/')\n"
        " local errors = {}\n"
        " for template in package.path:gmatch('[^;]+') do\n"
        "  local path = template:gsub('%?', function() return filename end)\n"
        "  if fs.exists(path) then\n"
        "   local chunk, err = loadfile(path)\n"
        "   if not chunk then error(err, 2) end\n"
        "   return chunk\n"
        "  end\n"
        "  errors[#errors+1] = \"\\n\\tno virtual file '\"..path..\"'\"\n"
        " end\n"
        " return table.concat(errors)\n"
        "end\n";
    if (luaL_loadbuffer(L, bridge, strlen(bridge), "@native-luajit-vfs") || lua_pcall(L, 0, 0, 0))
        luaL_error(L, "Native LuaJIT initialization failed: %s", lua_tostring(L, -1));
    lua_settop(L, top);
}
