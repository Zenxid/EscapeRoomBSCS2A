"""
db.py — Vault Zero database layer
Language : Python  |  Storage: SQLite (arena.db) + game.ini + game.log
"""
import sqlite3, hashlib, secrets, os
from datetime import datetime, timedelta
from configparser import ConfigParser

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE, "arena.db")
INI_PATH = os.path.join(BASE, "game.ini")
LOG_PATH = os.path.join(BASE, "game.log")


# ── Config (INI layer) ────────────────────────────────────────────────────────
def load_config() -> ConfigParser:
    cfg = ConfigParser()
    cfg.read(INI_PATH)
    return cfg


# ── Logging (flat-file layer) ─────────────────────────────────────────────────
def game_log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a") as f:
        f.write(f"[{ts}] {msg}\n")


# ── Connection ────────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────
def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS players (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
        email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
        password_hash TEXT    NOT NULL,
        salt          TEXT    NOT NULL,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
        last_login    TEXT,
        is_active     INTEGER NOT NULL DEFAULT 1,
        total_xp      INTEGER NOT NULL DEFAULT 0,
        level         INTEGER NOT NULL DEFAULT 1,
        escapes       INTEGER NOT NULL DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        token      TEXT    PRIMARY KEY,
        player_id  INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
        created_at TEXT    NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT    NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS game_runs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id  INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
        room       TEXT    NOT NULL DEFAULT 'storage',
        elapsed_s  INTEGER,
        escaped    INTEGER NOT NULL DEFAULT 0,
        started_at TEXT    NOT NULL DEFAULT (datetime('now')),
        ended_at   TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER REFERENCES players(id) ON DELETE SET NULL,
        event     TEXT    NOT NULL,
        detail    TEXT,
        ts        TEXT    NOT NULL DEFAULT (datetime('now'))
    )""")
    conn.commit()
    conn.close()
    game_log("DB initialised — arena.db ready")


# ── Password ──────────────────────────────────────────────────────────────────
def hash_pw(password: str, salt: str = None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return h.hex(), salt

def verify_pw(password, stored_hash, salt) -> bool:
    computed, _ = hash_pw(password, salt)
    return secrets.compare_digest(computed, stored_hash)


# ── Auth ──────────────────────────────────────────────────────────────────────
def register(username: str, email: str, password: str) -> dict:
    pw_hash, salt = hash_pw(password)
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO players (username,email,password_hash,salt) VALUES (?,?,?,?)",
            (username.strip(), email.strip().lower(), pw_hash, salt)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM players WHERE username=?", (username,)).fetchone()
        conn.execute("INSERT INTO audit_log (player_id,event,detail) VALUES (?,?,?)",
                     (row["id"], "REGISTER", username))
        conn.commit()
        game_log(f"REGISTER: {username}")
        return {"ok": True, "player": dict(row)}
    except sqlite3.IntegrityError as e:
        msg = str(e)
        if "username" in msg: return {"ok": False, "error": "Username already taken."}
        if "email"    in msg: return {"ok": False, "error": "Email already registered."}
        return {"ok": False, "error": "Registration failed."}
    finally:
        conn.close()

def login(username: str, password: str) -> dict:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM players WHERE username=? AND is_active=1", (username,)
        ).fetchone()
        if not row:
            return {"ok": False, "error": "Invalid username or password."}
        if not verify_pw(password, row["password_hash"], row["salt"]):
            conn.execute("INSERT INTO audit_log (player_id,event,detail) VALUES (?,?,?)",
                         (row["id"], "LOGIN_FAIL", username))
            conn.commit()
            game_log(f"LOGIN_FAIL: {username}")
            return {"ok": False, "error": "Invalid username or password."}
        token = secrets.token_urlsafe(32)
        expires = (datetime.utcnow() + timedelta(hours=8)).isoformat()
        conn.execute("INSERT INTO sessions (token,player_id,expires_at) VALUES (?,?,?)",
                     (token, row["id"], expires))
        conn.execute("UPDATE players SET last_login=datetime('now') WHERE id=?", (row["id"],))
        conn.execute("INSERT INTO audit_log (player_id,event,detail) VALUES (?,?,?)",
                     (row["id"], "LOGIN_OK", username))
        conn.commit()
        game_log(f"LOGIN_OK: {username}")
        return {"ok": True, "token": token, "player": dict(row)}
    finally:
        conn.close()

def get_player_by_token(token: str):
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT p.* FROM players p JOIN sessions s ON s.player_id=p.id
               WHERE s.token=? AND s.expires_at>datetime('now') AND p.is_active=1""",
            (token,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ── Game runs ─────────────────────────────────────────────────────────────────
def save_run(player_id: int, elapsed_s: int, escaped: bool, last_room: str):
    conn = get_conn()
    conn.execute(
        """INSERT INTO game_runs (player_id,room,elapsed_s,escaped,ended_at)
           VALUES (?,?,?,?,datetime('now'))""",
        (player_id, last_room, elapsed_s, int(escaped))
    )
    if escaped:
        conn.execute(
            "UPDATE players SET escapes=escapes+1, total_xp=total_xp+?, level=MAX(level,?) WHERE id=?",
            (100, 2, player_id)
        )
    conn.commit()
    conn.close()
    game_log(f"RUN_SAVED: player={player_id} escaped={escaped} time={elapsed_s}s room={last_room}")

def get_leaderboard():
    conn = get_conn()
    rows = conn.execute(
        "SELECT username,level,total_xp,escapes FROM players WHERE is_active=1 ORDER BY total_xp DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
