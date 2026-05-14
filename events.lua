-- events.lua  —  Vault Zero event scripting layer
-- Language: Lua  |  Called by: lua_bridge.py via subprocess
-- Reads quests.json, fires event hooks, returns JSON result

local json_path = arg[1] or "quests.json"
local event     = arg[2] or "room_enter"
local room_id   = arg[3] or "storage"
local extra     = arg[4] or ""

-- Minimal JSON encoder (no external deps)
local function json_encode(t)
    if type(t) == "table" then
        local is_arr = (#t > 0)
        if is_arr then
            local parts = {}
            for _, v in ipairs(t) do parts[#parts+1] = json_encode(v) end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            local parts = {}
            for k, v in pairs(t) do
                parts[#parts+1] = '"' .. k .. '":' .. json_encode(v)
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    elseif type(t) == "string" then
        return '"' .. t:gsub('"', '\\"'):gsub("\n", "\\n") .. '"'
    elseif type(t) == "boolean" then
        return t and "true" or "false"
    elseif type(t) == "number" then
        return tostring(t)
    else
        return '"nil"'
    end
end

-- Event handlers
local handlers = {}

handlers["room_enter"] = function(room, _)
    local flavour = {
        storage = "The fluorescent light flickers. Something drips in the dark.",
        lab     = "The centrifuge hums. One flask glows green in the dark.",
        server  = "The server fans create a white-noise curtain. LEDs blink in silence.",
        vault   = "The cameras sweep. You have very little time.",
    }
    return {
        event   = "room_enter",
        room    = room,
        flavour = flavour[room] or "You enter the room.",
        ok      = true,
    }
end

handlers["puzzle_attempt"] = function(room, extra)
    local attempts = tonumber(extra) or 1
    local taunts = {
        "The lock doesn't move.",
        "Wrong. The mechanism clicks back into place.",
        "Nothing. Try thinking about it differently.",
        "Still wrong. The clues are all here — look again.",
    }
    local idx = math.min(attempts, #taunts)
    return {
        event   = "puzzle_attempt",
        room    = room,
        attempt = attempts,
        flavour = taunts[idx],
        ok      = true,
    }
end

handlers["puzzle_solve"] = function(room, extra)
    local reactions = {
        storage = "A mechanical clunk echoes in the concrete room.",
        lab     = "A soft electronic chime. Green light.",
        server  = "The terminal screen floods with green text.",
        vault   = "The briefcase springs open with a pressurised hiss.",
    }
    return {
        event   = "puzzle_solve",
        room    = room,
        puzzle  = extra,
        flavour = reactions[room] or "It opens.",
        ok      = true,
    }
end

handlers["game_over"] = function(room, extra)
    return {
        event   = "game_over",
        reason  = extra,
        flavour = "The security system trips. Vault Zero locks down. "
                .. "You will be found.",
        ok      = true,
    }
end

handlers["escape"] = function(room, _)
    return {
        event   = "escape",
        room    = room,
        flavour = "You emerge into the corridor. The drive is in your hand. "
                .. "Project Echo — whatever it is — is yours.",
        ok      = true,
    }
end

-- Dispatch
local handler = handlers[event]
local result
if handler then
    result = handler(room_id, extra)
else
    result = { event = event, ok = false, error = "unknown event: " .. event }
end

io.write(json_encode(result) .. "\n")
