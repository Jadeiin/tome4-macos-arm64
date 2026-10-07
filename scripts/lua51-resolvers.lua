-- Resolve the engine's documented instant resolvers before dependent fields.
-- Installed before Entity methods are inherited by Actor/Object subclasses.
return function(Entity)
	if Entity.__native_lua51_resolvers then return end
	local resolve = Entity.resolve

	function Entity:resolve(t, last, on_entity, key_chain)
		t = t or self
		key_chain = key_chain or {}
		local instant = {}
		for k, value in pairs(t) do
			if type(value) == "table" and value.__resolver and value.__resolve_instant
				and (not value.__resolve_last or last) then
				instant[k] = value
			end
		end
		local function calculate(value, k)
			return resolvers.calc[value.__resolver](value, on_entity or self, self, t, k, key_chain)
		end
		for k, value in pairs(instant) do
			-- A preceding resolver may have changed another field.
			if t[k] == value then
				local result = calculate(value, k)
				t[k] = result
				-- Preserve upstream handling of an immediately returned resolver.
				if type(result) == "table" and result.__resolver and result.__resolve_instant
					and (not result.__resolve_last or last) then
					t[k] = calculate(result, k)
				end
			end
		end
		return resolve(self, t, last, on_entity, key_chain)
	end
	Entity.__native_lua51_resolvers = true
	print("[NATIVE LUA51] instant resolver priority enabled")
end
