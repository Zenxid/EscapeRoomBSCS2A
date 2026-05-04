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
    QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFrame,
    QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui  import (
    QFont, QColor, QTextCharFormat, QTextCursor, QPalette,
)

from db          import init_db, register, login, save_run, get_leaderboard, game_log
from game_engine import GameEngine
from lua_bridge  import fire_event
from game_data   import ROOMS, export_quests_json
from main_menu   import MainMenu
from c_bridge    import puzzle_hash, run_token, c_available, verify_code

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
        vl.addWidget(card)
        self._clog(C["green"], "[boot] auth system ready")

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

    def __init__(self, puzzle_key: str, puzzle: dict):
        super().__init__()
        self.puzzle_key = puzzle_key
        self.setStyleSheet(
            f"QFrame{{background:{C['bg3']};border:1px solid {C['border2']};border-radius:8px;}}")
        vl = QVBoxLayout(self); vl.setContentsMargins(14, 14, 14, 14); vl.setSpacing(8)

        title = QLabel(f"UNLOCK: {puzzle['label'].upper()}")
        title.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C['gold']};background:transparent;border:none;")
        vl.addWidget(title)

        hint = QTextEdit(); hint.setReadOnly(True)
        hint.setFont(QFont("Courier New", 10))
        hint.setPlainText(puzzle["hint"]); hint.setMaximumHeight(100)
        hint.setStyleSheet(
            f"background:{C['bg2']};color:{C['text2']};border:1px solid {C['border']};border-radius:4px;padding:6px;")
        vl.addWidget(hint)

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
        self._status.setStyleSheet(f"color:{C['red']};font-size:12px;background:transparent;border:none;")
        vl.addWidget(self._status)

        br = QHBoxLayout()
        cancel = _btn("Cancel", C["text3"], C["border"], 10)
        submit = _btn("[ SUBMIT ]", C["gold"], C["gold2"], 11)
        cancel.clicked.connect(self.cancelled.emit); submit.clicked.connect(self._submit)
        br.addWidget(cancel); br.addWidget(submit); vl.addLayout(br)
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


class GameScreen(QWidget):
    logout_requested = pyqtSignal()
    menu_requested   = pyqtSignal()

    def __init__(self, player: dict, mode: str = "MIXED"):
        super().__init__()
        self.player = player
        self.mode   = mode.upper()
        self.engine = GameEngine(player)
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
            splitter.setSizes([580, 580])
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
        hdr = QFrame(); hdr.setFixedHeight(28)
        hdr.setStyleSheet(f"background:{C['bg2']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(10,0,10,0)
        dot = QLabel("●"); dot.setStyleSheet(f"color:#8a6a2a;font-size:8px;background:transparent;")
        lbl = QLabel("GUI — PyQt6 layer")
        lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;letter-spacing:1px;background:transparent;")
        hl.addWidget(dot); hl.addWidget(lbl); hl.addStretch()
        self._db_lbl = QLabel("db: arena.db")
        self._db_lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;")
        hl.addWidget(self._db_lbl)
        vl.addWidget(hdr)

        self._room_art = QLabel()
        self._room_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._room_art.setFixedHeight(100)
        self._room_art.setFont(QFont("Courier New", 10))
        self._room_art.setStyleSheet(
            f"background:{C['bg3']};color:{C['text2']};border-bottom:1px solid {C['border']};padding:6px;")
        vl.addWidget(self._room_art)

        self._room_name = QLabel()
        self._room_name.setFont(QFont("Georgia", 12, QFont.Weight.Bold))
        self._room_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._room_name.setStyleSheet(
            f"color:{C['gold']};background:{C['bg3']};padding:6px;border-bottom:1px solid {C['border']};")
        vl.addWidget(self._room_name)

        self._room_desc = QTextEdit(); self._room_desc.setReadOnly(True)
        self._room_desc.setFont(QFont("Georgia", 11))
        self._room_desc.setStyleSheet(
            f"background:{C['bg']};color:{C['text']};border:none;padding:10px 14px;")
        self._room_desc.setMaximumHeight(95)
        vl.addWidget(self._room_desc)

        self._puzzle_area = QWidget()
        self._puzzle_area.setStyleSheet(f"background:{C['bg3']};border-top:1px solid {C['border']};")
        self._puzzle_vl = QVBoxLayout(self._puzzle_area)
        self._puzzle_vl.setContentsMargins(0,0,0,0)
        self._puzzle_area.hide()
        vl.addWidget(self._puzzle_area)

        acts_f = QFrame()
        acts_f.setStyleSheet(f"background:{C['bg2']};border-top:1px solid {C['border']};")
        self._acts_layout = QHBoxLayout(acts_f)
        self._acts_layout.setContentsMargins(8,8,8,8); self._acts_layout.setSpacing(6)
        vl.addWidget(acts_f)

        inv_f = QFrame(); inv_f.setFixedHeight(36)
        inv_f.setStyleSheet(f"background:{C['bg2']};border-top:1px solid {C['border']};")
        self._inv_layout = QHBoxLayout(inv_f)
        self._inv_layout.setContentsMargins(8,4,8,4); self._inv_layout.setSpacing(6)
        self._inv_empty = QLabel("inventory empty")
        self._inv_empty.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;")
        self._inv_layout.addWidget(self._inv_empty)
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
        fire_event("game_over", self.engine.room_id, reason)
        self._print([("red","TIME EXPIRED — VAULT LOCKDOWN"),("dim","You will be found.")])
        save_run(self.player["id"], self.engine.elapsed, False, self.engine.room_id)
        self._hud_timer.setText("FAILED")

    # ── Room ───────────────────────────────────────────────────────────────────
    def _enter_room(self):
        r   = self.engine.room
        evt = fire_event("room_enter", self.engine.room_id)

        if hasattr(self, "_room_name"):
            self._room_name.setText(r["name"])
            self._room_desc.setPlainText("\n".join(r["desc"]))
            if evt.get("flavour"):
                self._room_desc.append(f"\n{evt['flavour']}")
            self._room_art.setText(ROOM_ART.get(self.engine.room_id, ""))
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

    def _println(self): self._print([("dim","")])

    # ── Result handler ─────────────────────────────────────────────────────────
    def _handle(self, result: dict):
        self._print(result["lines"])
        if result.get("state_changed"):
            self._refresh_inv(); self._refresh_hud()
        if result.get("room_changed"):
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
            self._hide_puzzle(); self._refresh_actions()
        if result.get("wrong_code"):
            fire_event("puzzle_attempt", self.engine.room_id)
            if self._active_puzzle_widget:
                self._active_puzzle_widget.set_wrong()
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
        pw = PuzzleWidget(pkey, puzzle)
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
        while self._acts_layout.count():
            w = self._acts_layout.takeAt(0).widget()
            if w: w.deleteLater()
        actions = self.engine.get_gui_actions()
        key_labels = ["A","B","C","D","E","F","G","H"]
        col_colors = {"normal": C["text2"], "warn": C["amber"], "gold": C["gold"]}
        col_borders = {"warn": C["amber"], "gold": C["gold2"]}
        for i, act in enumerate(actions[:6]):
            kl   = key_labels[i] if i < 8 else str(i)
            col  = col_colors.get(act["style"], C["text2"])
            bdr  = col_borders.get(act["style"], C["border2"])
            btn  = _btn(f"[{kl}] {act['label']}", col, bdr, 10)
            cmd  = act["cmd"]
            btn.clicked.connect(lambda c=False, cm=cmd: self._gui_action(cm))
            self._acts_layout.addWidget(btn)
        self._acts_layout.addStretch()

    def _gui_action(self, cmd: str):
        self._print([("dim","vault> "), ("gold", cmd)], nl=False); self._println()
        result = self.engine.parse(cmd)
        self._handle(result)

    # ── Inventory ──────────────────────────────────────────────────────────────
    def _refresh_inv(self):
        if not hasattr(self, "_inv_layout"): return
        while self._inv_layout.count():
            w = self._inv_layout.takeAt(0).widget()
            if w: w.deleteLater()
        if not self.engine.inventory:
            e = QLabel("inventory empty")
            e.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;")
            self._inv_layout.addWidget(e); return
        type_colors = {"key":C["gold"],"item":C["green"],"clue":C["teal"],"weapon":C["red"]}
        for item in self.engine.inventory:
            tag = QLabel(item["name"]); tag.setFont(QFont("Courier New", 10))
            col = type_colors.get(item["type"], C["text2"])
            tag.setStyleSheet(
                f"color:{col};background:{C['bg3']};border:1px solid {C['border2']};"
                f"border-radius:3px;padding:1px 7px;")
            self._inv_layout.addWidget(tag)
        self._inv_layout.addStretch()

    # ── HUD ────────────────────────────────────────────────────────────────────
    def _refresh_hud(self):
        rooms = ["storage","lab","server","vault"]
        idx   = rooms.index(self.engine.room_id) + 1
        solved = sum(1 for rid in rooms
                     if all(p in self.engine.solved[rid] for p in ROOMS[rid]["solve_condition"]))
        self._hud_room.setText(f"ROOM {idx}/4")
        self._hud_solved.setText(f"SOLVED {solved}/4")
        self._hud_inv.setText(f"ITEMS {len(self.engine.inventory)}")

    # ── Escaped ────────────────────────────────────────────────────────────────
    def _on_escaped(self):
        self._tmr.stop()
        fire_event("escape", self.engine.room_id)
        tok = run_token(self.player["username"], self.engine.elapsed)
        save_run(self.player["id"], self.engine.elapsed, True, self.engine.room_id)
        self._hud_timer.setText("ESCAPED")
        self._hud_timer.setStyleSheet(f"color:{C['green']};background:transparent;")
        game_log(f"ESCAPED: {self.player['username']} time={self.engine.elapsed}s token={tok}")
        lb = get_leaderboard()
        self._print([("gold",""), ("gold","─── LEADERBOARD ──────────────────────────────")])
        for i, row in enumerate(lb, 1):
            self._print([("normal", f"  {i:2}. {row['username']:<20} LV{row['level']}  {row['total_xp']} XP")])
        self._print([("gold","─────────────────────────────────────────────"),
                     ("dim", f"  run token (C): {tok}")])


# ═════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vault Zero")
        self.resize(1280, 760)
        self.setStyleSheet(BASE_STYLE)
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

    def _show_login(self):
        self._stack.setCurrentWidget(self._login)

    def _on_login(self, player: dict, token: str):
        self._player = player
        self._show_menu()

    def _show_menu(self):
        if self._menu:
            self._stack.removeWidget(self._menu); self._menu.deleteLater()
        self._menu = MainMenu(self._player)
        self._menu.play_requested.connect(self._launch_game)
        self._menu.logout_requested.connect(self._on_logout)
        self._stack.addWidget(self._menu)
        self._stack.setCurrentWidget(self._menu)

    def _launch_game(self, mode: str):
        if self._game:
            self._stack.removeWidget(self._game); self._game.deleteLater()
        self._game = GameScreen(self._player, mode)
        self._game.logout_requested.connect(self._on_logout)
        self._game.menu_requested.connect(self._show_menu)
        self._stack.addWidget(self._game)
        self._stack.setCurrentWidget(self._game)

    def _on_logout(self):
        if self._game:
            self._stack.removeWidget(self._game); self._game.deleteLater(); self._game = None
        if self._menu:
            self._stack.removeWidget(self._menu); self._menu.deleteLater(); self._menu = None
        self._stack.setCurrentWidget(self._login)


# ═════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
def main():
    init_db()
    export_quests_json()
    game_log("Application started")

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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()