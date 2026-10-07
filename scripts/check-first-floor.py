#!/usr/bin/env python3
"""Create a disposable dwarf Bulwark and verify the actual first floor and infusions."""
import argparse
import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import zipfile

from project import APP, LOGS, ROOT
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seconds", type=int, default=120, help="Maximum test runtime")
parser.add_argument("--talents", action="store_true", help="Also cancel and complete real Shield Pummel targeting")
parser.add_argument("--require-dlcs", action="store_true", help="Also require all three paid DLCs to load")
args = parser.parse_args()
dlc_names = {"ashes-urhrok": "ashes-urhrok.teaac", "orcs": "orcs.teaac", "cults": "cults.teaac"}
expected_dlcs = [name for name, archive in dlc_names.items()
                 if args.require_dlcs or (APP / "Contents/Resources/game/dlcs" / archive).is_file()]
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
log_prefix = "luajit-gameplay" if args.talents else "luajit-first-floor"
home = ROOT / "build" / f"runtime-floor-{stamp}"
user = home / "Library/Application Support/T-Engine/4.0"
settings = user / "settings"
settings.mkdir(parents=True, exist_ok=True)
(settings / "disable_all_connectivity.cfg").write_text("disable_all_connectivity = true\n")
(settings / "addons.cfg").write_text('addons = {tome = {["native-floor-check"] = true}}\n')
addons = user / "addons"
addons.mkdir()
init = '''long_name="Native first-floor regression check"
short_name="native-floor-check"
for_module="tome"
version={1,7,6}
addon_version={1,0,0}
weight=1000
author={"Local build verification"}
description="Disposable automated character creation and first-floor check."
superload=true
'''
birther = r'''
local _M=loadPrevious(...)
local registered=_M.on_register
function _M:on_register(...)
 registered(self,...)
 if self.__native_floor_check then return end
 self.__native_floor_check=true
 game:onTickEnd(function()
  self.c_name.text="NativeFloorCheck"
  self:setDescriptor("sex","Male")
  self:setDescriptor("world","Maj'Eyal")
  self:setDescriptor("difficulty","Normal")
  self:setDescriptor("permadeath","Adventure")
  self:setDescriptor("race","Dwarf")
  self:setDescriptor("subrace","Dwarf")
  self:setDescriptor("class","Warrior")
  self:setDescriptor("subclass","Bulwark")
  __module_extra_info.no_birth_popup=true
  __module_extra_info.birth_done_script=[=[
   assert(game.zone.short_name=="reknor-escape","Unexpected starting zone")
   assert(game.level.level==1 and game.player.x and game.player.y,"Player did not enter the first floor")
   print("[NATIVE FLOOR CHECK] entered zone=reknor-escape floor=1")
   local template
   for _,object in ipairs(game.zone.object_list) do
    if object.name=="wild infusion" then template=object break end
   end
   assert(template,"Wild infusion is missing from the real zone object list")
   local before=core.game.getTime()
   for i=1,100 do
    local object=game.zone:finishEntity(game.level,"object",template)
    assert(object and type(object.chance)=="number" and type(object.inscription_data)=="table","Unresolved inscription")
    assert(type(object.inscription_data.power)=="number" and object.inscription_data.what,"Incomplete inscription data")
   end
   print("[NATIVE FLOOR CHECK] infusions=100 ms="..(core.game.getTime()-before))
   local ticks=core.wait.getTicks()
   assert(ticks==0,"Generation waiting state was not cleared")
   print("[NATIVE FLOOR CHECK] waiting_ticks=0")
   __NATIVE_TALENT_CHECK__
   print("[NATIVE FLOOR CHECK] ready zone="..game.zone.short_name.." floor="..game.level.level.." waiting_ticks="..ticks)
  ]=]
  print("[NATIVE FLOOR CHECK] creating dwarf Bulwark")
  self:atEnd("created")
 end)
end
return _M
'''
talent_check = r'''
   assert(jit and jit.arch=="arm64" and jit.status(),"Native ARM64 JIT is not enabled")
   print("[NATIVE TALENT CHECK] runtime="..jit.version.." arch="..jit.arch.." jit=true")
   local p=game.player
   local x,y
   for dx=-1,1 do for dy=-1,1 do
    local nx,ny=p.x+dx,p.y+dy
    if not x and (dx~=0 or dy~=0) and game.level.map:isBound(nx,ny)
     and not game.level.map:checkAllEntities(nx,ny,"block_move",p) then x,y=nx,ny end
   end end
   assert(x,"No adjacent free grid for the targeting test")
   local dummy=game.zone:makeEntityByName(game.level,"actor","ORC")
   assert(dummy,"Missing zone orc template")
   dummy.name="NativeTargetDummy"
   dummy.ai="none"
   dummy.max_life=10000;dummy.life=10000
   dummy.no_drops=true
   game.zone:addEntity(game.level,dummy,"actor",x,y)
   local tid=p.T_SHIELD_PUMMEL
   if not p:knowTalent(tid) then p:learnTalent(tid,true) end
   assert(p:hasShield(),"Bulwark is missing its starting shield")
   config.settings.auto_accept_target=false
   config.settings.tome.immediate_melee_keys=false
   config.settings.tome.immediate_melee_keys_auto=false
   p.talents_cd[tid]=nil
   local attacks=0
   local attack=p.attackTargetWith
   p.attackTargetWith=function(self,...)
    attacks=attacks+1
    return attack(self,...)
   end
   p:useTalent(tid,nil,nil,nil,nil,true,true)
   local co=game.target_co
   assert(co and coroutine.status(co)=="suspended","Shield Pummel did not suspend for targeting")
   game.target.target.x=nil;game.target.target.y=nil;game.target.target.entity=nil
   game.target_warning=false
   game:targetMode(false,false)
   assert(coroutine.status(co)=="dead" and not game.target_co and not p.talents_cd[tid] and attacks==0,
    "Cancelling targeting did not cleanly cancel the talent")
   print("[NATIVE TALENT CHECK] cancelled=shield-pummel attacks=0 cooldown=false")
   p:useTalent(tid,nil,nil,nil,nil,true,true)
   co=game.target_co
   assert(co and coroutine.status(co)=="suspended","Shield Pummel did not suspend a second time")
   game.target.target.x=x;game.target.target.y=y;game.target.target.entity=dummy
   game.target_warning=false
   game:targetMode(false,false)
   assert(coroutine.status(co)=="dead" and not game.target_co and attacks==2 and p.talents_cd[tid],
    "Selected Shield Pummel did not complete both attacks and start cooldown")
   assert(not p.__talent_running and not p.talent_error,"Talent error or running state remains")
   p.attackTargetWith=attack
   print("[NATIVE TALENT CHECK] selected=shield-pummel attacks=2 cooldown=true")
'''
birther = birther.replace("__NATIVE_TALENT_CHECK__", talent_check if args.talents else "")
game = r'''
local _M=loadPrevious(...)
local change=_M.changeLevelReal
function _M:changeLevelReal(...)
 local started=core.game.getTime()
 local result=change(self,...)
 print("[NATIVE FLOOR CHECK] generation_ms="..(core.game.getTime()-started).." zone="..tostring(self.zone and self.zone.short_name))
 return result
end
return _M
'''
with zipfile.ZipFile(addons / "tome-native-floor-check.teaa", "w", zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("init.lua", init)
    archive.writestr("superload/mod/dialogs/Birther.lua", birther)
    archive.writestr("superload/mod/class/Game.lua", game)
logs = LOGS
system_log = Path("/tmp/te4_log.txt")
old_stat = system_log.stat() if system_log.exists() else None
command = [str(APP / "Contents/MacOS/t-engine"), "--home", str(home),
           "--flush-stdout", "--no-web", "-Mtome", "-n", "-uNativeFloorCheck"]
print(f"Testing {'first floor and targeting' if args.talents else 'the first floor'} with an isolated profile: {home}", flush=True)
started = time.monotonic()
with (logs / f"{log_prefix}-stderr.log").open("w") as output:
    process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
    try:
        ready_at = None
        while process.poll() is None and time.monotonic() - started < args.seconds:
            if system_log.exists() and (old_stat is None or system_log.stat().st_mtime_ns != old_stat.st_mtime_ns):
                current = system_log.read_text(errors="replace")
                if str(home) in current and "[NATIVE FLOOR CHECK] ready " in current and ready_at is None:
                    ready_at = time.monotonic()
                if "Lua Error:" in current:
                    break
            if ready_at is not None and time.monotonic() - ready_at >= 2:
                break
            time.sleep(0.25)
        fresh = system_log.exists() and (old_stat is None or system_log.stat().st_mtime_ns != old_stat.st_mtime_ns)
        current = system_log.read_text(errors="replace") if fresh else ""
        if fresh:
            shutil.copyfile(system_log, logs / f"{log_prefix}-startup.log")
        checks = {
            "game_running": process.poll() is None,
            "own_profile": str(home) in current,
            "luajit_arm64": bool(re.search(r"LuaVM:\tLuaJIT 2\.1[^\n]*\tarm64", current)),
            "resolver_fix_installed": "[NATIVE LUA51] instant resolver priority enabled" in current,
            "first_floor_entered": "[NATIVE FLOOR CHECK] entered zone=reknor-escape floor=1" in current,
            "waiting_state_cleared": "[NATIVE FLOOR CHECK] waiting_ticks=0" in current,
            "hundred_infusions_resolved": "[NATIVE FLOOR CHECK] infusions=100 " in current,
            "no_lua_errors": bool(current) and "Lua Error:" not in current,
            "openal_soft": "OpenAL Soft" in current,
        }
        for name in expected_dlcs:
            checks[name + "_loaded"] = f"[MODULE LOADER] addon \t{name}\t MD5" in current
        if args.talents:
            checks.update({
                "jit_enabled": "arch=arm64 jit=true" in current,
                "target_cancelled": "[NATIVE TALENT CHECK] cancelled=shield-pummel attacks=0 cooldown=false" in current,
                "target_selected": "[NATIVE TALENT CHECK] selected=shield-pummel attacks=2 cooldown=true" in current,
            })
        generation = re.findall(r"\[NATIVE FLOOR CHECK\] generation_ms=(\d+) zone=(\S+)", current)
        report = {"time": stamp, "profile": str(home), "elapsed_seconds": round(time.monotonic()-started, 2),
                  "expected_dlcs": expected_dlcs,
                  "checks": checks, "generation_times_ms": [{"zone": zone, "ms": int(ms)} for ms, zone in generation],
                  "passed": all(checks.values())}
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        print("Test process closed.", flush=True)
if report["passed"]:
    shutil.rmtree(home)
report["profile_cleaned"] = report["passed"]
(logs / f"{log_prefix}-check.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 1)
