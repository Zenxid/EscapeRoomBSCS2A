"""
main.py — Vault Zero  (entry point)
Language : Python (PyQt6)

Flow:
  BootSequence  →  LoginScreen  →  MainMenu  →  GameScreen
                                                  mode = CLI | GUI | MIXED

GameScreen respects chosen mode:
  CLI   → full-width terminal only (CLI panel, no GUI panel)
  GUI   → full-width GUI only (no CLI input panel)
  MIXED → QSplitter: CLI left, GUI right (default 50/50)
"""

import sys, re, time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFrame,
    QProgressBar, QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui  import (
    QFont, QColor, QTextCharFormat, QTextCursor, QPalette,
    QPainter, QPen, QBrush,
)

from db          import init_db, register, login, save_run, get_leaderboard, game_log
from game_engine import GameEngine
from lua_bridge  import fire_event
from game_data   import ROOMS, export_quests_json
from main_menu   import MainMenu
from c_bridge    import puzzle_hash, run_token, c_available, verify_code
import audio
from icon_gen    import load_qt_icon

# ── Shared palette ────────────────────────────────────────────────────────────
C = {
    "bg":     "#0a0907", "bg2": "#110f0c", "bg3": "#181410", "bg4": "#1e1a14",
    "border": "#2a2318", "border2": "#3a3020", "border3": "#4a4030",
    "text":   "#c9b99a", "text2": "#8a7a65", "text3": "#5a4e3e",
    "gold":   "#d4a853", "gold2": "#a07830",
    "green":  "#4a8a4a", "red": "#aa4a4a", "amber": "#9a7a2a",
    "teal":   "#3a7a7a", "dim": "#5a4e3e",
}

STYLE_MAP = {
    "normal": C["text"],  "system": C["green"], "error": C["red"],
    "warn":   C["amber"], "gold":   C["gold"],  "dim":   C["dim"],
}

BASE_STYLE = f"""
QWidget   {{ background:{C['bg']}; color:{C['text']}; }}
QFrame    {{ background:{C['bg2']}; border:0px; }}
QLineEdit {{ background:{C['bg3']}; color:{C['text']};
             border:1px solid {C['border2']}; border-radius:4px; padding:6px 10px; }}
QLineEdit:focus {{ border:1px solid {C['gold2']}; }}
QScrollBar:vertical {{ background:{C['bg2']}; width:6px; }}
QScrollBar::handle:vertical {{ background:{C['border2']}; border-radius:3px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QProgressBar {{ background:{C['bg3']}; border:1px solid {C['border']};
                border-radius:3px; text-align:center; color:{C['text']}; }}
QProgressBar::chunk {{ background:{C['green']}; }}
"""

def _btn(text, color=None, border=None, size=11):
    c = color or C["text2"]; b = border or C["border2"]
    btn = QPushButton(text)
    btn.setFont(QFont("Courier New", size))
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{c};border:1px solid {b};"
        f"border-radius:4px;padding:7px 14px;}}"
        f"QPushButton:hover{{background:{C['bg4']};color:{C['gold']};border-color:{C['border3']};}}"
        f"QPushButton:pressed{{background:{C['bg3']};}}"
        f"QPushButton:disabled{{color:{C['dim']};border-color:{C['border']};}}"
    )
    return btn


# ═════════════════════════════════════════════════════════════════════════════
# BOOT SEQUENCE SCREEN
# ═════════════════════════════════════════════════════════════════════════════
class BootSequence(QWidget):
    finished = pyqtSignal()

    def _build_boot_lines(self):
        """
        Build boot lines at runtime using lua_bridge.lua_status() and
        lua_bridge.c_status() — both probe the filesystem live so the
        boot screen always reflects the actual state on this machine.
        """
        from lua_bridge import lua_status, c_status

        lua_ok,  lua_msg = lua_status()
        c_ok,    c_msg   = c_status()

        lua_line = (C["green"] if lua_ok else C["amber"], f"[boot] {lua_msg}")
        c_line   = (C["green"] if c_ok   else C["amber"], f"[boot] {c_msg}")

        return [
            (C["dim"],   "[boot] reading game.ini ..."),
            (C["green"], "[boot] game.ini OK"),
            (C["dim"],   f"[boot] Python engine v{sys.version.split()[0]} starting ..."),
            (C["green"], "[boot] Python OK"),
            (C["dim"],   "[boot] Lua scripting engine ..."),
            lua_line,
            (C["dim"],   "[boot] C extension (questhash) ..."),
            c_line,
            (C["dim"],   "[db]   connecting to arena.db ..."),
            (C["green"], "[db]   arena.db connected"),
            (C["dim"],   "[db]   exporting quests.json for Lua ..."),
            (C["green"], "[db]   quests.json written"),
            (C["gold"],  ""),
            (C["gold"],  "  VAULT ZERO — SECURE FACILITY"),
            (C["gold"],  "  BREACH DETECTED — INITIATING ESCAPE PROTOCOL"),
            (C["gold"],  ""),
        ]

    def __init__(self):
        super().__init__()
        self.BOOT_LINES = self._build_boot_lines()
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wrap = QWidget(); wrap.setMaximumWidth(560)
        wl = QVBoxLayout(wrap); wl.setSpacing(0); wl.setContentsMargins(20, 20, 20, 20)

        self._out = QTextEdit(); self._out.setReadOnly(True)
        self._out.setFont(QFont("Courier New", 12))
        self._out.setStyleSheet(
            f"background:#050403; border:1px solid {C['border']}; border-radius:6px; padding:12px;")
        self._out.setFixedHeight(320)
        wl.addWidget(self._out)

        self._bar = QProgressBar()
        self._bar.setMaximum(len(self.BOOT_LINES))
        self._bar.setValue(0); self._bar.setFixedHeight(4); self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            f"QProgressBar{{background:{C['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{C['gold']};}}")
        wl.addSpacing(8); wl.addWidget(self._bar)

        skip = _btn("[ SKIP ]", C["text3"], C["border"], 10)
        skip.clicked.connect(self._skip)
        wl.addSpacing(6); wl.addWidget(skip, alignment=Qt.AlignmentFlag.AlignRight)
        vl.addWidget(wrap)

        self._idx = 0
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(120)

    def _tick(self):
        if self._idx >= len(self.BOOT_LINES):
            self._timer.stop()
            QTimer.singleShot(400, self.finished.emit)
            return
        color, text = self.BOOT_LINES[self._idx]
        cur = self._out.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(color))
        cur.setCharFormat(fmt); cur.insertText(text + "\n")
        self._out.setTextCursor(cur); self._out.ensureCursorVisible()
        self._bar.setValue(self._idx + 1)
        self._idx += 1

    def _skip(self):
        self._timer.stop(); self.finished.emit()


# ═════════════════════════════════════════════════════════════════════════════
# LOGIN SCREEN
# ═════════════════════════════════════════════════════════════════════════════
class LoginScreen(QWidget):
    login_success = pyqtSignal(dict, str)  # player, token

    def __init__(self):
        super().__init__()
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QWidget(); card.setMaximumWidth(420)
        card.setStyleSheet(
            f"background:{C['bg2']}; border:1px solid {C['border2']}; border-radius:10px;")
        cl = QVBoxLayout(card); cl.setContentsMargins(28, 28, 28, 28); cl.setSpacing(0)

        # title
        t = QLabel("VAULT ZERO")
        t.setFont(QFont("Georgia", 22, QFont.Weight.Bold))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"color:{C['gold']}; letter-spacing:4px; background:transparent; border:none;")
        s = QLabel("SECURE PLAYER AUTHENTICATION")
        s.setFont(QFont("Courier New", 9))
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet(f"color:{C['text3']}; letter-spacing:2px; background:transparent; border:none;")
        cl.addWidget(t); cl.addWidget(s); cl.addSpacing(20)

        # tabs
        tr = QHBoxLayout(); tr.setSpacing(0)
        self._tab_l = QPushButton("[ LOGIN ]");    self._tab_l.setCheckable(True)
        self._tab_r = QPushButton("[ REGISTER ]"); self._tab_r.setCheckable(True)
        tab_ss = (f"QPushButton{{background:transparent;color:{C['text3']};border:none;"
                  f"border-bottom:2px solid transparent;padding:8px 20px;"
                  f"font-family:'Courier New';font-size:11px;}}"
                  f"QPushButton:checked{{color:{C['gold']};border-bottom:2px solid {C['gold']};}}")
        for tb in (self._tab_l, self._tab_r):
            tb.setStyleSheet(tab_ss)
        self._tab_l.setChecked(True)
        self._tab_l.clicked.connect(lambda: self._switch(False))
        self._tab_r.clicked.connect(lambda: self._switch(True))
        tr.addWidget(self._tab_l); tr.addWidget(self._tab_r)
        cl.addLayout(tr); cl.addSpacing(2)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C['border']}; background:{C['border']};")
        cl.addWidget(sep); cl.addSpacing(14)

        # banner
        self._banner = QLabel(""); self._banner.setWordWrap(True)
        self._banner.setStyleSheet("font-size:12px;padding:8px;border-radius:4px;background:transparent;border:none;")
        self._banner.hide(); cl.addWidget(self._banner)

        # login form
        self._lf = QWidget(); self._lf.setStyleSheet("background:transparent;border:none;")
        ll = QVBoxLayout(self._lf); ll.setContentsMargins(0,0,0,0); ll.setSpacing(10)
        self._lu = self._field(ll, "USERNAME", "your_handle")
        self._lp = self._field(ll, "PASSWORD", "••••••••", True)
        lb = _btn("[ ENTER VAULT ]", C["gold"], C["gold2"], 12)
        lb.clicked.connect(self._do_login); ll.addSpacing(4); ll.addWidget(lb)
        self._lb = lb; cl.addWidget(self._lf)

        # register form
        self._rf = QWidget(); self._rf.setStyleSheet("background:transparent;border:none;")
        rl = QVBoxLayout(self._rf); rl.setContentsMargins(0,0,0,0); rl.setSpacing(10)
        self._ru  = self._field(rl, "USERNAME", "3-20 chars, letters/numbers/_")
        self._re  = self._field(rl, "EMAIL", "you@example.com")
        self._rp  = self._field(rl, "PASSWORD", "min 8 characters", True)
        self._rp2 = self._field(rl, "CONFIRM PASSWORD", "repeat password", True)
        rb = _btn("[ CREATE ACCOUNT ]", C["gold"], C["gold2"], 12)
        rb.clicked.connect(self._do_register); rl.addSpacing(4); rl.addWidget(rb)
        self._rb = rb; self._rf.hide(); cl.addWidget(self._rf)

        # cli log
        self._log = QTextEdit(); self._log.setReadOnly(True)
        self._log.setFont(QFont("Courier New", 10)); self._log.setMaximumHeight(80)
        self._log.setStyleSheet(f"background:#050403;border:1px solid {C['border']};border-radius:4px;")
        cl.addSpacing(10); cl.addWidget(self._log)

        ft = QLabel("db: arena.db  |  lang: python · sql · lua · bash · c")
        ft.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ft.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;border:none;")
        cl.addSpacing(6); cl.addWidget(ft)

        # Exit button — always visible on the login screen
        cl.addSpacing(6)
        exit_btn = _btn("[ EXIT VAULT ZERO ]", C["red"], C["red"], 10)
        exit_btn.clicked.connect(QApplication.quit)
        cl.addWidget(exit_btn)

        vl.addWidget(card)
        self._clog(C["green"], "[boot] auth system ready")

    def clear_fields(self):
        """Clear all login and register fields — called on logout."""
        self._lu.clear()
        self._lp.clear()
        self._ru.clear()
        self._re.clear()
        self._rp.clear()
        self._rp2.clear()
        self._banner.hide()
        self._switch(False)   # reset to login tab
        self._clog(C["dim"], "[logout] session cleared")

    def _field(self, layout, lbl_text, ph, pw=False):
        lbl = QLabel(lbl_text)
        lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;letter-spacing:1px;background:transparent;border:none;")
        inp = QLineEdit(); inp.setPlaceholderText(ph)
        if pw: inp.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(lbl); layout.addWidget(inp)
        return inp

    def _switch(self, show_reg: bool):
        self._tab_l.setChecked(not show_reg); self._tab_r.setChecked(show_reg)
        self._lf.setVisible(not show_reg); self._rf.setVisible(show_reg)
        self._banner.hide()

    def _banner_show(self, msg, ok=True):
        bg = "#0e1e0e" if ok else "#1e0e0e"
        bdr= "#2a4a2a" if ok else "#4a2a2a"
        col= C["green"] if ok else C["red"]
        self._banner.setStyleSheet(
            f"font-size:12px;padding:8px;border-radius:4px;background:{bg};border:1px solid {bdr};color:{col};")
        self._banner.setText(msg); self._banner.show()

    def _clog(self, color, msg):
        cur = self._log.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(color))
        cur.setCharFormat(fmt); cur.insertText(msg + "\n")
        self._log.setTextCursor(cur); self._log.ensureCursorVisible()

    def _do_login(self):
        u = self._lu.text().strip(); p = self._lp.text()
        if not u or not p: self._banner_show("Username and password required.", False); return
        self._lb.setEnabled(False); self._lb.setText("[ AUTHENTICATING... ]")
        self._clog(C["dim"], f"[login] authenticating {u} ...")
        result = login(u, p)
        if result["ok"]:
            self._clog(C["green"], "[login] OK — session token issued")
            self.login_success.emit(result["player"], result["token"])
        else:
            self._banner_show(result["error"], False)
            self._clog(C["red"], f"[login] FAIL: {result['error']}")
        self._lb.setEnabled(True); self._lb.setText("[ ENTER VAULT ]")

    def _do_register(self):
        u  = self._ru.text().strip(); e = self._re.text().strip()
        p  = self._rp.text();         p2= self._rp2.text()
        if len(u) < 3: self._banner_show("Username: 3+ characters.", False); return
        if not re.match(r"^[A-Za-z0-9_]{3,20}$", u):
            self._banner_show("Username: letters, numbers, underscore only.", False); return
        if "@" not in e: self._banner_show("Enter a valid email.", False); return
        if len(p) < 8:   self._banner_show("Password: 8+ characters.", False); return
        if p != p2:       self._banner_show("Passwords do not match.", False); return
        self._rb.setEnabled(False); self._rb.setText("[ CREATING... ]")
        result = register(u, e, p)
        if result["ok"]:
            self._banner_show("Account created! You can now log in.", True)
            self._clog(C["green"], f"[register] account created: {u}")
            QTimer.singleShot(1200, lambda: self._switch(False))
        else:
            self._banner_show(result["error"], False)
        self._rb.setEnabled(True); self._rb.setText("[ CREATE ACCOUNT ]")


# ═════════════════════════════════════════════════════════════════════════════
# PUZZLE INPUT WIDGET (embedded in GUI panel)
# ═════════════════════════════════════════════════════════════════════════════
class PuzzleWidget(QFrame):
    submitted  = pyqtSignal(str, str)  # puzzle_key, code
    cancelled  = pyqtSignal()

    def __init__(self, puzzle_key: str, puzzle: dict, difficulty: str = "normal"):
        super().__init__()
        self.puzzle_key = puzzle_key
        self.setStyleSheet(
            f"QFrame{{background:{C['bg3']};border:1px solid {C['border2']};border-radius:8px;}}")
        vl = QVBoxLayout(self); vl.setContentsMargins(14, 14, 14, 14); vl.setSpacing(8)

        # Title row with difficulty badge
        title_row = QHBoxLayout()
        title = QLabel(f"UNLOCK: {puzzle['label'].upper()}")
        title.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C['gold']};background:transparent;border:none;")
        title_row.addWidget(title)
        title_row.addStretch()
        from game_data import DIFFICULTIES
        diff_data = DIFFICULTIES.get(difficulty, DIFFICULTIES["normal"])
        diff_badge = QLabel(f"[ {diff_data['label']} ]")
        diff_badge.setFont(QFont("Courier New", 9))
        diff_badge.setStyleSheet(
            f"color:{diff_data['color']};background:transparent;border:none;")
        title_row.addWidget(diff_badge)
        vl.addLayout(title_row)

        # Hint — respects difficulty level
        from game_data import get_hint
        hint_level = diff_data.get("hint_level", "partial")
        hint_text  = get_hint(puzzle, hint_level)

        hint_frame = QFrame()
        hint_frame.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:4px;}}")
        hfl = QVBoxLayout(hint_frame)
        hfl.setContentsMargins(8, 6, 8, 6); hfl.setSpacing(0)

        if hint_level == "none":
            # Nightmare — show lock icon, no text
            no_hint = QLabel("🔒  No hints on Nightmare mode.")
            no_hint.setFont(QFont("Courier New", 10))
            no_hint.setStyleSheet(
                f"color:{diff_data['color']};background:transparent;")
            no_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hfl.addWidget(no_hint)
        else:
            hint_lbl = QLabel(hint_text)
            hint_lbl.setFont(QFont("Courier New", 10))
            hint_lbl.setWordWrap(True)
            hint_lbl.setStyleSheet(f"color:{C['text2']};background:transparent;")
            hfl.addWidget(hint_lbl)
        vl.addWidget(hint_frame)

        self._inp = QLineEdit()
        self._inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inp.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        self._inp.setPlaceholderText("_ _ _ _")
        self._inp.setMaxLength(puzzle.get("length", 6))
        self._inp.setStyleSheet(
            f"background:{C['bg2']};color:{C['gold']};border:1px solid {C['gold2']};"
            f"border-radius:4px;padding:8px;letter-spacing:6px;")
        self._inp.returnPressed.connect(self._submit)
        vl.addWidget(self._inp)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            f"color:{C['red']};font-size:12px;background:transparent;border:none;")
        vl.addWidget(self._status)

        br = QHBoxLayout()
        cancel = _btn("Cancel", C["text3"], C["border"], 10)
        submit = _btn("[ SUBMIT ]", C["gold"], C["gold2"], 11)
        cancel.clicked.connect(self.cancelled.emit)
        submit.clicked.connect(self._submit)
        br.addWidget(cancel); br.addWidget(submit)
        vl.addLayout(br)
        QTimer.singleShot(50, self._inp.setFocus)

    def _submit(self):
        code = self._inp.text().strip()
        if code: self.submitted.emit(self.puzzle_key, code)

    def set_wrong(self):
        self._status.setText("✗  Wrong code — try again")
        self._inp.selectAll(); self._inp.setFocus()

    def set_correct(self):
        self._status.setStyleSheet(
            f"color:{C['green']};font-size:12px;background:transparent;border:none;")
        self._status.setText("✓  Correct!")


# ═════════════════════════════════════════════════════════════════════════════
# GAME SCREEN  (mode-aware: CLI | GUI | MIXED)
# ═════════════════════════════════════════════════════════════════════════════
# ROOM_ART kept for reference; GUI now uses RoomArtWidget (QPainter)
ROOM_ART = {
    "storage": (
        "┌──────────────────────────────────────────┐\n"
        "│ [SHELF]  [SHELF]  [SHELF]  │  [CABINET]  │\n"
        "│  rope    toolbox   log     │  ████████   │\n"
        "│  ====    [148?]   scroll   │  top:LOCK   │\n"
        "│                           │             │\n"
        "│     [  WORKBENCH  ]        └─────────────┤\n"
        "│      papers/diagram        ▓DOOR▓ [KEY?] │\n"
        "└─────────────────── [GRATE] ──────────────┘"
    ),
    "lab": (
        "┌──────────────────────────────────────────┐\n"
        "│ [LAB BENCH]           │  [SERVER RACK]   │\n"
        "│  beakers: 3,9,5       │  ● ● ○ ●  A      │\n"
        "│  flask 7-ALPHA ✦      │  ● ○ ● ●  B      │\n"
        "│                       │                  │\n"
        "│  [WHITEBOARD]         │  [SPECIMEN CAB]  │\n"
        "│   V = R × I           │  R B G Y W vials │\n"
        "└───────────────────────┴──────[DOOR]──────┘"
    ),
    "server": (
        "┌──────────────────────────────────────────┐\n"
        "│ [RACK A]      [RACK B]   │  [TERMINAL]   │\n"
        "│  α ● BETA ●   ①●  ②○    │  LOGIN:       │\n"
        "│  γ ○ DELT ●   ③●  ④●    │  pwd = ??     │\n"
        "│  1101=13      1011=11    │  ██████████   │\n"
        "│                                          │\n"
        "│  [CORK BOARD: notes pinned]   [WIRING]   │\n"
        "└──────────────────────────────[VAULT]─────┘"
    ),
    "vault": (
        "┌──────────────────────────────────────────┐\n"
        "│  [001][002][003]...[200]  DEPOSIT BOXES  │\n"
        "│                                          │\n"
        "│         ┌──────────────────┐             │\n"
        "│         │  STEEL BRIEFCASE │  ← OPEN ME  │\n"
        "│         │    [ _ _ _ _ ]   │             │\n"
        "│         └──────────────────┘             │\n"
        "│  ◉ cam           clock: ??:??    ◉ cam   │\n"
        "└──────────────────────────────────────────┘"
    ),
}



# ═════════════════════════════════════════════════════════════════════════════
# DYNAMIC ROOM ART WIDGET  (QPainter — redraws based on game state)
# ═════════════════════════════════════════════════════════════════════════════
class RoomArtWidget(QWidget):
    """
    Draws room art dynamically using QPainter.
    Objects change appearance when examined/solved — state is pulled
    from the GameEngine on every repaint.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self._room_id  = "storage"
        self._engine   = None   # set after build

    def set_state(self, room_id: str, engine):
        self._room_id = room_id
        self._engine  = engine
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(C["bg3"]))
        draw = getattr(self, f"_draw_{self._room_id}", self._draw_default)
        draw(p)
        p.end()

    def _col(self, key): return QColor(C.get(key, C["text2"]))

    def _solved(self, puzzle_key):
        if not self._engine: return False
        return puzzle_key in self._engine.solved.get(self._room_id, [])

    def _has(self, item_key):
        if not self._engine: return False
        return any(i["key"] == item_key for i in self._engine.inventory)

    # ── Storage Room ───────────────────────────────────────────────────────────
    def _draw_storage(self, p):
        W, H = self.width(), self.height()
        # Background floor/wall
        p.setPen(QPen(self._col("border"), 1))
        p.drawRect(10, 10, W-20, H-20)

        # ── SHELVES (west wall) ────────────────────────────────────────────────
        shelf_x, shelf_y, shelf_w, shelf_h = 20, 15, 55, H-25
        p.fillRect(shelf_x, shelf_y, shelf_w, shelf_h, QColor(C["bg4"]))
        p.setPen(QPen(self._col("border2"), 1))
        p.drawRect(shelf_x, shelf_y, shelf_w, shelf_h)

        # shelf dividers
        for sy in [shelf_y + shelf_h//3, shelf_y + 2*shelf_h//3]:
            p.drawLine(shelf_x, sy, shelf_x+shelf_w, sy)

        # Rope (top shelf) — grey if taken
        rope_col = self._col("dim") if self._has("rope") else self._col("teal")
        p.setPen(QPen(rope_col, 2))
        cx = shelf_x + 14
        for i in range(3):
            p.drawEllipse(cx + i*4, shelf_y+6, 8, 6)
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(rope_col))
        p.drawText(shelf_x+2, shelf_y+20, "ROPE")

        # Toolbox (mid shelf) — gold if solved, else amber
        tb_col = self._col("green") if self._solved("toolbox") else self._col("gold")
        tb_y   = shelf_y + shelf_h//3 + 4
        p.fillRect(shelf_x+8, tb_y, 38, 18, QColor(C["bg2"]))
        p.setPen(QPen(tb_col, 1))
        p.drawRect(shelf_x+8, tb_y, 38, 18)
        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(tb_col))
        p.drawText(shelf_x+10, tb_y+8, "TOOLBOX")
        status = "OPEN" if self._solved("toolbox") else "[148?]"
        p.drawText(shelf_x+10, tb_y+16, status)

        # Log (bottom shelf)
        log_col = self._col("dim") if self._has("log") else self._col("text2")
        log_y   = shelf_y + 2*shelf_h//3 + 4
        p.setPen(QPen(log_col, 1))
        p.setFont(QFont("Courier New", 7))
        p.drawText(shelf_x+4, log_y+8, "LOG")
        p.drawText(shelf_x+4, log_y+16, "scroll")

        # ── WORKBENCH (centre) ────────────────────────────────────────────────
        wb_x = shelf_x + shelf_w + 10
        wb_w = (W - 20 - wb_x - 80) if W > 300 else 80
        wb_y = H // 2
        wb_h = H - wb_y - 15
        p.fillRect(wb_x, wb_y, wb_w, wb_h, QColor(C["bg4"]))
        p.setPen(QPen(self._col("border2"), 1))
        p.drawRect(wb_x, wb_y, wb_w, wb_h)
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(self._col("text3")))
        p.drawText(wb_x + 4, wb_y + 11, "[ WORKBENCH ]")
        p.drawText(wb_x + 4, wb_y + 21, "papers / diagram")
        p.drawText(wb_x + 4, wb_y + 31, "sticky note")

        # ── FILING CABINET (NE corner) ─────────────────────────────────────────
        cab_x = W - 90
        cab_solved = self._solved("cabinet")
        cab_col = self._col("green") if cab_solved else self._col("red")
        p.fillRect(cab_x, 15, 70, H-25, QColor(C["bg2"]))
        p.setPen(QPen(cab_col, 1))
        p.drawRect(cab_x, 15, 70, H-25)
        # drawer lines
        dh = (H-25) // 4
        for di in range(1, 4):
            p.drawLine(cab_x, 15+di*dh, cab_x+70, 15+di*dh)
        # lock indicator
        lock_label = "OPEN" if cab_solved else "top:LOCK"
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(cab_col))
        p.drawText(cab_x+4, 30, "[CABINET]")
        p.drawText(cab_x+4, 42, lock_label)
        # highlight top drawer
        if not cab_solved:
            p.fillRect(cab_x+2, 17, 66, dh-2, QColor(80, 30, 30, 60))

        # ── GRATE (floor) ─────────────────────────────────────────────────────
        gr_x = wb_x + wb_w//2 - 20
        gr_y = H - 18
        gr_col = self._col("dim") if self._solved("toolbox") else self._col("text3")
        p.setPen(QPen(gr_col, 1))
        p.drawRect(gr_x, gr_y, 40, 10)
        for gx in range(gr_x+5, gr_x+40, 8):
            p.drawLine(gx, gr_y, gx, gr_y+10)
        p.setFont(QFont("Courier New", 6))
        p.drawText(gr_x+2, gr_y+8, "GRATE")

        # ── Room label ────────────────────────────────────────────────────────
        p.setPen(QPen(self._col("text3")))
        p.setFont(QFont("Courier New", 8))
        p.drawText(W//2 - 50, H-4, "Storage Room — Level B2")

    # ── Research Lab ──────────────────────────────────────────────────────────
    def _draw_lab(self, p):
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), QColor(C["bg3"]))
        p.setPen(QPen(self._col("border"), 1))
        p.drawRect(10, 10, W-20, H-20)
        cab_solved = self._solved("specimenCabinet")

        # Lab bench (west)
        p.fillRect(18, 15, W//3, H-25, QColor(C["bg4"]))
        p.setPen(QPen(self._col("border2"), 1))
        p.drawRect(18, 15, W//3, H-25)
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(self._col("text2")))
        p.drawText(22, 28, "[ LAB BENCH ]")

        # Beakers
        for bi, (bnum, blab) in enumerate([(3,"3"),(9,"9"),(5,"5")]):
            bx = 24 + bi*22
            bc = self._col("teal") if bnum in [3,5] else self._col("text3")
            p.setPen(QPen(bc, 1))
            p.drawRect(bx, 35, 16, 22)
            p.drawLine(bx+2, 35, bx+14, 35)
            p.setFont(QFont("Courier New", 7))
            p.drawText(bx+4, 48, blab)

        # Flask
        fk_col = self._col("green")
        p.setPen(QPen(fk_col, 1))
        p.setBrush(QBrush(QColor(30, 80, 40, 100)))
        p.drawEllipse(22, 62, 18, 14)
        p.setBrush(QBrush())
        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(fk_col))
        p.drawText(22, 85, "7-ALPHA ✦")

        # Whiteboard (centre)
        wb_x = W//3 + 25
        p.fillRect(wb_x, 18, 90, 55, QColor(20, 24, 22))
        p.setPen(QPen(self._col("border2"), 1))
        p.drawRect(wb_x, 18, 90, 55)
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(self._col("text")))
        p.drawText(wb_x+4, 32, "V = R × I")
        p.setPen(QPen(self._col("amber")))
        p.drawText(wb_x+4, 44, "R=4Ω  I=2A")
        p.drawText(wb_x+4, 56, "V = 08 → ?")
        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(self._col("text3")))
        p.drawText(wb_x+4, 68, "[WHITEBOARD]")

        # Specimen cabinet (east)
        sc_col = self._col("green") if cab_solved else self._col("amber")
        sc_x = W - 95
        p.fillRect(sc_x, 15, 75, H-25, QColor(C["bg2"]))
        p.setPen(QPen(sc_col, 1))
        p.drawRect(sc_x, 15, 75, H-25)
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(sc_col))
        p.drawText(sc_x+4, 28, "SPECIMEN CAB")
        vial_colors = [C["red"], "#4a6ab0", C["green"], C["gold"], C["text"]]
        vial_labels = ["R","B","G","Y","W"]
        for vi in range(5):
            vx = sc_x + 6 + vi*13
            vy = 35
            p.fillRect(vx, vy, 10, 20, QColor(vial_colors[vi]))
            p.setPen(QPen(self._col("bg"), 1))
            p.setFont(QFont("Courier New", 6))
            p.drawText(vx+1, vy+13, vial_labels[vi])
        lock_txt = "OPEN ✓" if cab_solved else "4-digit lock"
        p.setPen(QPen(sc_col))
        p.setFont(QFont("Courier New", 7))
        p.drawText(sc_x+4, H-18, lock_txt)

        # Server rack
        sr_x = wb_x + 96
        if sr_x + 60 < sc_x - 5:
            p.fillRect(sr_x, 18, 52, 70, QColor(C["bg2"]))
            p.setPen(QPen(self._col("border2"), 1))
            p.drawRect(sr_x, 18, 52, 70)
            led_colors = [C["green"], C["green"], C["red"], C["green"]]
            for li, lc in enumerate(led_colors):
                p.fillRect(sr_x+4, 24+li*14, 8, 8, QColor(lc))
                p.setFont(QFont("Courier New", 6))
                p.setPen(QPen(self._col("text3")))
                p.drawText(sr_x+14, 31+li*14, ["α","β","γ","δ"][li])
            p.setPen(QPen(self._col("text3")))
            p.setFont(QFont("Courier New", 6))
            p.drawText(sr_x+4, H-20, "RACK")

        p.setPen(QPen(self._col("text3")))
        p.setFont(QFont("Courier New", 8))
        p.drawText(W//2-55, H-4, "Research Lab — Level B2")

    # ── Server Room ───────────────────────────────────────────────────────────
    def _draw_server(self, p):
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), QColor(C["bg3"]))
        p.setPen(QPen(self._col("border"), 1))
        p.drawRect(10, 10, W-20, H-20)
        term_solved = self._solved("terminal")

        # Rack A
        def draw_rack(rx, ry, rw, rh, leds, label):
            p.fillRect(rx, ry, rw, rh, QColor(C["bg2"]))
            p.setPen(QPen(self._col("border2"), 1))
            p.drawRect(rx, ry, rw, rh)
            row_h = rh // len(leds)
            for ri, (on, lname) in enumerate(leds):
                p.fillRect(rx+2, ry+2+ri*row_h, rw-4, row_h-3, QColor(C["bg3"]))
                led_col = C["green"] if on else C["red"]
                p.fillRect(rx+4, ry+5+ri*row_h, 8, 6, QColor(led_col))
                p.setFont(QFont("Courier New", 6))
                p.setPen(QPen(self._col("text2")))
                p.drawText(rx+14, ry+12+ri*row_h, lname)
            p.setFont(QFont("Courier New", 7))
            p.setPen(QPen(self._col("text3")))
            p.drawText(rx+4, ry+rh+10, label)

        draw_rack(18, 15, 60, H-35,
                  [(True,"ALPHA"),(True,"BETA"),(False,"GAMMA"),(True,"DELTA")],
                  "RACK A  1101=13")
        draw_rack(85, 15, 60, H-35,
                  [(True,"ROW1"),(False,"ROW2"),(True,"ROW3"),(True,"ROW4")],
                  "RACK B  1011=11")

        # Terminal
        tm_col = self._col("green") if term_solved else self._col("amber")
        tm_x = W - 145
        p.fillRect(tm_x, 15, 125, H-25, QColor(10, 14, 10))
        p.setPen(QPen(tm_col, 1))
        p.drawRect(tm_x, 15, 125, H-25)
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(tm_col))
        p.drawText(tm_x+4, 28, "ADMIN TERMINAL")
        if term_solved:
            p.setPen(QPen(self._col("green")))
            p.drawText(tm_x+4, 42, "OVERRIDE: 24")
            p.drawText(tm_x+4, 54, "VAULT CODE: 2941")
            p.drawText(tm_x+4, 66, "ACCESS GRANTED ✓")
        else:
            p.setPen(QPen(self._col("text3")))
            p.drawText(tm_x+4, 42, "LOGIN REQUIRED")
            p.drawText(tm_x+4, 54, "pwd = RA + RB")
            p.drawText(tm_x+4, 66, "13 + 11 = ???")
            # blinking cursor
            import time as _t
            if int(_t.time()*2) % 2:
                p.fillRect(tm_x+4, 72, 8, 10, QColor(C["amber"]))

        p.setPen(QPen(self._col("text3")))
        p.setFont(QFont("Courier New", 8))
        p.drawText(W//2-55, H-4, "Server Room — Level B2")

    # ── Vault ──────────────────────────────────────────────────────────────────
    def _draw_vault(self, p):
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), QColor(C["bg3"]))
        p.setPen(QPen(self._col("border"), 1))
        p.drawRect(10, 10, W-20, H-20)
        brief_solved = self._solved("briefcase")

        # Deposit boxes (walls)
        box_col = self._col("border2")
        p.setPen(QPen(box_col, 1))
        for col in range(12):
            for row in range(3):
                bx = 18 + col*18
                by = 15 + row*12
                if bx + 16 < W - 10:
                    p.fillRect(bx, by, 14, 10, QColor(C["bg4"]))
                    p.drawRect(bx, by, 14, 10)

        # Briefcase (centre table)
        bc_col = self._col("green") if brief_solved else self._col("gold")
        bfx = W//2 - 55; bfy = H//2 - 10
        p.fillRect(bfx, bfy, 110, 40, QColor(C["bg2"]))
        p.setPen(QPen(bc_col, 2))
        p.drawRect(bfx, bfy, 110, 40)
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(bc_col))
        if brief_solved:
            p.drawText(bfx+8, bfy+16, "VAULT ZERO — OPENED")
            p.drawText(bfx+8, bfy+30, "PROJECT ECHO secured ✓")
        else:
            p.drawText(bfx+8, bfy+16, "STEEL BRIEFCASE")
            # combination slots
            for si in range(4):
                sx = bfx+10+si*24
                p.fillRect(sx, bfy+22, 18, 12, QColor(C["bg3"]))
                p.setPen(QPen(bc_col, 1))
                p.drawRect(sx, bfy+22, 18, 12)
                p.setFont(QFont("Courier New", 7))
                p.drawText(sx+5, bfy+32, "_")

        # Cameras
        for cx, cy in [(18, H-22), (W-30, H-22)]:
            p.setPen(QPen(self._col("red"), 1))
            p.drawEllipse(cx, cy, 10, 8)
            p.fillRect(cx+2, cy+2, 6, 4, QColor(C["red"]))

        p.setPen(QPen(self._col("text3")))
        p.setFont(QFont("Courier New", 8))
        p.drawText(W//2-45, H-4, "Vault Zero — Classified")

    def _draw_reactor(self, p):
        W, H = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#080c08"))
        p.setPen(QPen(self._col("border"), 1))
        p.drawRect(10, 10, W-20, H-20)

        entry_solved  = self._solved("entryPanel")
        coolant_solved= self._solved("coolantValve")
        rods_solved   = self._solved("controlRods")
        full_solved   = self._solved("meltdownOverride")

        # Reactor cylinder (centre)
        cx, cy, cr = W//2, H//2, min(W,H)//5
        status_col = ("#4a8a4a" if full_solved else
                      "#4a7ab0" if rods_solved else
                      "#8a7a65" if coolant_solved else
                      "#8a6a2a")
        p.setPen(QPen(QColor(status_col), 2))
        p.setBrush(QBrush(QColor(status_col).darker(300)))
        p.drawEllipse(cx-cr, cy-cr, cr*2, cr*2)
        p.setBrush(QBrush())
        # Inner rings
        for ri in range(1,4):
            p.setPen(QPen(QColor(status_col), 1))
            p.drawEllipse(cx-cr+ri*6, cy-cr+ri*6, (cr-ri*6)*2, (cr-ri*6)*2)

        # Status text
        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(QColor(status_col)))
        status_txt = ("SHUTDOWN" if full_solved else
                      "STABLE"   if rods_solved  else
                      "COOLANT"  if coolant_solved else
                      "CRITICAL")
        p.drawText(cx - 24, cy + 4, status_txt)
        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(self._col("text3")))
        p.drawText(cx - 18, cy + 14, "412°C CORE")

        # Warning lights (corners)
        warn_col = ("#4a8a4a" if full_solved else "#d4a853" if coolant_solved else "#8a3a3a")
        for lx, ly in [(18,18),(W-28,18),(18,H-28),(W-28,H-28)]:
            p.fillRect(lx, ly, 10, 10, QColor(warn_col))
            p.setPen(QPen(self._col("border2"),1))
            p.drawRect(lx, ly, 10, 10)

        # Steam pipes (left & right)
        p.setPen(QPen(self._col("border2"), 3))
        for px in [35, 45]:
            p.drawLine(px, 20, px, H-20)
        for px in [W-35, W-45]:
            p.drawLine(px, 20, px, H-20)

        # Control rod console (east, small)
        rx = W-90; ry = H//2-25
        p.fillRect(rx, ry, 70, 50, QColor(C["bg2"]))
        p.setPen(QPen(self._col("border2"),1))
        p.drawRect(rx, ry, 70, 50)
        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(self._col("text3")))
        p.drawText(rx+4, ry+10, "CTRL RODS")
        rod_col = self._col("green") if rods_solved else self._col("amber")
        for ri in range(3):
            val = ["4","6","2"][ri] if rods_solved else "?"
            p.setPen(QPen(rod_col,1))
            p.drawRect(rx+4+ri*20, ry+16, 16, 20)
            p.setFont(QFont("Courier New",8,QFont.Weight.Bold))
            p.drawText(rx+8+ri*20, ry+29, val)

        # Coolant valve array (west, small)
        vx, vy = 18, H//2-30
        p.fillRect(vx, vy, 55, 60, QColor(C["bg2"]))
        p.setPen(QPen(self._col("border2"),1))
        p.drawRect(vx, vy, 55, 60)
        p.setFont(QFont("Courier New",6))
        p.setPen(QPen(self._col("text3")))
        p.drawText(vx+4, vy+10, "COOLANT")
        v_col = self._col("green") if coolant_solved else self._col("red")
        for vi, (vname, vpres) in enumerate([("A","4.2"),("B","1.7"),("C","8.9"),("D","3.1")]):
            p.setPen(QPen(v_col,1))
            p.setFont(QFont("Courier New",6))
            p.drawText(vx+4, vy+18+vi*10, f"{vname}:{vpres}")

        # Room label
        p.setPen(QPen(self._col("text3")))
        p.setFont(QFont("Courier New", 8))
        p.drawText(W//2-55, H-4, "Reactor Core — Level B3")

    def _draw_default(self, p):
        W, H = self.width(), self.height()
        p.setPen(QPen(self._col("text3")))
        p.setFont(QFont("Courier New", 10))
        p.drawText(W//2-40, H//2, "[ ROOM ART ]")

class GameScreen(QWidget):
    logout_requested = pyqtSignal()
    menu_requested   = pyqtSignal()

    def __init__(self, player: dict, mode: str = "mixed", difficulty: str = "normal"):
        super().__init__()
        self.player     = player
        self.mode       = mode.upper()
        self.difficulty = difficulty
        self.engine     = GameEngine(player, difficulty)
        self._active_puzzle_key = None
        self._active_puzzle_widget = None
        self._build()
        self._start_timer()
        self._enter_room()

    # ── Build ──────────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── Top bar ────────────────────────────────────────────────────────────
        topbar = QFrame(); topbar.setFixedHeight(42)
        topbar.setStyleSheet(f"background:{C['bg2']};border-bottom:1px solid {C['border']};")
        tb = QHBoxLayout(topbar); tb.setContentsMargins(12,0,12,0); tb.setSpacing(14)

        title = QLabel("VAULT ZERO")
        title.setFont(QFont("Georgia", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C['gold']};letter-spacing:2px;background:transparent;")

        mode_badge = QLabel(f"[ {self.mode} MODE ]")
        mode_badge_colors = {"CLI": C["green"], "GUI": C["gold"], "MIXED": C["teal"]}
        mode_badge.setFont(QFont("Courier New", 10))
        mode_badge.setStyleSheet(
            f"color:{mode_badge_colors.get(self.mode, C['text3'])};"
            f"background:transparent;border:none;letter-spacing:1px;")

        tb.addWidget(title); tb.addWidget(mode_badge); tb.addStretch()

        self._hud_room   = self._hud("ROOM 1/4", tb)
        self._hud_solved = self._hud("SOLVED 0/4", tb)
        self._hud_inv    = self._hud("ITEMS 0", tb)
        self._hud_timer  = QLabel("15:00")
        self._hud_timer.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._hud_timer.setStyleSheet(f"color:{C['gold']};background:transparent;")
        tb.addWidget(self._hud_timer)

        menu_btn = _btn("Menu", C["text3"], C["border"], 10)
        menu_btn.clicked.connect(self.menu_requested.emit)
        tb.addWidget(menu_btn)
        root.addWidget(topbar)

        # ── Content area (mode-dependent) ──────────────────────────────────────
        content = QWidget(); content.setStyleSheet("background:transparent;")
        cl = QHBoxLayout(content); cl.setContentsMargins(0,0,0,0); cl.setSpacing(0)

        show_cli = self.mode in ("CLI", "MIXED")
        show_gui = self.mode in ("GUI", "MIXED")

        if self.mode == "MIXED":
            splitter = QSplitter(Qt.Orientation.Horizontal)
            splitter.setHandleWidth(1)
            splitter.setStyleSheet(f"QSplitter::handle{{background:{C['border']};}}")
            splitter.addWidget(self._build_cli_panel())
            splitter.addWidget(self._build_gui_panel())
            splitter.setSizes([560, 560])
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 1)
            cl.addWidget(splitter)
        elif show_cli:
            cl.addWidget(self._build_cli_panel())
        elif show_gui:
            cl.addWidget(self._build_gui_panel())

        root.addWidget(content, 1)

        # ── Bottom bar ─────────────────────────────────────────────────────────
        botbar = QFrame(); botbar.setFixedHeight(26)
        botbar.setStyleSheet(f"background:#040302;border-top:1px solid {C['border']};")
        bb = QHBoxLayout(botbar); bb.setContentsMargins(12,0,12,0)
        self._bot_db = QLabel("db: arena.db")
        self._bot_db.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;")
        langs = QLabel("bash · python · lua · sql · c")
        langs.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;")
        bb.addWidget(self._bot_db); bb.addStretch(); bb.addWidget(langs)
        root.addWidget(botbar)

    def _hud(self, text, layout):
        l = QLabel(text); l.setFont(QFont("Courier New", 10))
        l.setStyleSheet(f"color:{C['text2']};background:transparent;")
        layout.addWidget(l); return l

    # ── CLI panel ──────────────────────────────────────────────────────────────
    def _build_cli_panel(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)
        hdr = QFrame(); hdr.setFixedHeight(28)
        hdr.setStyleSheet(f"background:{C['bg2']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(10,0,10,0)
        dot = QLabel("●"); dot.setStyleSheet(f"color:#3a6a3a;font-size:8px;background:transparent;")
        lbl = QLabel("CLI — bash/python/c layer")
        lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;letter-spacing:1px;background:transparent;")
        hl.addWidget(dot); hl.addWidget(lbl); hl.addStretch()
        vl.addWidget(hdr)

        self._cli_out = QTextEdit(); self._cli_out.setReadOnly(True)
        self._cli_out.setFont(QFont("Courier New", 12))
        self._cli_out.setStyleSheet(f"background:#050403;border:none;padding:6px;")
        vl.addWidget(self._cli_out, 1)

        hint = QLabel("  look · examine [obj] · open [obj] · use [item] on [obj] · go n · help")
        hint.setStyleSheet(f"color:{C['text3']};font-size:10px;background:#050403;padding:2px 8px;")
        vl.addWidget(hint)

        inp_f = QFrame(); inp_f.setFixedHeight(38)
        inp_f.setStyleSheet(f"background:#050403;border-top:1px solid {C['border']};")
        il = QHBoxLayout(inp_f); il.setContentsMargins(8,4,8,4); il.setSpacing(4)
        prompt = QLabel("vault>"); prompt.setFont(QFont("Courier New", 12))
        prompt.setStyleSheet(f"color:{C['green']};background:transparent;")
        self._cli_inp = QLineEdit()
        self._cli_inp.setFont(QFont("Courier New", 12))
        self._cli_inp.setStyleSheet(
            f"background:transparent;color:{C['gold']};border:none;padding:0;")
        self._cli_inp.setPlaceholderText("enter command...")
        self._cli_inp.returnPressed.connect(self._cli_submit)
        il.addWidget(prompt); il.addWidget(self._cli_inp, 1)
        vl.addWidget(inp_f)
        return w

    # ── GUI panel ──────────────────────────────────────────────────────────────
    def _build_gui_panel(self):
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)

        # Panel header — thin strip
        hdr = QFrame(); hdr.setFixedHeight(26)
        hdr.setStyleSheet(f"background:{C['bg2']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(10,0,10,0); hl.setSpacing(8)
        dot = QLabel("●"); dot.setStyleSheet(f"color:#8a6a2a;font-size:8px;background:transparent;")
        lbl = QLabel("GUI — PyQt6 layer")
        lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;letter-spacing:1px;background:transparent;")
        hl.addWidget(dot); hl.addWidget(lbl); hl.addStretch()
        self._db_lbl = QLabel("db: arena.db")
        self._db_lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;")
        hl.addWidget(self._db_lbl)
        vl.addWidget(hdr)

        # Room art — large, takes most of the panel height
        self._room_art = RoomArtWidget()
        self._room_art.setMinimumHeight(200)
        vl.addWidget(self._room_art, 3)

        # Room name — slim fixed bar, no wasted vertical space
        name_bar = QFrame(); name_bar.setFixedHeight(28)
        name_bar.setStyleSheet(
            f"background:{C['bg3']};border-top:1px solid {C['border']};"
            f"border-bottom:1px solid {C['border']};")
        nl = QHBoxLayout(name_bar); nl.setContentsMargins(12,0,12,0)
        self._room_name = QLabel()
        self._room_name.setFont(QFont("Georgia", 11, QFont.Weight.Bold))
        self._room_name.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._room_name.setStyleSheet(f"color:{C['gold']};background:transparent;")
        nl.addWidget(self._room_name)
        vl.addWidget(name_bar)

        # Room description — plain QLabel, word-wrapped, no scroll bar
        self._room_desc = QLabel()
        self._room_desc.setFont(QFont("Georgia", 11))
        self._room_desc.setWordWrap(True)
        self._room_desc.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._room_desc.setStyleSheet(
            f"color:{C['text']};background:{C['bg']};padding:10px 14px;")
        self._room_desc.setMinimumHeight(60)
        vl.addWidget(self._room_desc, 1)

        # GUI feedback — QLabel, word-wrapped, expands, no scroll
        self._gui_narr = QLabel()
        self._gui_narr.setFont(QFont("Courier New", 10))
        self._gui_narr.setWordWrap(True)
        self._gui_narr.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._gui_narr.setStyleSheet(
            f"color:{C['text2']};background:{C['bg2']};padding:8px 12px;"
            f"border-top:1px solid {C['border']};")
        self._gui_narr.setMinimumHeight(50)
        vl.addWidget(self._gui_narr, 1)

        # Puzzle area
        self._puzzle_area = QWidget()
        self._puzzle_area.setStyleSheet(
            f"background:{C['bg3']};border-top:1px solid {C['border']};")
        self._puzzle_vl = QVBoxLayout(self._puzzle_area)
        self._puzzle_vl.setContentsMargins(0,0,0,0)
        self._puzzle_area.hide()
        vl.addWidget(self._puzzle_area)

        # Action panel — scrollable, grouped, holds all GUI actions
        acts_outer = QFrame()
        acts_outer.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border-top:1px solid {C['border']};}}")
        acts_outer.setFixedHeight(160)
        ao_vl = QVBoxLayout(acts_outer); ao_vl.setContentsMargins(0,0,0,0); ao_vl.setSpacing(0)

        # Group label strip
        self._acts_group_lbl = QLabel("  ACTIONS")
        self._acts_group_lbl.setFixedHeight(20)
        self._acts_group_lbl.setFont(QFont("Courier New", 9))
        self._acts_group_lbl.setStyleSheet(
            f"color:{C['text3']};background:{C['bg3']};"
            f"padding-left:10px;border-bottom:1px solid {C['border']};")
        ao_vl.addWidget(self._acts_group_lbl)

        # Scroll area containing the button grid
        self._acts_scroll = QScrollArea()
        self._acts_scroll.setWidgetResizable(True)
        self._acts_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._acts_scroll.setStyleSheet(
            f"QScrollArea{{background:{C['bg2']};border:none;}}"
            f"QScrollBar:vertical{{background:{C['bg3']};width:5px;}}"
            f"QScrollBar::handle:vertical{{background:{C['border2']};border-radius:2px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}")

        self._acts_inner = QWidget()
        self._acts_inner.setStyleSheet(f"background:{C['bg2']};")
        self._acts_layout = QVBoxLayout(self._acts_inner)
        self._acts_layout.setContentsMargins(6,4,6,4)
        self._acts_layout.setSpacing(3)
        self._acts_scroll.setWidget(self._acts_inner)
        ao_vl.addWidget(self._acts_scroll)
        vl.addWidget(acts_outer)

        # Inventory bar — scrollable, fixed height, never widens window
        inv_f = QFrame(); inv_f.setFixedHeight(34)
        inv_f.setStyleSheet(
            f"background:{C['bg2']};border-top:1px solid {C['border']};")

        inv_outer = QHBoxLayout(inv_f)
        inv_outer.setContentsMargins(4,2,4,2); inv_outer.setSpacing(0)

        # Scroll area so items wrap horizontally without widening the frame
        self._inv_scroll = QScrollArea()
        self._inv_scroll.setWidgetResizable(True)
        self._inv_scroll.setFixedHeight(30)
        self._inv_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._inv_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._inv_scroll.setStyleSheet(
            f"QScrollArea{{background:transparent;border:none;}}"
            f"QScrollBar:horizontal{{background:{C['bg3']};height:4px;}}"
            f"QScrollBar::handle:horizontal{{background:{C['border2']};border-radius:2px;}}"
            f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0;}}")

        self._inv_inner = QWidget()
        self._inv_inner.setStyleSheet("background:transparent;")
        self._inv_layout = QHBoxLayout(self._inv_inner)
        self._inv_layout.setContentsMargins(4,0,4,0)
        self._inv_layout.setSpacing(5)
        self._inv_layout.setAlignment(Qt.AlignmentFlag.AlignLeft |
                                       Qt.AlignmentFlag.AlignVCenter)

        self._inv_scroll.setWidget(self._inv_inner)
        inv_outer.addWidget(self._inv_scroll)
        vl.addWidget(inv_f)
        return w

    # ── Timer ──────────────────────────────────────────────────────────────────
    def _start_timer(self):
        self._tmr = QTimer(self); self._tmr.timeout.connect(self._tick); self._tmr.start(1000)

    def _tick(self):
        if self.engine.finished: return
        r = self.engine.remaining; m, s = divmod(r, 60)
        self._hud_timer.setText(f"{m:02d}:{s:02d}")
        if r <= 60:
            self._hud_timer.setStyleSheet(f"color:{C['red']};background:transparent;")
        if r <= 0:
            self._tmr.stop(); self._game_over("Time expired")

    def _game_over(self, reason):
        self.engine.finished = True
        audio.on_alarm()
        audio.play_bgm("gameover", loop=False)
        fire_event("game_over", self.engine.room_id, reason)
        save_run(self.player["id"], self.engine.elapsed, False, self.engine.room_id, self.difficulty)

        # CLI output
        self._print([
            ("gold",  ""),
            ("red",   "╔══════════════════════════════════════════╗"),
            ("red",   "║       TIME EXPIRED — VAULT LOCKDOWN      ║"),
            ("red",   "║          YOU HAVE BEEN FOUND.            ║"),
            ("red",   "╚══════════════════════════════════════════╝"),
            ("dim",   ""),
            ("dim",   f"  Room reached : {self.engine.room['name']}"),
            ("dim",   f"  Time elapsed : {self.engine.elapsed}s"),
            ("dim",   "  Run saved to arena.db"),
        ])

        # HUD
        self._hud_timer.setText("FAILED")
        self._hud_timer.setStyleSheet(f"color:{C['red']};font-weight:bold;background:transparent;")

        # GUI narr overlay
        if hasattr(self, "_gui_narr"):
            self._gui_narr.setStyleSheet(
                f"background:#2a0808;color:{C['red']};border:none;"
                f"border-top:1px solid {C['red']};padding:8px 12px;")
            self._gui_narr.setText(
                "TIME EXPIRED — VAULT LOCKDOWN TRIGGERED\n\n"
                "Security doors sealed. Cameras active.\n"
                "You will be found.\n\n"
                f"Room reached: {self.engine.room['name']}\n"
                "Run saved to arena.db."
            )
        if hasattr(self, "_room_desc"):
            self._room_desc.setStyleSheet(
                f"background:#1a0808;color:{C['red']};border:none;padding:10px 14px;")
            self._room_desc.setText(
                "LOCKDOWN ACTIVE\nAll exits sealed. Security response imminent."
            )
        # Disable input
        if hasattr(self, "_cli_inp"):
            self._cli_inp.setEnabled(False)
            self._cli_inp.setPlaceholderText("VAULT LOCKED — game over")
        # Disable all action buttons in the scroll panel
        if hasattr(self, "_acts_inner"):
            for btn in self._acts_inner.findChildren(QPushButton):
                btn.setEnabled(False)

    # ── Room ───────────────────────────────────────────────────────────────────
    def _enter_room(self):
        r   = self.engine.room
        evt = fire_event("room_enter", self.engine.room_id)

        # Play room-specific BGM
        audio.play_bgm(self.engine.room_id)

        # Start reactor meltdown timer when entering reactor
        if self.engine.room_id == "reactor" and not hasattr(self, "_meltdown_tmr"):
            self._start_meltdown_timer()
            self._print([
                ("warn", ""),
                ("warn", "☢  WARNING — REACTOR MELTDOWN COUNTDOWN STARTED"),
                ("warn", "☢  8 MINUTES TO CATASTROPHIC FAILURE"),
                ("warn", "☢  Solve all reactor puzzles before time runs out"),
                ("warn", ""),
            ])

        if hasattr(self, "_room_name"):
            self._room_name.setText(r["name"])
            self._gui_narr_clear()   # fresh feedback on room enter
            desc_text = "\n".join(r["desc"])
            if evt.get("flavour"):
                desc_text += f"\n\n{evt['flavour']}"
            self._room_desc.setText(desc_text)
            self._room_art.set_state(self.engine.room_id, self.engine)
            db_txt = f"db: {r['db_indicator']}"
            if hasattr(self, "_db_lbl"):    self._db_lbl.setText(db_txt)
            self._bot_db.setText(db_txt)
            self._refresh_actions()
            self._refresh_inv()
            self._hide_puzzle()

        self._refresh_hud()
        out = self.engine.get_room_enter_output()
        self._print(out["lines"])

    # ── CLI ────────────────────────────────────────────────────────────────────
    def _cli_submit(self):
        raw = self._cli_inp.text().strip()
        if not raw: return
        self._cli_inp.clear()
        self._print([("dim", f"vault> "), ("gold", raw)], nl=False)
        self._println()
        # Handle special post-game commands
        if raw.lower() in ("menu", "quit", "exit", "return", "back"):
            self.menu_requested.emit()
            return
        result = self.engine.parse(raw)
        self._handle(result)

    def _print(self, lines, nl=True):
        if not hasattr(self, "_cli_out"): return
        cur = self._cli_out.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        for item in lines:
            style, text = (item[0], item[1]) if len(item)==2 else ("normal", str(item))
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(STYLE_MAP.get(style, C["text"])))
            cur.setCharFormat(fmt)
            cur.insertText(text + ("\n" if nl else ""))
        self._cli_out.setTextCursor(cur)
        self._cli_out.ensureCursorVisible()

    def _println(self): self._print([("dim", "")])

    def _gui_print(self, lines):
        """Mirror output lines to the GUI narrative QLabel (no scroll, no TextEdit)."""
        if not hasattr(self, "_gui_narr"): return
        # Collect visible lines, skip CLI-only noise
        parts = []
        for item in lines:
            style, text = (item[0], item[1]) if len(item) == 2 else ("normal", str(item))
            if not text.strip(): continue
            if style == "dim" and (text.startswith("[db]") or text.startswith("[c]")
                                   or text.startswith("Type") or text.startswith("──")):
                continue
            parts.append(text)
        if not parts: return
        # Append to existing text (keep last 6 lines to avoid label growing forever)
        current = self._gui_narr.text()
        all_lines = [l for l in current.split("\n") if l.strip()] + parts
        self._gui_narr.setText("\n".join(all_lines[-6:]))

    def _gui_narr_line(self, style: str, text: str):
        """Push a single line to the GUI narrative label."""
        self._gui_print([(style, text)])

    def _gui_narr_clear(self):
        """Clear the GUI narrative label."""
        if hasattr(self, "_gui_narr"): self._gui_narr.setText("")

    # ── Result handler ─────────────────────────────────────────────────────────
    def _handle(self, result: dict):
        self._print(result["lines"])
        # Push same feedback to GUI narr panel (so GUI button clicks show results)
        if hasattr(self, "_gui_narr"):
            self._gui_print(result["lines"])
        if result.get("state_changed"):
            self._refresh_inv(); self._refresh_hud()
            if result.get("solved_puzzle") is None:
                audio.on_item_obtained()   # item taken, not puzzle solved
            # Repaint room art to reflect new state (item taken, puzzle solved etc.)
            if hasattr(self, "_room_art"):
                self._room_art.set_state(self.engine.room_id, self.engine)
        # Always refresh actions — look_done flag may have changed (reveals take/use)
        self._refresh_actions()
        if result.get("room_changed"):
            audio.on_proceed()
            self._enter_room(); return
        if result.get("puzzle_key"):
            self._show_puzzle(result["puzzle_key"])
        if result.get("solved_puzzle"):
            pkey = result["solved_puzzle"]
            evt  = fire_event("puzzle_solve", self.engine.room_id, pkey)
            h    = puzzle_hash(self.engine.room_id, pkey)
            if hasattr(self, "_cli_out"):
                self._print([("dim", f"[c]  puzzle_id={h}")])
            if evt.get("flavour"):
                self._print([("dim", evt["flavour"])])
                self._gui_narr_line("dim", evt["flavour"])
            audio.on_room_unlock() if self.engine.room_solved() else audio.on_puzzle_correct()
            self._hide_puzzle(); self._refresh_actions()
            if hasattr(self, "_room_art"):
                self._room_art.set_state(self.engine.room_id, self.engine)
        if result.get("wrong_code"):
            fire_event("puzzle_attempt", self.engine.room_id)
            if self._active_puzzle_widget:
                self._active_puzzle_widget.set_wrong()
            audio.on_puzzle_wrong()
            self._gui_narr_line("error", "✗  Wrong code — check your clues and try again.")
        if result.get("escaped"):
            self._on_escaped()

    # ── Puzzle ─────────────────────────────────────────────────────────────────
    def _show_puzzle(self, pkey: str):
        if not hasattr(self, "_puzzle_area"): return
        self._active_puzzle_key = pkey
        puzzle = self.engine.room["puzzles"][pkey]
        while self._puzzle_vl.count():
            w = self._puzzle_vl.takeAt(0).widget()
            if w: w.deleteLater()
        pw = PuzzleWidget(pkey, puzzle, self.difficulty)
        pw.submitted.connect(self._gui_submit)
        pw.cancelled.connect(self._hide_puzzle)
        self._active_puzzle_widget = pw
        self._puzzle_vl.addWidget(pw)
        self._puzzle_area.show()

    def _hide_puzzle(self):
        if hasattr(self, "_puzzle_area"): self._puzzle_area.hide()
        self._active_puzzle_key = None; self._active_puzzle_widget = None

    def _gui_submit(self, pkey: str, code: str):
        self._print([("dim", f"vault> enter {code}")])
        # use C extension for validation
        puzzle = self.engine.room["puzzles"][pkey]
        c_match = verify_code(code, puzzle["answer"])
        result  = self.engine.submit_puzzle(pkey, code)
        self._handle(result)

    # ── Action buttons ─────────────────────────────────────────────────────────
    def _refresh_actions(self):
        if not hasattr(self, "_acts_layout"): return

        # Clear all existing items
        while self._acts_layout.count():
            item = self._acts_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        actions = self.engine.get_gui_actions()
        if not actions:
            return

        # Group actions by their "group" field
        groups = {}
        for act in actions:
            g = act.get("group", "other")
            groups.setdefault(g, []).append(act)

        GROUP_ORDER  = ["explore", "examine", "take", "use", "unlock", "navigate", "other"]
        GROUP_LABELS = {
            "explore":  "EXPLORE",
            "examine":  "EXAMINE",
            "take":     "TAKE",
            "use":      "USE",
            "unlock":   "UNLOCK",
            "navigate": "PROCEED",
            "other":    "OTHER",
        }
        GROUP_COLORS = {
            "explore":  (C["text2"],  C["border2"]),
            "examine":  (C["text2"],  C["border2"]),
            "take":     (C["teal"],   C["teal"]),
            "use":      (C["teal"],   C["teal"]),
            "unlock":   (C["amber"],  C["amber"]),
            "navigate": (C["gold"],   C["gold2"]),
            "other":    (C["text2"],  C["border2"]),
        }

        for gname in GROUP_ORDER:
            if gname not in groups:
                continue
            acts = groups[gname]

            # Group header label
            g_lbl = QLabel(f"  {GROUP_LABELS[gname]}")
            g_lbl.setFixedHeight(18)
            g_lbl.setFont(QFont("Courier New", 8))
            g_lbl.setStyleSheet(
                f"color:{C['text3']};background:{C['bg3']};"
                f"border-top:1px solid {C['border']};padding-left:4px;")
            self._acts_layout.addWidget(g_lbl)

            # Button row (wrap into rows of 2)
            btn_row = None
            btn_col_idx = 0
            COLS = 2
            for act in acts:
                if btn_col_idx % COLS == 0:
                    row_w = QWidget()
                    row_w.setStyleSheet("background:transparent;")
                    btn_row = QHBoxLayout(row_w)
                    btn_row.setContentsMargins(0,0,0,0)
                    btn_row.setSpacing(4)
                    self._acts_layout.addWidget(row_w)

                col, bdr = GROUP_COLORS.get(gname, (C["text2"], C["border2"]))
                icon  = act.get("icon", "")
                label = f"{icon}  {act['label']}" if icon else act["label"]
                btn   = _btn(label, col, bdr, 10)
                btn.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                btn.setFixedHeight(26)
                cmd = act["cmd"]
                btn.clicked.connect(lambda c=False, cm=cmd: (audio.on_button_click(), self._gui_action(cm)))
                btn_row.addWidget(btn)
                btn_col_idx += 1

            # Pad last row if odd number
            if btn_col_idx % COLS != 0:
                btn_row.addStretch()

        self._acts_layout.addStretch()

        # Update group label strip with current room
        if hasattr(self, "_acts_group_lbl"):
            room_name = self.engine.room["name"]
            n_actions = len(actions)
            self._acts_group_lbl.setText(
                f"  ACTIONS  ·  {room_name}  ·  {n_actions} available")

    def _gui_action(self, cmd: str):
        self._print([("dim","vault> "), ("gold", cmd)], nl=False); self._println()
        result = self.engine.parse(cmd)
        self._handle(result)

    # ── Inventory ──────────────────────────────────────────────────────────────
    def _refresh_inv(self):
        if not hasattr(self, "_inv_layout"): return
        # Remove all existing widgets
        while self._inv_layout.count():
            item = self._inv_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        if not self.engine.inventory:
            e = QLabel("inventory empty")
            e.setFont(QFont("Courier New", 9))
            e.setStyleSheet(
                f"color:{C['text3']};background:transparent;")
            self._inv_layout.addWidget(e)
            return

        type_colors = {
            "key":    C["gold"],
            "item":   C["green"],
            "clue":   C["teal"],
            "weapon": C["red"],
        }
        type_icons = {
            "key":    "🔑",
            "item":   "⚙",
            "clue":   "📋",
            "weapon": "⚔",
        }
        for item in self.engine.inventory:
            col  = type_colors.get(item["type"], C["text2"])
            icon = type_icons.get(item["type"],  "·")
            # Truncate long names to keep tags compact
            name = item["name"]
            if len(name) > 18:
                name = name[:16] + "…"
            tag = QLabel(f"{icon} {name}")
            tag.setFont(QFont("Courier New", 9))
            tag.setFixedHeight(22)
            tag.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            tag.setStyleSheet(
                f"color:{col};background:{C['bg3']};"
                f"border:1px solid {C['border2']};border-radius:3px;"
                f"padding:0px 6px;")
            self._inv_layout.addWidget(tag)

    # ── HUD ────────────────────────────────────────────────────────────────────
    def _refresh_hud(self):
        from game_data import ROOM_ORDER
        rooms = ROOM_ORDER   # ["storage","lab","server","vault","reactor"]
        idx   = (rooms.index(self.engine.room_id) + 1
                 if self.engine.room_id in rooms else 1)
        total_rooms   = len(rooms)
        total_puzzles = self.engine.total_puzzles
        solved_puzzles= self.engine.total_puzzles_solved
        self._hud_room.setText(f"ROOM {idx}/{total_rooms}")
        self._hud_solved.setText(f"PUZZLES {solved_puzzles}/{total_puzzles}")
        self._hud_inv.setText(f"ITEMS {len(self.engine.inventory)}")

    # ── Escaped ────────────────────────────────────────────────────────────────
    def _on_escaped(self):
        self._tmr.stop()
        audio.on_escape()
        audio.play_bgm("victory", loop=False)
        fire_event("escape", self.engine.room_id)
        tok     = run_token(self.player["username"], self.engine.elapsed)
        is_full = self.engine.room_id == "reactor"
        save_run(self.player["id"], self.engine.elapsed, True,
                 self.engine.room_id, self.difficulty)
        game_log(f"ESCAPED: {self.player['username']} full={is_full} "
                 f"time={self.engine.elapsed}s token={tok}")

        mins, secs = divmod(self.engine.elapsed, 60)
        time_str   = f"{mins:02d}:{secs:02d}"

        # ── CLI victory banner ────────────────────────────────────────────────
        if is_full:
            self._print([
                ("gold", ""),
                ("gold", "╔══════════════════════════════════════════════╗"),
                ("gold", "║   ★  VAULT ZERO — FULL COMPLETION  ★        ║"),
                ("gold", "║      Reactor secured. Facility saved.        ║"),
                ("gold", "╚══════════════════════════════════════════════╝"),
            ])
        else:
            self._print([
                ("gold", ""),
                ("gold", "╔══════════════════════════════════════════════╗"),
                ("gold", "║         VAULT ZERO — ESCAPED                ║"),
                ("gold", "╚══════════════════════════════════════════════╝"),
            ])
        self._print([
            ("gold",   f"  Time      : {time_str}"),
            ("gold",   f"  Difficulty: {self.engine.diff_cfg['label']}"),
            ("gold",   f"  Puzzles   : {self.engine.total_puzzles_solved}/{self.engine.total_puzzles}"),
            ("dim",    f"  Run token : {tok}"),
            ("dim",    ""),
            ("gold",   "─── LEADERBOARD ─────────────────────────────────"),
        ])
        lb = get_leaderboard()
        for i, row in enumerate(lb, 1):
            self._print([("normal",
                f"  {i:2}. {row['username']:<18} LV{row['level']}  {row['total_xp']} XP")])
        self._print([("gold", "─────────────────────────────────────────────────")])

        # ── HUD ───────────────────────────────────────────────────────────────
        self._hud_timer.setText("ESCAPED" if not is_full else "★ COMPLETE")
        self._hud_timer.setStyleSheet(
            f"color:{C['green']};font-weight:bold;background:transparent;")

        # ── GUI victory overlay ───────────────────────────────────────────────
        if hasattr(self, "_room_desc"):
            self._room_desc.setStyleSheet(
                f"color:{C['gold']};background:#0e1808;padding:10px 14px;")
            desc = ("★ FULL COMPLETION — Reactor shutdown. Facility saved.\n\n"
                    if is_full else
                    "ESCAPED VAULT ZERO\n\n")
            desc += (f"Time: {time_str}  ·  "
                     f"Difficulty: {self.engine.diff_cfg['label']}  ·  "
                     f"Puzzles: {self.engine.total_puzzles_solved}/{self.engine.total_puzzles}")
            self._room_desc.setText(desc)

        if hasattr(self, "_gui_narr"):
            self._gui_narr.setStyleSheet(
                f"color:{C['green']};background:#0a1a0a;padding:8px 12px;"
                f"border-top:1px solid {C['green']};")
            self._gui_narr.setText(
                "Run saved to arena.db  ·  Leaderboard updated")

        # ── Disable CLI input ─────────────────────────────────────────────────
        if hasattr(self, "_cli_inp"):
            self._cli_inp.setEnabled(False)
            self._cli_inp.setPlaceholderText("Escape complete — use the buttons below")

        # ── FINISH / PLAY AGAIN buttons in action area ────────────────────────
        if hasattr(self, "_acts_layout"):
            # clear existing buttons
            while self._acts_layout.count():
                item = self._acts_layout.takeAt(0)
                w = item.widget()
                if w: w.deleteLater()

            btn_row = QWidget(); btn_row.setStyleSheet("background:transparent;")
            bhl = QHBoxLayout(btn_row)
            bhl.setContentsMargins(8, 8, 8, 8); bhl.setSpacing(10)

            finish_btn = _btn("[ RETURN TO MENU ]", C["gold"], C["gold2"], 12)
            finish_btn.setFixedHeight(36)
            finish_btn.clicked.connect(self.menu_requested.emit)

            again_btn = _btn("[ PLAY AGAIN ]", C["green"], C["green"], 12)
            again_btn.setFixedHeight(36)
            again_btn.clicked.connect(self.menu_requested.emit)

            bhl.addWidget(finish_btn)
            bhl.addWidget(again_btn)
            self._acts_layout.addWidget(btn_row)
            # Also show finish button in CLI panel if mixed/cli mode
            self._print([
                ("dim",  ""),
                ("gold", "  [ Click RETURN TO MENU or type 'menu' to continue ]"),
            ])

    # ── Reactor meltdown secondary countdown ───────────────────────────────────
    def _start_meltdown_timer(self):
        """
        Called when entering the reactor room.
        Starts an 8-minute secondary countdown displayed as a separate
        MELTDOWN label. If it hits zero the reactor explodes — game over.
        """
        self._meltdown_secs = 480   # 8 minutes
        self._meltdown_lbl  = None

        # Find or create a meltdown label in the HUD area
        if hasattr(self, "_hud_timer"):
            # Insert meltdown indicator after the main timer in top bar
            pass   # we update _hud_timer text to show both

        self._meltdown_tmr = QTimer(self)
        self._meltdown_tmr.timeout.connect(self._meltdown_tick)
        self._meltdown_tmr.start(1000)

    def _meltdown_tick(self):
        if self.engine.finished or self.engine.room_id != "reactor":
            if hasattr(self, "_meltdown_tmr"):
                self._meltdown_tmr.stop()
            return
        self._meltdown_secs -= 1
        m, s = divmod(self._meltdown_secs, 60)

        # Override the HUD timer to show meltdown countdown in red/amber
        col = C["red"] if self._meltdown_secs <= 60 else C["amber"]
        self._hud_timer.setText(f"☢ {m:02d}:{s:02d}")
        self._hud_timer.setStyleSheet(f"color:{col};font-weight:bold;background:transparent;")

        # Flash GUI narr as warning
        if self._meltdown_secs % 30 == 0 and self._meltdown_secs > 0:
            audio.on_alarm()
            mins_left = self._meltdown_secs // 60
            self._gui_narr_line(
                "warn" if self._meltdown_secs > 60 else "error",
                f"☢  MELTDOWN IN {mins_left}m {self._meltdown_secs % 60:02d}s — SOLVE PUZZLES NOW"
            )
            self._print([("warn" if self._meltdown_secs > 60 else "error",
                          f"☢  MELTDOWN COUNTDOWN: {m:02d}:{s:02d} remaining")])

        if self._meltdown_secs <= 0:
            self._meltdown_tmr.stop()
            self._game_over("Reactor meltdown — facility destroyed")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vault Zero")

        # ── App icon ──────────────────────────────────────────────────────────
        icon = load_qt_icon()
        if icon:
            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)

        # ── Fullscreen on 720p and 1080p, maximised on larger ─────────────────
        screen = QApplication.primaryScreen()
        if screen:
            sg     = screen.availableGeometry()
            sw, sh = sg.width(), sg.height()
            if sh <= 1080:
                # 720p and 1080p — true fullscreen
                self.setWindowState(
                    Qt.WindowState.WindowFullScreen)
            else:
                # 1440p+ — maximised but not fullscreen
                self.setWindowState(
                    Qt.WindowState.WindowMaximized)
        else:
            self.resize(1280, 760)

        self.setStyleSheet(BASE_STYLE)
        self._fs = (screen and screen.availableGeometry().height() <= 1080)
        self._player = None
        self._game   = None
        self._menu   = None

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Boot → Login → Menu → Game
        self._boot  = BootSequence()
        self._boot.finished.connect(self._show_login)
        self._stack.addWidget(self._boot)

        self._login = LoginScreen()
        self._login.login_success.connect(self._on_login)
        self._stack.addWidget(self._login)

        self._stack.setCurrentWidget(self._boot)

    def keyPressEvent(self, event):
        """
        F11    = toggle fullscreen
        Escape = exit fullscreen
        M      = mute/unmute audio
        +/-    = BGM volume up/down
        """
        from PyQt6.QtCore import Qt as _Qt
        key = event.key()
        if key == _Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showMaximized()
            else:
                self.showFullScreen()
        elif key == _Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showMaximized()
        elif key == _Qt.Key.Key_M:
            muted = audio.toggle_mute()
            # Show mute status in title bar briefly
            self.setWindowTitle("Vault Zero  [ MUTED ]" if muted else "Vault Zero")
        elif key in (_Qt.Key.Key_Plus, _Qt.Key.Key_Equal):
            audio.set_bgm_volume(min(1.0, audio._BGM_VOL + 0.1))
        elif key == _Qt.Key.Key_Minus:
            audio.set_bgm_volume(max(0.0, audio._BGM_VOL - 0.1))
        else:
            super().keyPressEvent(event)

    def _show_login(self):
        audio.play_bgm("menu")
        self._stack.setCurrentWidget(self._login)

    def _on_login(self, player: dict, token: str):
        self._player = player
        self._show_menu()

    def _show_menu(self):
        # Always fetch fresh player data from DB before showing menu
        # so XP, escapes and level reflect the latest completed run
        from db import get_fresh_player
        fresh = get_fresh_player(self._player["id"])
        if fresh:
            self._player = fresh
        if self._menu:
            self._stack.removeWidget(self._menu); self._menu.deleteLater()
        self._menu = MainMenu(self._player)
        self._menu.play_requested.connect(self._launch_game)
        self._menu.logout_requested.connect(self._on_logout)
        self._stack.addWidget(self._menu)
        audio.play_bgm("menu")
        self._stack.setCurrentWidget(self._menu)

    def _launch_game(self, payload):
        # payload is either a mode string (legacy) or (mode, difficulty) tuple
        if isinstance(payload, tuple):
            mode, difficulty = payload
        else:
            mode, difficulty = payload, "normal"
        if self._game:
            self._stack.removeWidget(self._game); self._game.deleteLater()
        self._game = GameScreen(self._player, mode, difficulty)
        self._game.logout_requested.connect(self._on_logout)
        self._game.menu_requested.connect(self._show_menu)
        self._stack.addWidget(self._game)
        self._stack.setCurrentWidget(self._game)

    def _on_logout(self):
        if self._game:
            self._stack.removeWidget(self._game); self._game.deleteLater(); self._game = None
        if self._menu:
            self._stack.removeWidget(self._menu); self._menu.deleteLater(); self._menu = None
        self._login.clear_fields()          # wipe username/password fields
        audio.stop_bgm(400)                 # fade out music
        self._stack.setCurrentWidget(self._login)


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
def main():
    init_db()
    export_quests_json()
    game_log("Application started")
    audio.init()   # initialise pygame mixer

    app = QApplication(sys.argv)
    app.setApplicationName("Vault Zero")

    palette = QPalette()
    for role, col in [
        (QPalette.ColorRole.Window,          C["bg"]),
        (QPalette.ColorRole.WindowText,      C["text"]),
        (QPalette.ColorRole.Base,            C["bg2"]),
        (QPalette.ColorRole.AlternateBase,   C["bg3"]),
        (QPalette.ColorRole.Text,            C["text"]),
        (QPalette.ColorRole.Button,          C["bg2"]),
        (QPalette.ColorRole.ButtonText,      C["text"]),
        (QPalette.ColorRole.Highlight,       C["gold2"]),
        (QPalette.ColorRole.HighlightedText, C["bg"]),
    ]:
        palette.setColor(role, QColor(col))
    app.setPalette(palette)

    win = MainWindow(); win.show()
    ret = app.exec()
    audio.shutdown()
    sys.exit(ret)


if __name__ == "__main__":
    main()