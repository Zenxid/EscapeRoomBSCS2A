"""
lua_bridge.py — Python → Lua → C bridge
Language: Python  |  Calls: events.lua (Lua) + questhash.dll/.so (C)

Windows-aware: checks C:\Lua\bin and MSYS2 paths directly
because shutil.which() on Windows sometimes misses newly-added PATH entries
if the terminal session started before PATH was updated.
"""
import subprocess, json, os, shutil, ctypes, platform, sys

BASE   = os.path.dirname(os.path.abspath(__file__))
IS_WIN = platform.system() == "Windows"

# ── Lua binary search ─────────────────────────────────────────────────────────
def _find_lua() -> str | None:
    # shutil.which candidates (works when PATH is correctly refreshed)
    which_names = (
        ["lua.exe", "lua54.exe", "lua5.4.exe", "lua53.exe",
         "lua5.3.exe", "luajit.exe", "lua"]
        if IS_WIN else
        ["lua", "lua5.4", "lua5.3", "lua5.1", "luajit"]
    )
    for name in which_names:
        found = shutil.which(name)
        if found:
            return found

    # Windows hard-coded fallbacks — cover common install locations
    if IS_WIN:
        hardcoded = [
            r"C:\Lua\bin\lua.exe",
            r"C:\Lua\bin\lua54.exe",
            r"C:\Lua\bin\lua5.4.exe",
            r"C:\Lua\bin\lua53.exe",
            r"C:\Lua\bin\lua5.3.exe",
            r"C:\Lua\lua.exe",
            r"C:\Lua\lua54.exe",
            r"C:\msys64\ucrt64\bin\lua.exe",
            r"C:\msys64\mingw64\bin\lua.exe",
            r"C:\msys64\usr\bin\lua.exe",
            r"C:\tools\lua\lua.exe",
            r"C:\ProgramData\chocolatey\bin\lua.exe",
        ]
        # Also scan C:\Lua\bin for any .exe that starts with "lua"
        for lua_dir in [r"C:\Lua\bin", r"C:\Lua"]:
            if os.path.isdir(lua_dir):
                for fname in os.listdir(lua_dir):
                    if fname.lower().startswith("lua") and fname.lower().endswith(".exe"):
                        hardcoded.insert(0, os.path.join(lua_dir, fname))

        for p in hardcoded:
            if os.path.isfile(p):
                return p
    return None


# ── C compiler search ─────────────────────────────────────────────────────────
def _find_gcc() -> str | None:
    which_names = (
        ["gcc.exe", "gcc", "cc.exe", "clang.exe", "cl.exe"]
        if IS_WIN else
        ["gcc", "cc", "clang"]
    )
    for name in which_names:
        found = shutil.which(name)
        if found:
            return found

    if IS_WIN:
        hardcoded = [
            r"C:\msys64\ucrt64\bin\gcc.exe",
            r"C:\msys64\mingw64\bin\gcc.exe",
            r"C:\msys64\usr\bin\gcc.exe",
            r"C:\mingw64\bin\gcc.exe",
            r"C:\MinGW\bin\gcc.exe",
            r"C:\Program Files\mingw-w64\x86_64-8.1.0-posix-seh-rt_v6-rev0\mingw64\bin\gcc.exe",
            r"C:\ProgramData\chocolatey\bin\gcc.exe",
        ]
        for p in hardcoded:
            if os.path.isfile(p):
                return p
    return None


# ── Auto-compile questhash.c → .dll/.so ──────────────────────────────────────
def _try_compile() -> str | None:
    src = os.path.join(BASE, "questhash.c")
    out = os.path.join(BASE, "questhash.dll" if IS_WIN else "questhash.so")

    if not os.path.exists(src):
        return None
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src):
        return out   # already up to date

    gcc = _find_gcc()
    if not gcc:
        return None

    cmd = [gcc, "-O2", "-shared", "-fPIC", "-o", out, src]
    if IS_WIN:
        # On Windows with MinGW/MSYS2 we also need -lm sometimes
        cmd = [gcc, "-O2", "-shared", "-o", out, src]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=30, cwd=BASE)
        if r.returncode == 0 and os.path.exists(out):
            return out
    except Exception:
        pass
    return None


# ── Load shared library ───────────────────────────────────────────────────────
_lib       = None
_lib_tried = False   # only try once per session

def _get_lib():
    global _lib, _lib_tried
    if _lib is not None:
        return _lib
    if _lib_tried:
        return None
    _lib_tried = True

    # Look for pre-compiled first, then try to compile
    candidates = [
        os.path.join(BASE, "questhash.dll"),
        os.path.join(BASE, "questhash.so"),
    ]
    lib_path = next((p for p in candidates if os.path.exists(p)), None)
    if not lib_path:
        lib_path = _try_compile()
    if not lib_path:
        return None

    try:
        lib = ctypes.CDLL(lib_path)
        lib.hash_puzzle_id.restype   = ctypes.c_uint32
        lib.hash_puzzle_id.argtypes  = [ctypes.c_char_p, ctypes.c_char_p]
        lib.hash_player_run.restype  = ctypes.c_uint32
        lib.hash_player_run.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        lib.verify_code.restype      = ctypes.c_int
        lib.verify_code.argtypes     = [ctypes.c_char_p, ctypes.c_char_p]
        lib.get_run_token.restype    = None
        lib.get_run_token.argtypes   = [
            ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_int
        ]
        _lib = lib
        return lib
    except Exception:
        return None


# ── Find events.lua ───────────────────────────────────────────────────────────
def _find_lua_script() -> str | None:
    candidates = [
        os.path.join(BASE, "events.lua"),            # flat root (your setup)
        os.path.join(BASE, "quests", "events.lua"),  # quests/ subfolder
        os.path.join(BASE, "scripts", "events.lua"),
    ]
    return next((p for p in candidates if os.path.exists(p)), None)


# ── Resolve at import time ────────────────────────────────────────────────────
LUA_BIN    = _find_lua()
LUA_SCRIPT = _find_lua_script()


# ── Public: status strings for boot screen ────────────────────────────────────
def lua_status() -> tuple:
    if LUA_BIN and LUA_SCRIPT:
        return True, f"Lua OK  ({LUA_BIN})  →  {os.path.basename(LUA_SCRIPT)}"
    if LUA_BIN and not LUA_SCRIPT:
        return False, "Lua runtime found but events.lua missing — place it in project root"
    if not LUA_BIN:
        msg = ("Lua not in PATH — add C:\\Lua\\bin to Windows PATH, then restart VS Code"
               if IS_WIN else
               "Lua not installed — run: sudo apt install lua5.4")
        return False, msg
    return False, "Lua: unknown error"


def c_status() -> tuple:
    lib = _get_lib()
    if lib:
        ext = "questhash.dll" if IS_WIN else "questhash.so"
        return True, f"C extension loaded OK  ({ext})"

    src = os.path.join(BASE, "questhash.c")
    if not os.path.exists(src):
        return False, "C: questhash.c not found in project folder"

    gcc = _find_gcc()
    if not gcc:
        msg = ("C: gcc not found — add C:\\msys64\\ucrt64\\bin to PATH, restart VS Code"
               if IS_WIN else
               "C: gcc not found — run: sudo apt install build-essential")
        return False, msg

    return False, f"C: compilation failed — compiler found ({gcc}) but build errored"


# ── Public: C wrappers ────────────────────────────────────────────────────────
def c_available() -> bool:
    return _get_lib() is not None

def hash_puzzle_id(room: str, puzzle: str) -> int:
    lib = _get_lib()
    if lib:
        return lib.hash_puzzle_id(room.encode(), puzzle.encode())
    h = 0x811c9dc5
    for b in f"{room}::{puzzle}".encode():
        h ^= b; h = (h * 0x01000193) & 0xFFFFFFFF
    return h

def verify_code_c(inp: str, answer: str) -> bool:
    lib = _get_lib()
    if lib:
        return bool(lib.verify_code(inp.encode(), answer.encode()))
    return inp.strip().lower() == answer.strip().lower()

def get_run_token(username: str, elapsed_s: int) -> str:
    lib = _get_lib()
    if lib:
        buf = ctypes.create_string_buffer(64)
        lib.get_run_token(username.encode(), ctypes.c_uint32(elapsed_s), buf, 64)
        return buf.value.decode()
    return f"{elapsed_s:08x}-{elapsed_s}"


# ── Public: fire Lua event ────────────────────────────────────────────────────
def fire_event(event: str, room_id: str, extra: str = "") -> dict:
    if LUA_BIN and LUA_SCRIPT:
        try:
            r = subprocess.run(
                [LUA_BIN, LUA_SCRIPT, "quests.json", event, room_id, extra],
                capture_output=True, text=True, timeout=5, cwd=BASE
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout.strip())
                data["source"] = "lua"
                return data
        except Exception:
            pass
    return _fallback(event, room_id, extra)


def _fallback(event, room_id, extra):
    flavours = {
        "room_enter":     "You step into the room.",
        "puzzle_attempt": "Wrong. Try again.",
        "puzzle_solve":   "It opens.",
        "game_over":      "Vault Zero locks down.",
        "escape":         "You escape with the drive.",
    }
    return {"event": event, "room": room_id,
            "flavour": flavours.get(event, ""),
            "ok": True, "source": "python_fallback"}