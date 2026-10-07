/* Exercise copied runtime libraries without registering a GUI application. */
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

typedef struct lua_State lua_State;
typedef struct { uint8_t major, minor, patch; } SDLVersion;

static void *open_library(const char *directory, const char *name)
{
    char path[PATH_MAX];
    if (snprintf(path, sizeof(path), "%s/%s", directory, name) >= sizeof(path)) exit(2);
    void *handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!handle) { fprintf(stderr, "%s: %s\n", name, dlerror()); exit(1); }
    return handle;
}

static void *symbol(void *handle, const char *name)
{
    void *result = dlsym(handle, name);
    if (!result) { fprintf(stderr, "Missing symbol %s\n", name); exit(1); }
    return result;
}

int main(int argc, char **argv)
{
    if (argc < 3) return 2;
    void *sdl = open_library(argv[1], "libSDL2-2.0.0.dylib");
    int (*init)(uint32_t) = symbol(sdl, "SDL_Init");
    void (*quit)(void) = symbol(sdl, "SDL_Quit");
    void (*version)(SDLVersion *) = symbol(sdl, "SDL_GetVersion");
    if (init(0)) { fprintf(stderr, "SDL initialization failed\n"); return 1; }
    SDLVersion v;
    version(&v);
    printf("SDL2 %u.%u.%u initialized with its SDL3 backend\n", v.major, v.minor, v.patch);
    void *lua = open_library(argv[1], "libluajit-5.1.2.dylib");
    lua_State *(*new_state)(void) = symbol(lua, "luaL_newstate");
    void (*open_libs)(lua_State *) = symbol(lua, "luaL_openlibs");
    int (*load)(lua_State *, const char *) = symbol(lua, "luaL_loadstring");
    int (*pcall)(lua_State *, int, int, int) = symbol(lua, "lua_pcall");
    const char *(*string)(lua_State *, int, size_t *) = symbol(lua, "lua_tolstring");
    void (*close)(lua_State *) = symbol(lua, "lua_close");
    lua_State *L = new_state();
    if (!L) return 2;
    open_libs(L);
    const char *check = "assert(jit.arch=='arm64' and jit.status());"
                        "local n=0;for i=1,100000 do n=n+i end;assert(n==5000050000);"
                        "assert(require('jit.util').traceinfo(1));"
                        "print('ARM64 LuaJIT emitted a JIT trace')";
    if (load(L, check) || pcall(L, 0, 0, 0)) {
        fprintf(stderr, "LuaJIT check failed: %s\n", string(L, -1, NULL));
        return 1;
    }
    for (int i = 2; i < argc; i++) open_library(argv[1], argv[i]);
    for (uint32_t i = 0; i < _dyld_image_count(); i++)
        printf("IMAGE\t%s\n", _dyld_get_image_name(i));
    close(L);
    quit();
    return 0;
}
