"""
c_bridge.py — Python ctypes wrapper around questhash.so
Language: Python  |  Calls: C (questhash.so)
This is the Python ↔ C interface — the 5th language bridge.
"""
import ctypes, os, hashlib

BASE = os.path.dirname(os.path.abspath(__file__))
_LIB = None

def _load():
    global _LIB
    if _LIB is not None:
        return _LIB
    candidates = [
        os.path.join(BASE, "questhash.so"),
        os.path.join(BASE, "questhash.dll"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                lib = ctypes.CDLL(path)
                # hash_puzzle_id(room, puzzle) -> uint32
                lib.hash_puzzle_id.restype  = ctypes.c_uint32
                lib.hash_puzzle_id.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                # verify_code(input, answer) -> int
                lib.verify_code.restype  = ctypes.c_int
                lib.verify_code.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                # get_run_token(username, elapsed, buf, buf_len) -> void
                lib.get_run_token.restype  = None
                lib.get_run_token.argtypes = [
                    ctypes.c_char_p, ctypes.c_uint32,
                    ctypes.c_char_p, ctypes.c_int
                ]
                _LIB = lib
                return _LIB
            except Exception:
                pass
    return None

# ── Public API ────────────────────────────────────────────────────────────────

def puzzle_hash(room_id: str, puzzle_key: str) -> str:
    """Return 8-char hex ID for a puzzle event (via C). Falls back to Python."""
    lib = _load()
    if lib:
        h = lib.hash_puzzle_id(room_id.encode(), puzzle_key.encode())
        return f"{h:08x}"
    # Python fallback
    raw = hashlib.sha256(f"{room_id}:{puzzle_key}".encode()).hexdigest()
    return raw[:8]

def run_token(username: str, elapsed: int) -> str:
    """Generate a unique run token (via C). Falls back to Python."""
    lib = _load()
    if lib:
        buf = ctypes.create_string_buffer(64)
        lib.get_run_token(username.encode(), ctypes.c_uint32(elapsed), buf, 64)
        return buf.value.decode()
    return f"py-{abs(hash(username+str(elapsed))):08x}"

def verify_code(code: str, answer: str) -> bool:
    """Case-insensitive code check (via C). Falls back to Python."""
    lib = _load()
    if lib:
        return bool(lib.verify_code(code.encode(), answer.encode()))
    return code.strip().lower() == answer.strip().lower()

def c_available() -> bool:
    return _load() is not None
