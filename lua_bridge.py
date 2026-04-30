"""
lua_bridge.py — Python ↔ Lua bridge
Language: Python  |  Calls: quests/events.lua via subprocess
Returns parsed dict from Lua's JSON output
"""
import subprocess, json, os, shutil

BASE     = os.path.dirname(os.path.abspath(__file__))
LUA_SCRIPT = os.path.join(BASE, "quests", "events.lua")
LUA_BIN  = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("lua5.3") or shutil.which("lua5.1")


def fire_event(event: str, room_id: str, extra: str = "") -> dict:
    """
    Fire a Lua event script.
    Returns dict from the Lua JSON output, or a fallback dict if Lua not available.
    """
    if not LUA_BIN or not os.path.exists(LUA_SCRIPT):
        return _fallback(event, room_id, extra)

    try:
        result = subprocess.run(
            [LUA_BIN, LUA_SCRIPT, "quests.json", event, room_id, extra],
            capture_output=True, text=True, timeout=3,
            cwd=BASE
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except Exception:
        pass
    return _fallback(event, room_id, extra)


def _fallback(event: str, room_id: str, extra: str) -> dict:
    """Used when Lua runtime is not installed."""
    flavours = {
        "room_enter":     "You step into the room.",
        "puzzle_attempt": "Wrong. Try again.",
        "puzzle_solve":   "It opens.",
        "game_over":      "Vault Zero locks down.",
        "escape":         "You escape with the drive.",
    }
    return {
        "event":   event,
        "room":    room_id,
        "flavour": flavours.get(event, ""),
        "ok":      True,
        "source":  "python_fallback",
    }
