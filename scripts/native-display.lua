-- Keep the upstream windowed/borderless UI; native fullscreen uses the desktop.
return function(DisplayResolution)
	local init = DisplayResolution.init
	local generateList = DisplayResolution.generateList

	function DisplayResolution:generateList()
		if self.native_fullscreen then
			local width, height = core.display.desktopSize()
			local resolution = ("%dx%d"):format(width, height)
			self.list = {{name="a)  "..resolution, r=resolution}}
		else
			generateList(self)
		end
	end

	function DisplayResolution:init(on_change)
		local _, _, fullscreen = core.display.size()
		self.native_fullscreen = fullscreen
		init(self, on_change)
		for _, checkbox in ipairs{self.c_fs, self.c_bl, self.c_wn} do
			local on_change = checkbox.on_change
			checkbox.on_change = function(checked)
				on_change(checked)
				self.native_fullscreen = self.c_fs.checked
				self:generateList()
				self.c_list.list = self.list
				self.c_list.nb_items = #self.list
				self.c_list.h = nil
				self.c_list:generate()
				self:setupUI(true, true)
			end
		end
	end
end
