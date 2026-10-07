#!/usr/bin/env python3
"""Check ToME's math, sorting and PhysFS APIs against native LuaJIT."""
import platform
import shlex
import subprocess
import zipfile
from pathlib import Path

from project import ROOT, SOURCE, VERSION
BUILD = ROOT / "build/native/checks"
if platform.machine() != "arm64":
    raise SystemExit("Run the check from an ARM64 terminal.")
BUILD.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(SOURCE / f"game/modules/tome-{VERSION}.team") as z:
    physical = z.read("data/timed_effects/physical.lua").decode()
effects = []
for name in ["DUAL_WEAPON_DEFENSE", "PARRY", "COUNTER_ATTACKING", "DEFENSIVE_GRAPPLING"]:
    start = physical.rfind("\nnewEffect{", 0, physical.index(f'name = "{name}"')) + 1
    end = physical.index("\nnewEffect{", start + 1)
    effects.append(physical[start:end])
with zipfile.ZipFile(SOURCE / "game/addons/tome-remote-designer.teaa") as z:
    cookies = z.read("overload/codeweb/cookies.lua").decode()
debugger = (SOURCE / "game/thirdparty/remdebug/engine.lua").read_text()
strings = []
for text, signature in [(cookies, "local function read_cookies (req)"),
                        (debugger, "local function break_dir(path)")]:
    start = text.index(signature)
    strings.append(text[start:text.index("\nend", start) + 4])
strings.append("return {read_cookies=read_cookies, break_dir=break_dir}")
archive = BUILD / "luajit-vfs.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("fixtures/module.lua", 'return {name="native virtual module"}\n')
    z.writestr("fixtures/yield.lua", 'return coroutine.yield("waiting",nil,3)\n')
    z.writestr("fixtures/invalid.lua", 'local = invalid syntax\n')
    z.writestr("fixtures/physical-effects.lua", "\n".join(effects))
    z.writestr("fixtures/legacy-strings.lua", "\n".join(strings))
    z.writestr("fixtures/check.lua", r'''
assert(jit.arch=="arm64" and jit.status())
local legacy=dofile("/fixtures/legacy-strings.lua")
local request={headers={cookie='first="a"; second="b"; $Path="/game"'}}
legacy.read_cookies(request)
assert(request.cookies.first.value=="a" and request.cookies.second.value=="b")
assert(request.cookies.second.options.Path=="/game")
local parts=legacy.break_dir([[C:\games\T-Engine/file.lua]])
assert(#parts==4 and parts[1]=="C:" and parts[4]=="file.lua")
local effects = {}
_t=function(s) return s end
newEffect=function(effect) effects[effect.name]=effect end
util={bound=function(n,lo,hi) return math.min(hi,math.max(lo,n)) end}
dofile("/fixtures/physical-effects.lua")
local actor={attr=function() return false end,isUnarmed=function() return true end}
for _,case in ipairs{
 {"DUAL_WEAPON_DEFENSE","deflectchance","deflects"},
 {"PARRY","deflectchance","deflects"},
 {"COUNTER_ATTACKING","counterchance","counterattacks"},
 {"DEFENSIVE_GRAPPLING","throwchance","throws"},
} do
 local chance=effects[case[1]][case[2]]
 for _,value in ipairs{{0,0},{0.5,30},{1,60},{1.5,60}} do
  assert(chance(actor,{chance=60,[case[3]]=value[1]})==value[2],case[1])
 end
end
assert(effects.PARRY.deflectchance(actor,{chance=60,deflects=0.5},1/3)==10)
assert(math.mod(-5,3)==-2 and math.mod(5,-3)==2 and math.mod(1.75,1)==0.75)
local unlocks={{order=3},{order=1},{order=2}}
table.sort(unlocks,"order")
assert(unlocks[1].order==1 and unlocks[2].order==2 and unlocks[3].order==3)
local numeric={{9},{2},{5}};table.sort(numeric,1);assert(numeric[1][1]==2 and numeric[3][1]==9)
local default={3,1,2};table.sort(default);assert(default[1]==1 and default[3]==3)
table.sort(default,function(a,b) return a>b end);assert(default[1]==3 and default[3]==1)
local strings={{name="z"},{name="a"}};table.sort(strings,"name");assert(strings[1].name=="a")
package.path="/?.lua"
engine={}
assert(loadfile("/engine/version.lua"))()
assert(engine.version[1]==1 and engine.version[2]==7 and engine.version[3]==6)
assert(require("fixtures.module").name=="native virtual module")
local chunk,err=loadfile("/fixtures/missing.lua")
assert(chunk==nil and err:find("cannot open",1,true))
chunk,err=loadfile("/fixtures/invalid.lua")
assert(chunk==nil and err:find("fixtures/invalid.lua",1,true))
local function pack(...) return {n=select("#",...),...} end
local co=coroutine.create(function()
 local result=pack(dofile("/fixtures/yield.lua"))
 assert(result.n==3 and result[1]==8 and result[2]==nil and result[3]==9)
end)
local result=pack(coroutine.resume(co))
assert(result.n==4 and result[1] and result[2]=="waiting" and result[3]==nil and result[4]==3)
assert(coroutine.resume(co,8,nil,9) and coroutine.status(co)=="dead")
print("PASS: native LuaJIT original cookie/debugger parsing, parry/counter/grapple effects and math.mod, ToME sorting, PhysFS loading, missing/syntax errors, and yieldable dofile")
''')
objects = []
obj = ROOT / "build/native/obj/t-engine4-src-1.7.6/src"
for directory in ["physfs", "physfs/archivers", "physfs/platform", "zlib"]:
    objects.extend(sorted((obj / directory).glob("*.o")))
flags = shlex.split(subprocess.check_output(
    ["/opt/homebrew/bin/pkg-config", "--cflags", "--libs", "luajit", "sdl2"], text=True))
runner = BUILD / "luajit-vfs"
subprocess.run(["/usr/bin/clang", "-arch", "arm64", f"-I{SOURCE / 'src/physfs'}",
                f"-I{ROOT / 'scripts'}", str(ROOT / "scripts/check-luajit-vfs.c"),
                str(ROOT / "build/native/obj/scripts/NativeLua.o"), *map(str, objects),
                *flags, "-o", str(runner)], check=True)
result = subprocess.run([str(runner), str(archive), str(SOURCE / f"game/engines/te4-{VERSION}.teae"),
                         "/fixtures/check.lua"], text=True, capture_output=True)
(ROOT / "logs/luajit-vfs-check.log").write_text(result.stdout + result.stderr)
print(result.stdout + result.stderr, end="")
raise SystemExit(result.returncode)
