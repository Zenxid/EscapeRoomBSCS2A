"""
questhash_bridge.py — Python ctypes interface to questhash.so (C layer)
Language : Python + C  |  The 5th programming language in the Vault Zero stack.
"""
import ctypes, os, platform, hashlib

BASE      = os.path.dirname(os.path.abspath(__file__))
_lib_name = "questhash.so" if platform.system() != "Windows" else "questhash.dll"
_lib_path = os.path.join(BASE, _lib_name)

_AVAILABLE = False
_lib = None

try:
    _lib = ctypes.CDLL(_lib_path)
    # hash_puzzle_id(room_id, puzzle_key) -> uint32
    _lib.hash_puzzle_id.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    _lib.hash_puzzle_id.restype  = ctypes.c_uint32
    # verify_code(input, answer) -> int
    _lib.verify_code.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    _lib.verify_code.restype  = ctypes.c_int
    # get_run_token(username, elapsed, buf, buf_len) -> void
    _lib.get_run_token.argtypes = [
        ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_int
    ]
    _lib.get_run_token.restype = None
    _AVAILABLE = True
except OSError:
    _AVAILABLE = False


def quest_hash(room_id: str, puzzle_key: str, attempt: int = 0) -> str:
    if _AVAILABLE:
        h = _lib.hash_puzzle_id(room_id.encode(), puzzle_key.encode())
        return f"{h:08x}"
    raw = hashlib.sha256(f"{room_id}:{puzzle_key}:{attempt}".encode()).hexdigest()
    return raw[:8]

def validate_code(input_code: str, expected: str, salt: str = "vault-zero") -> bool:
    if _AVAILABLE:
        return bool(_lib.verify_code(input_code.encode(), expected.encode()))
    return input_code.strip().lower() == expected.strip().lower()

def room_index(room_id: str) -> int:
    order = ["storage","lab","server","vault"]
    return order.index(room_id) if room_id in order else -1

def xor_encrypt(data: bytes, key: str) -> bytes:
    k = key.encode()
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))

def is_available() -> bool:
    return _AVAILABLE