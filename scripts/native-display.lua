-- Native macOS fullscreen uses the desktop; window sizes are logical points.
return function(DisplayResolution)
	local Dialog = require "engine.ui.Dialog"
	local List = require "engine.ui.List"

	function DisplayResolution:generateList()
		local width, height = core.display.usableSize()
		local list = {}
		for _, size in pairs(game.available_resolutions) do
			if not size[3] and size[1] <= width and size[2] <= height then
				local resolution = ("%dx%d"):format(size[1], size[2])
				list[#list+1] = {name=resolution.." ".._t"Windowed", r=resolution,
					w=size[1], h=size[2]}
			end
		end
		table.sort(list, function(a, b) return a.w == b.w and a.h < b.h or a.w < b.w end)
		table.insert(list, 1, {name=_t"Fullscreen", fullscreen=true})
		self.list = list
	end

	function DisplayResolution:init(on_change)
		self.on_change = on_change
		self:generateList()
		Dialog.init(self, _t"Switch Resolution", 300, 20)
		self.c_list = List.new{width=self.iw, nb_items=#self.list, list=self.list,
			fct=function(item) self:use(item) end}
		self:loadUI{{left=0, top=0, ui=self.c_list}}
		self:setFocus(self.c_list)
		self:setupUI(true, true)
		self.key:addBinds{EXIT=function() game:unregisterDialog(self) end}
	end

	function DisplayResolution:use(item)
		local resolution
		if item.fullscreen then
			local _, _, _, _, width, height = core.display.size()
			resolution = ("%dx%d Fullscreen"):format(width, height)
		else
			resolution = item.r.." Windowed"
		end
		game:setResolution(resolution, true)
		game:unregisterDialog(self)
		if self.on_change then self.on_change(resolution) end
	end
end
