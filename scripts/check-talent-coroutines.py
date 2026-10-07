#!/usr/bin/env python3
"""Check archived talent/targeting coroutine behavior in ARM64 LuaJIT."""
import platform
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
    talents = archive.read("engine/interface/ActorTalents.lua").decode()
    targeting = archive.read("engine/interface/GameTargeting.lua").decode()
with zipfile.ZipFile(SOURCE / f"game/modules/tome-{VERSION}.team") as archive:
    shields = archive.read("data/talents/techniques/weaponshield.lua").decode()

parts = [r'''
local _M = {talents_def={}}
local Map = {setViewerFaction=function() end}
local Dialog = {yesnoPopup=function() error("Unexpected confirmation popup") end}
local function noop() end
config={settings={auto_accept_target=false}}
_t=function(s) return s end
function newTalent(t) t.id="T_SHIELD_PUMMEL";t.mode=t.mode or "activated";_M.talents_def[t.id]=t end
''']
parts.append(function(talents, "function _M:useTalent("))
parts.append("local Targeting={}\n")
for signature in ["function _M:targetGetForPlayer(", "function _M:targetMode("]:
    parts.append(function(targeting, signature).replace("function _M:", "function Targeting:", 1))
start = shields.index("newTalent{")
parts.append(shields[start:shields.index("\nnewTalent{", start + 1)])
parts.append(r'''
local function reset()
 local actor=setmetatable({name="NativeTest",uid=1,player=true,x=3,y=3,faction="players",
  talents={},talents_cd={},sustain_talents={},attacks=0,cooldowns=0,posts=0,errors=0,
  EFF_STUNNED="stunned",T_SHIELD_EXPERTISE="expertise"},{__index=_M})
 actor.isTalentCoolingDown=function() return false end
 actor.preUseTalent=function() return true end
 actor.postUseTalent=function(self,t,ret) self.posts=self.posts+1;return ret end
 actor.logTalentMessage=noop
 actor.setCurrentTalentMode=function(self,mode) self.mode=mode end
 actor.startTalentCooldown=function(self) self.cooldowns=self.cooldowns+1 end
 actor.isTalentConfirmable=function() return false end
 actor.onTalentLuaError=function(self,t,err) self.errors=self.errors+1;self.last_error=err end
 actor.hasShield=function() return {},{} end
 actor.getTalentRange=function() return 1 end
 actor.getTalentTarget=function(self,t) local tg=t.target(self,t);tg.no_start_scan=true;return tg end
 actor.getTarget=function(self,tg) return game:targetGetForPlayer(tg) end
 actor.canProject=function(self,tg,x,y) return x==4 and y==3 end
 actor.combatTalentWeaponDamage=function() return 1 end
 actor.getTalentLevel=function() return 1 end
 actor.combatTalentScale=function() return 4 end
 actor.combatAttackStr=function() return 20 end
 actor.attackTargetWith=function(self) self.attacks=self.attacks+1;return 1,true end
 actor.reactionToward=function() return -100 end
 actor.getName=function(self) return self.name end
 local victim={x=4,y=3,EFF_STUNNED="stunned",canBe=function() return true end,
  setEffect=function(self,eff,duration) self.effect=eff;self.duration=duration end}
 local keys={setCurrent=noop}
 game=setmetatable({player=actor,level={map={getTileToScreen=function() return 0,0 end}},
  target={target={},setActive=noop},normal_key=keys,targetmode_key=keys,
  logNewest=function() return "",1 end,logPlayer=noop,logSeen=noop}, {__index=Targeting})
 return actor,victim
end
''')
checks = r'''
assert(jit and jit.arch=="arm64" and jit.status()==EXPECT_JIT)
local actor,victim,ok,err
-- Run the actual Shield Pummel/useTalent/targetGetForPlayer/targetMode methods.
for i=1,40 do
 local actor,victim=reset()
 assert(actor:useTalent("T_SHIELD_PUMMEL")==nil)
 local co=game.target_co
 assert(co and coroutine.status(co)=="suspended" and actor.attacks==0 and actor.errors==0)
 game.target.target={x=4,y=3,entity=victim}
 game:targetMode(false,false)
 assert(coroutine.status(co)=="dead" and not game.target_co)
 assert(actor.attacks==2 and victim.effect=="stunned" and victim.duration==4,
  "attacks="..actor.attacks.." effect="..tostring(victim.effect).." duration="..tostring(victim.duration))
 assert(actor.cooldowns==1 and actor.posts==1 and actor.mode==nil and actor.errors==0)
 -- Cancellation must finish cleanly and spend no cooldown.
 actor=reset();actor:useTalent("T_SHIELD_PUMMEL");co=game.target_co
 game.target.target={};game:targetMode(false,false)
 assert(coroutine.status(co)=="dead" and actor.attacks==0 and actor.cooldowns==0 and actor.errors==0)
end
-- A failure after resuming must still restore talent state and report a trace.
actor,victim=reset()
actor.attackTargetWith=function() error("intentional talent failure") end
actor:useTalent("T_SHIELD_PUMMEL")
game.target.target={x=4,y=3,entity=victim}
ok,err=pcall(function() game:targetMode(false,false) end)
assert(not ok and tostring(err):find("intentional talent failure",1,true))
assert(actor.errors==1 and actor.mode==nil and actor.__talent_running==nil and actor.cooldowns==0)
assert(actor.last_error:find("stack traceback:",1,true) and actor.last_error:find("attackTargetWith",1,true))

local function pack(...) return {n=select("#",...),...} end
-- Nested pcall/xpcall must retain the caller handle captured by UI callbacks.
local outer,callback,steps
steps=0
outer=coroutine.create(function()
 assert(coroutine.running()==outer)
 local result=pack(pcall(function(a,b,c)
  assert(a==1 and b==nil and c==3 and coroutine.running()==outer)
  return xpcall(function()
   assert(coroutine.running()==outer and coroutine.status(outer)=="running")
   callback=coroutine.running()
   local input=pack(coroutine.yield("select",nil,3))
   assert(input.n==3 and input[1]==8 and input[2]==nil and input[3]==9)
   steps=steps+1
   coroutine.yield("dialog")
   steps=steps+1
   return nil,"done",nil
  end,debug.traceback)
 end,1,nil,3))
 assert(result.n==5 and result[1] and result[2] and result[3]==nil and result[4]=="done" and result[5]==nil)
end)
local result=pack(coroutine.resume(outer))
assert(result.n==4 and result[1] and result[2]=="select" and result[3]==nil and result[4]==3 and callback==outer)
result=pack(coroutine.resume(callback,8,nil,9));assert(result[1] and result[2]=="dialog" and steps==1)
assert(coroutine.resume(callback) and steps==2 and coroutine.status(outer)=="dead")
-- Errors and nil/false/table error-handler results keep their original values.
outer=coroutine.create(function()
 local object={}
 local success,value=pcall(function() coroutine.yield();error(object) end)
 assert(not success and value==object)
 for _,handler in ipairs({function() return nil end,function() return false end,function() return object end}) do
  success,value=xpcall(function() error(object) end,handler)
  assert(not success and value==handler())
 end
 success,value=xpcall(function() error(object) end,function() error("bad handler") end)
 assert(not success and value=="error in error handling")
end)
assert(coroutine.resume(outer));assert(coroutine.resume(outer) and coroutine.status(outer)=="dead")
assert(coroutine.running()==nil)
print("PASS: 40 actual Shield Pummel selections and cancellations, failure cleanup, nested suspension, caller identity, nil values, and error handling")
'''
definitions = "\n".join(parts) + "\n"
outputs = []
for label, command in [
    ("LuaJIT 2.1 JIT on", ["/opt/homebrew/bin/luajit", str(BUILD / "luajit-talents-on.lua")]),
    ("LuaJIT 2.1 JIT off", ["/opt/homebrew/bin/luajit", str(BUILD / "luajit-talents-off.lua")]),
]:
    if "JIT on" in label:
        Path(command[-1]).write_text("jit.on();local EXPECT_JIT=true\n" + definitions + checks)
    elif "JIT off" in label:
        Path(command[-1]).write_text("jit.off();local EXPECT_JIT=false\n" + definitions + checks)
    result = subprocess.run(command, text=True, capture_output=True)
    output = label + "\n" + result.stdout + result.stderr
    outputs.append(output)
    print(output, end="")
    if result.returncode:
        (ROOT / "logs/talent-coroutines-check.log").write_text("\n".join(outputs))
        raise SystemExit(result.returncode)
(ROOT / "logs/talent-coroutines-check.log").write_text("\n".join(outputs))
