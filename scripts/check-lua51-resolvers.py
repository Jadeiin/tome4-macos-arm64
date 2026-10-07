#!/usr/bin/env python3
"""Reproduce and fix wild-infusion resolution using the actual archived Lua code."""
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

def function(text, signature):
    start = text.index(signature)
    return text[start:text.index("\nend", start) + 4]

with zipfile.ZipFile(SOURCE / f"game/engines/te4-{VERSION}.teae") as archive:
    files = {name: archive.read(name).decode() for name in [
        "engine/Entity.lua", "engine/resolvers.lua", "engine/class.lua",
        "engine/utils.lua", "engine/Object.lua", "engine/interface/ObjectActivable.lua",
        "engine/interface/ObjectIdentify.lua", "engine/interface/ActorTalents.lua"]}
with zipfile.ZipFile(SOURCE / f"game/modules/tome-{VERSION}.team") as archive:
    files.update({name: archive.read(name).decode() for name in [
        "mod/resolvers.lua", "mod/class/Object.lua", "data/general/objects/scrolls.lua"]})

parts = [r'''
local _M = {}
local next_uid, __uids = 1, {}
config={settings={}}
_t=function(s) return s end
colors={LIGHT_GREEN={r=0,g=255,b=0}}
resolvers={calc={},current_level=1,mbonus_max_level=50}
util={bound=function(n,lo,hi) return math.min(hi,math.max(lo,n)) end}
rng={percent=checked_percent,range=function(lo,hi) return lo end,
 float=function(lo,hi) return (lo+hi)/2 end,
 mbonus=function(max,level,maxlevel) return math.floor(max*level/maxlevel) end,
 tableIndex=function(t,exclude) for k in pairs(t) do if not exclude or not exclude[k] then return k end end end}
''']
for file, signatures in {
    "engine/Entity.lua": ["function _M:resolve(", "function _M:init(", "local function importBase("],
    "engine/resolvers.lua": ["function resolvers.generic(", "function resolvers.calc.generic("],
    "engine/class.lua": ["local function clonerecursfull("],
    "engine/utils.lua": ["function table.clone(", "function table.merge(", "function table.mergeAppendArray("],
    "mod/resolvers.lua": ["function resolvers.mbonus_level(", "function resolvers.calc.mbonus_level(",
                          "function resolvers.mbonus(", "function resolvers.calc.mbonus("],
}.items():
    parts.extend(function(files[file], signature) for signature in signatures)
parts.append("local Entity=_M\nlocal CoreObject,Activable,Identify,Talents,TomeObject={},{},{},{},{}\n"
             "engine={Object=CoreObject,interface={ObjectActivable=Activable,ObjectIdentify=Identify,ActorTalents=Talents}}")
for file, binding in [("engine/Object.lua", "CoreObject"),
                      ("engine/interface/ObjectActivable.lua", "Activable"),
                      ("engine/interface/ObjectIdentify.lua", "Identify"),
                      ("engine/interface/ActorTalents.lua", "Talents"),
                      ("mod/class/Object.lua", "TomeObject")]:
    parts.append(function(files[file], "function _M:init(").replace(
        "function _M:init(", f"function {binding}:init(", 1))
parts.append(r'''
local res,prototype={}
function newEntity(t)
 if t.base then t=importBase(t,res[t.base]) end
 local e=setmetatable({},{__index=_M})
 TomeObject.init(e,t,false)
 if e.define_as then res[e.define_as]=e else prototype=e end
end
''')
scrolls = files["data/general/objects/scrolls.lua"]
for marker in ['define_as = "BASE_INFUSION"', 'name = "wild infusion"']:
    start = scrolls.rfind("newEntity{", 0, scrolls.index(marker))
    end = scrolls.find("\nnewEntity{", start + 1)
    parts.append(scrolls[start:end])
parts.append(r'''
local failures=0
for padding=0,80 do
 local baseline=clonerecursfull({},prototype)
 for i=1,padding do baseline["layout"..i]={tag="different hash layout"} end
 local ok,err=pcall(function() baseline:resolve();baseline:resolve(nil,true) end)
 if not ok then
  assert(tostring(err):find("number expected, got table",1,true),tostring(err))
  failures=failures+1
 end
end
print("Baseline: "..failures.." of 81 layouts reproduced the original percent type error")
''')
parts.append("local install=(function()\n" + (ROOT / "scripts/lua51-resolvers.lua").read_text() + "\nend)()\ninstall(_M)")
parts.append(r'''
for padding=0,80 do
 local e=clonerecursfull({},prototype)
 for i=1,padding do e["layout"..i]={tag="different hash layout"} end
 e:resolve();e:resolve(nil,true)
 assert(type(e.chance)=="number" and type(e.inscription_data)=="table")
 assert(type(e.inscription_data.power)=="number" and e.inscription_data.what)
end
-- Preserve the separate final pass and forwarding to a different target entity.
local calls=0
resolvers.calc.finalcheck=function(value,actor,owner,t,k,chain)
 calls=calls+1
 assert(actor==target and owner==holder and t==holder and k=="pending" and chain[1]=="root")
 return 9
end
target={}
holder=setmetatable({pending={__resolver="finalcheck",__resolve_instant=true,__resolve_last=true}},{__index=_M})
holder:resolve(nil,false,target,{"root"});assert(calls==0)
holder:resolve(nil,true,target,{"root"});assert(calls==1 and holder.pending==9)
-- Nested instant values must be processed once before their dependent callback.
local nestedcalls=0
resolvers.calc.nestedvalue=function() nestedcalls=nestedcalls+1 return 7 end
resolvers.calc.nestedconsumer=function(_,actor,owner,t) assert(t.value==7) return t.value+1 end
local nested=setmetatable({data={value={__resolver="nestedvalue",__resolve_instant=true},
 dependent={__resolver="nestedconsumer"}}},{__index=_M})
nested:resolve();nested:resolve(nil,true)
assert(nestedcalls==1 and nested.data.dependent==8)
local patched=_M.resolve;install(_M);assert(_M.resolve==patched)
print("PASS: 81 wild-infusion table layouts, final-pass forwarding, nested dependency, and idempotent installation")
''')
case = BUILD / "lua51-resolvers.lua"
case.write_text("\n".join(parts) + "\n")
runner = BUILD / "luajit-resolvers"
flags = shlex.split(subprocess.check_output(
    ["/opt/homebrew/bin/pkg-config", "--cflags", "--libs", "luajit"], text=True))
subprocess.run(["/usr/bin/clang", "-arch", "arm64", str(ROOT / "scripts/check-lua51-resolvers.c"),
                *flags, "-o", str(runner)], check=True)
result = subprocess.run([str(runner), str(case)], text=True, capture_output=True)
(ROOT / "logs/luajit-resolvers-check.log").write_text(result.stdout + result.stderr)
print(result.stdout + result.stderr, end="")
raise SystemExit(result.returncode)
