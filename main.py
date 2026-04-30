"""
main.py — Vault Zero PyQt6 Desktop Application
Language : Python (PyQt6)
GUI layer: Qt widgets — QSplitter, QTextEdit, QPushButton, QStackedWidget
CLI layer: real QTextEdit terminal driven by game_engine.parse()
Both panels share one GameEngine instance — state is always in sync.
"""
import sys, re
from configparser import ConfigParser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFrame,
    QScrollArea, QSizePolicy, QInputDialog, QMessageBox,
    QProgressBar,
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QThread, QObject, QSize
)
from PyQt6.QtGui import (
    QFont, QColor, QTextCharFormat, QTextCursor,
    QPalette, QKeyEvent,
)

from db          import init_db, register, login, save_run, get_leaderboard, game_log
from game_engine import GameEngine
from lua_bridge  import fire_event
from game_data   import ROOMS, export_quests_json

# ── Palette ───────────────────────────────────────────────────────────────────
C = {
    "bg":      "#0a0907",
    "bg2":     "#110f0c",
    "bg3":     "#181410",
    "bg4":     "#1e1a14",
    "border":  "#2a2318",
    "border2": "#3a3020",
    "text":    "#c9b99a",
    "text2":   "#8a7a65",
    "text3":   "#5a4e3e",
    "gold":    "#d4a853",
    "gold2":   "#a07830",
    "green":   "#4a8a4a",
    "red":     "#aa4a4a",
    "amber":   "#9a7a2a",
    "teal":    "#3a7a7a",
    "dim":     "#5a4e3e",
}

STYLE_MAP = {
    "normal": C["text"],
    "system": C["green"],
    "error":  C["red"],
    "warn":   C["amber"],
    "gold":   C["gold"],
    "dim":    C["dim"],
}

BASE_STYLE = f"""
QWidget       {{ background:{C['bg']}; color:{C['text']}; }}
QFrame        {{ background:{C['bg2']}; border:0px; }}
QLineEdit     {{ background:{C['bg3']}; color:{C['text']}; border:1px solid {C['border2']};
                 border-radius:4px; padding:6px 10px; selection-background-color:{C['gold2']}; }}
QLineEdit:focus {{ border:1px solid {C['gold2']}; }}
QScrollBar:vertical {{ background:{C['bg2']}; width:6px; }}
QScrollBar::handle:vertical {{ background:{C['border2']}; border-radius:3px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QProgressBar  {{ background:{C['bg3']}; border:1px solid {C['border']}; border-radius:3px; text-align:center; color:{C['text']}; }}
QProgressBar::chunk {{ background:{C['green']}; }}
"""

def btn_style(color=None, border=None):
    c   = color  or C["text2"]
    b   = border or C["border2"]
    return (f"QPushButton {{ background:transparent; color:{c}; border:1px solid {b};"
            f" border-radius:4px; padding:6px 12px; font-family:'Courier New'; font-size:12px; }}"
            f"QPushButton:hover {{ background:{C['bg4']}; color:{C['gold']}; border-color:{C['border2']}; }}"
            f"QPushButton:pressed {{ background:{C['bg3']}; }}"
            f"QPushButton:disabled {{ color:{C['dim']}; border-color:{C['border']}; }}")


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN SCREEN
# ─────────────────────────────────────────────────────────────────────────────
class LoginScreen(QWidget):
    login_success = pyqtSignal(dict, str)   # player dict, token

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        wrap = QWidget(); wrap.setMaximumWidth(440)
        wrap.setStyleSheet(f"background:{C['bg2']}; border:1px solid {C['border2']}; border-radius:10px;")
        vl = QVBoxLayout(wrap); vl.setContentsMargins(28, 28, 28, 28); vl.setSpacing(0)

        # title
        title = QLabel("VAULT ZERO"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Georgia", 22, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{C['gold']}; letter-spacing:4px; background:transparent; border:none;")
        sub = QLabel("SECURE PLAYER AUTHENTICATION")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color:{C['text3']}; font-size:10px; letter-spacing:2px; background:transparent; border:none;")
        vl.addWidget(title); vl.addWidget(sub); vl.addSpacing(20)

        # tabs
        tab_row = QHBoxLayout(); tab_row.setSpacing(0)
        self.tab_login = QPushButton("[ LOGIN ]")
        self.tab_reg   = QPushButton("[ REGISTER ]")
        for t in (self.tab_login, self.tab_reg):
            t.setCheckable(True)
            t.setStyleSheet(f"QPushButton{{background:transparent;color:{C['text3']};border:none;"
                            f"border-bottom:2px solid transparent;padding:8px 20px;font-family:'Courier New';font-size:11px;}}"
                            f"QPushButton:checked{{color:{C['gold']};border-bottom:2px solid {C['gold']};}}")
        self.tab_login.setChecked(True)
        self.tab_login.clicked.connect(lambda: self._switch_tab(False))
        self.tab_reg.clicked.connect(lambda: self._switch_tab(True))
        tab_row.addWidget(self.tab_login); tab_row.addWidget(self.tab_reg)
        vl.addLayout(tab_row); vl.addSpacing(4)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C['border']}; background:{C['border']};"); vl.addWidget(sep)
        vl.addSpacing(16)

        # banner
        self.banner = QLabel(""); self.banner.setWordWrap(True)
        self.banner.setStyleSheet("font-size:12px; padding:8px; border-radius:4px; background:transparent; border:none;")
        self.banner.hide(); vl.addWidget(self.banner)

        # login form
        self.login_form = QWidget(); self.login_form.setStyleSheet("background:transparent; border:none;")
        lf = QVBoxLayout(self.login_form); lf.setContentsMargins(0,0,0,0); lf.setSpacing(10)
        self.l_user = self._field(lf, "USERNAME", "your_handle")
        self.l_pass = self._field(lf, "PASSWORD", "••••••••", password=True)
        self.l_btn  = self._submit_btn(lf, "[ ENTER VAULT ]", self._do_login)
        vl.addWidget(self.login_form)

        # register form
        self.reg_form = QWidget(); self.reg_form.setStyleSheet("background:transparent; border:none;")
        rf = QVBoxLayout(self.reg_form); rf.setContentsMargins(0,0,0,0); rf.setSpacing(10)
        self.r_user  = self._field(rf, "USERNAME", "3–20 chars, letters/numbers/_")
        self.r_email = self._field(rf, "EMAIL",    "you@example.com")
        self.r_pass  = self._field(rf, "PASSWORD", "min 8 characters", password=True)
        self.r_pass2 = self._field(rf, "CONFIRM PASSWORD", "repeat password", password=True)
        self.r_btn   = self._submit_btn(rf, "[ CREATE ACCOUNT ]", self._do_register)
        self.reg_form.hide(); vl.addWidget(self.reg_form)

        # CLI boot log
        self.cli_log = QTextEdit(); self.cli_log.setReadOnly(True)
        self.cli_log.setMaximumHeight(90)
        self.cli_log.setFont(QFont("Courier New", 10))
        self.cli_log.setStyleSheet(f"background:#050403; border:1px solid {C['border']}; border-radius:4px; color:{C['dim']};")
        vl.addSpacing(10); vl.addWidget(self.cli_log)

        footer = QLabel(f"db: arena.db  |  lang: python · sql · lua · bash · pyqt6")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"color:{C['text3']}; font-size:10px; background:transparent; border:none;")
        vl.addSpacing(8); vl.addWidget(footer)

        outer.addWidget(wrap)
        self._boot_log()

    def _field(self, layout, label_text, placeholder, password=False):
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color:{C['text2']}; font-size:11px; letter-spacing:1px; background:transparent; border:none;")
        inp = QLineEdit(); inp.setPlaceholderText(placeholder)
        if password: inp.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(lbl); layout.addWidget(inp)
        return inp

    def _submit_btn(self, layout, text, slot):
        btn = QPushButton(text)
        btn.setStyleSheet(btn_style(C["gold"], C["gold2"]))
        btn.clicked.connect(slot)
        layout.addSpacing(4); layout.addWidget(btn)
        return btn

    def _switch_tab(self, show_reg: bool):
        self.tab_login.setChecked(not show_reg)
        self.tab_reg.setChecked(show_reg)
        self.login_form.setVisible(not show_reg)
        self.reg_form.setVisible(show_reg)
        self.banner.hide()

    def _boot_log(self):
        msgs = [
            (C["dim"],   "[boot] reading game.ini ... OK"),
            (C["dim"],   "[boot] PyQt6 GUI layer active"),
            (C["green"], "[db]   arena.db connected"),
            (C["green"], "[boot] Vault Zero ready"),
        ]
        for color, msg in msgs:
            self._clog(color, msg)

    def _clog(self, color, msg):
        cur = self.cli_log.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(color))
        cur.setCharFormat(fmt); cur.insertText(msg + "\n")
        self.cli_log.setTextCursor(cur)
        self.cli_log.ensureCursorVisible()

    def _show_banner(self, msg, ok=True):
        bg  = "#0e1e0e" if ok else "#1e0e0e"
        bdr = "#2a4a2a" if ok else "#4a2a2a"
        col = C["green"] if ok else C["red"]
        self.banner.setStyleSheet(f"font-size:12px; padding:8px; border-radius:4px;"
                                  f"background:{bg}; border:1px solid {bdr}; color:{col};")
        self.banner.setText(msg); self.banner.show()

    def _do_login(self):
        u = self.l_user.text().strip()
        p = self.l_pass.text()
        if not u or not p:
            self._show_banner("Username and password required.", False); return
        self.l_btn.setEnabled(False); self.l_btn.setText("[ AUTHENTICATING... ]")
        self._clog(C["dim"], f"[login] authenticating {u} ...")
        result = login(u, p)
        if result["ok"]:
            self._clog(C["green"], f"[login] OK — session issued")
            self.login_success.emit(result["player"], result["token"])
        else:
            self._show_banner(result["error"], False)
            self._clog(C["red"], f"[login] FAIL: {result['error']}")
        self.l_btn.setEnabled(True); self.l_btn.setText("[ ENTER VAULT ]")

    def _do_register(self):
        u  = self.r_user.text().strip()
        e  = self.r_email.text().strip()
        p  = self.r_pass.text()
        p2 = self.r_pass2.text()
        if len(u) < 3: self._show_banner("Username must be 3+ characters.", False); return
        if not re.match(r"^[A-Za-z0-9_]{3,20}$", u):
            self._show_banner("Username: letters, numbers, underscore only.", False); return
        if "@" not in e: self._show_banner("Enter a valid email.", False); return
        if len(p) < 8:   self._show_banner("Password must be 8+ characters.", False); return
        if p != p2:       self._show_banner("Passwords do not match.", False); return
        self.r_btn.setEnabled(False); self.r_btn.setText("[ CREATING... ]")
        result = register(u, e, p)
        if result["ok"]:
            self._show_banner("Account created! You can now log in.", True)
            self._clog(C["green"], f"[register] account created: {u}")
            QTimer.singleShot(1200, lambda: self._switch_tab(False))
        else:
            self._show_banner(result["error"], False)
        self.r_btn.setEnabled(True); self.r_btn.setText("[ CREATE ACCOUNT ]")


# ─────────────────────────────────────────────────────────────────────────────
# PUZZLE INPUT DIALOG
# ─────────────────────────────────────────────────────────────────────────────
class PuzzleDialog(QWidget):
    submitted = pyqtSignal(str, str)   # puzzle_key, code
    cancelled = pyqtSignal()

    def __init__(self, puzzle_key: str, puzzle: dict, parent=None):
        super().__init__(parent)
        self.puzzle_key = puzzle_key
        self.setStyleSheet(f"background:{C['bg3']}; border:1px solid {C['border2']}; border-radius:8px;")
        vl = QVBoxLayout(self); vl.setContentsMargins(16, 16, 16, 16); vl.setSpacing(10)

        lbl_title = QLabel(f"UNLOCK: {puzzle['label'].upper()}")
        lbl_title.setFont(QFont("Georgia", 12, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color:{C['gold']}; background:transparent; border:none;")
        vl.addWidget(lbl_title)

        hint_box = QTextEdit(); hint_box.setReadOnly(True)
        hint_box.setFont(QFont("Courier New", 11))
        hint_box.setPlainText(puzzle["hint"])
        hint_box.setMaximumHeight(110)
        hint_box.setStyleSheet(f"background:{C['bg2']}; color:{C['text2']}; border:1px solid {C['border']};"
                               f" border-radius:4px; padding:6px;")
        vl.addWidget(hint_box)

        self.inp = QLineEdit()
        self.inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.inp.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        self.inp.setPlaceholderText("_ _ _ _")
        self.inp.setMaxLength(puzzle.get("length", 6))
        self.inp.setStyleSheet(f"background:{C['bg2']}; color:{C['gold']}; border:1px solid {C['gold2']};"
                               f" border-radius:4px; padding:8px; letter-spacing:6px;")
        self.inp.returnPressed.connect(self._submit)
        vl.addWidget(self.inp)

        self.status = QLabel(""); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet(f"color:{C['red']}; font-size:12px; background:transparent; border:none;")
        vl.addWidget(self.status)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel"); cancel_btn.setStyleSheet(btn_style())
        submit_btn = QPushButton("[ SUBMIT ]"); submit_btn.setStyleSheet(btn_style(C["gold"], C["gold2"]))
        cancel_btn.clicked.connect(self.cancelled.emit)
        submit_btn.clicked.connect(self._submit)
        btn_row.addWidget(cancel_btn); btn_row.addWidget(submit_btn)
        vl.addLayout(btn_row)
        QTimer.singleShot(50, self.inp.setFocus)

    def _submit(self):
        code = self.inp.text().strip()
        if code:
            self.submitted.emit(self.puzzle_key, code)

    def set_wrong(self):
        self.status.setText("✗  Wrong code — try again")
        self.inp.selectAll(); self.inp.setFocus()

    def set_correct(self):
        self.status.setText("✓  Correct!")
        self.status.setStyleSheet(f"color:{C['green']}; font-size:12px; background:transparent; border:none;")


# ─────────────────────────────────────────────────────────────────────────────
# GAME SCREEN
# ─────────────────────────────────────────────────────────────────────────────
class GameScreen(QWidget):
    logout_requested = pyqtSignal()

    def __init__(self, player: dict):
        super().__init__()
        self.player  = player
        self.engine  = GameEngine(player)
        self._active_puzzle_key = None
        self._build()
        self._start_timer()
        self._enter_room()

    # ── Build layout ───────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # Top bar
        topbar = QFrame(); topbar.setFixedHeight(42)
        topbar.setStyleSheet(f"background:{C['bg2']}; border-bottom:1px solid {C['border']};")
        tb = QHBoxLayout(topbar); tb.setContentsMargins(14, 0, 14, 0); tb.setSpacing(16)
        title_lbl = QLabel("VAULT ZERO")
        title_lbl.setFont(QFont("Georgia", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color:{C['gold']}; letter-spacing:2px; background:transparent;")
        tb.addWidget(title_lbl)
        tb.addStretch()
        # HUD labels
        self.hud_room   = self._hud_lbl("ROOM 1/4", tb)
        self.hud_solved = self._hud_lbl("SOLVED 0/4", tb)
        self.hud_inv    = self._hud_lbl("ITEMS 0", tb)
        self.hud_timer  = QLabel("15:00")
        self.hud_timer.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self.hud_timer.setStyleSheet(f"color:{C['gold']}; background:transparent;")
        tb.addWidget(self.hud_timer)
        logout_btn = QPushButton("Logout"); logout_btn.setStyleSheet(btn_style())
        logout_btn.clicked.connect(self._do_logout)
        tb.addWidget(logout_btn)
        root.addWidget(topbar)

        # Splitter — CLI left, GUI right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background:{C['border']}; }}")

        # ── LEFT: CLI panel ────────────────────────────────────────────────────
        cli_widget = QWidget()
        cli_vl = QVBoxLayout(cli_widget); cli_vl.setContentsMargins(0, 0, 0, 0); cli_vl.setSpacing(0)
        cli_hdr = QFrame(); cli_hdr.setFixedHeight(28)
        cli_hdr.setStyleSheet(f"background:{C['bg2']}; border-bottom:1px solid {C['border']};")
        ch = QHBoxLayout(cli_hdr); ch.setContentsMargins(12, 0, 12, 0)
        dot = QLabel("●"); dot.setStyleSheet(f"color:#3a6a3a; font-size:8px; background:transparent;")
        lbl = QLabel("CLI — bash/python layer")
        lbl.setStyleSheet(f"color:{C['text3']}; font-size:10px; letter-spacing:1px; background:transparent;")
        ch.addWidget(dot); ch.addWidget(lbl); ch.addStretch()
        cli_vl.addWidget(cli_hdr)

        self.cli_output = QTextEdit(); self.cli_output.setReadOnly(True)
        self.cli_output.setFont(QFont("Courier New", 12))
        self.cli_output.setStyleSheet(f"background:#050403; border:none; padding:6px;")
        cli_vl.addWidget(self.cli_output, 1)

        hint_lbl = QLabel("  try: look · examine [obj] · open [obj] · use [item] on [obj] · go n · help")
        hint_lbl.setStyleSheet(f"color:{C['text3']}; font-size:10px; background:#050403; padding:2px 8px;")
        cli_vl.addWidget(hint_lbl)

        inp_frame = QFrame(); inp_frame.setFixedHeight(38)
        inp_frame.setStyleSheet(f"background:#050403; border-top:1px solid {C['border']};")
        inf = QHBoxLayout(inp_frame); inf.setContentsMargins(8, 4, 8, 4); inf.setSpacing(4)
        prompt_lbl = QLabel("vault>")
        prompt_lbl.setFont(QFont("Courier New", 12))
        prompt_lbl.setStyleSheet(f"color:{C['green']}; background:transparent;")
        self.cli_input = QLineEdit()
        self.cli_input.setFont(QFont("Courier New", 12))
        self.cli_input.setStyleSheet(
            f"background:transparent; color:{C['gold']}; border:none; padding:0;"
        )
        self.cli_input.setPlaceholderText("enter command...")
        self.cli_input.returnPressed.connect(self._cli_submit)
        inf.addWidget(prompt_lbl); inf.addWidget(self.cli_input, 1)
        cli_vl.addWidget(inp_frame)
        splitter.addWidget(cli_widget)

        # ── RIGHT: GUI panel ───────────────────────────────────────────────────
        gui_widget = QWidget()
        gui_vl = QVBoxLayout(gui_widget); gui_vl.setContentsMargins(0, 0, 0, 0); gui_vl.setSpacing(0)
        gui_hdr = QFrame(); gui_hdr.setFixedHeight(28)
        gui_hdr.setStyleSheet(f"background:{C['bg2']}; border-bottom:1px solid {C['border']};")
        gh = QHBoxLayout(gui_hdr); gh.setContentsMargins(12, 0, 12, 0)
        dot2 = QLabel("●"); dot2.setStyleSheet(f"color:#8a6a2a; font-size:8px; background:transparent;")
        lbl2 = QLabel("GUI — PyQt6 layer")
        lbl2.setStyleSheet(f"color:{C['text3']}; font-size:10px; letter-spacing:1px; background:transparent;")
        gh.addWidget(dot2); gh.addWidget(lbl2); gh.addStretch()
        self.db_lbl = QLabel("db: arena.db")
        self.db_lbl.setStyleSheet(f"color:{C['text3']}; font-size:10px; background:transparent;")
        gh.addWidget(self.db_lbl)
        gui_vl.addWidget(gui_hdr)

        # Room art (SVG-style ASCII drawn via QLabel)
        self.room_art = QLabel()
        self.room_art.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.room_art.setFixedHeight(100)
        self.room_art.setFont(QFont("Courier New", 11))
        self.room_art.setStyleSheet(f"background:{C['bg3']}; color:{C['text2']}; border-bottom:1px solid {C['border']}; padding:6px;")
        gui_vl.addWidget(self.room_art)

        # Room name + description
        self.room_name = QLabel()
        self.room_name.setFont(QFont("Georgia", 13, QFont.Weight.Bold))
        self.room_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.room_name.setStyleSheet(f"color:{C['gold']}; background:{C['bg3']}; padding:6px; border-bottom:1px solid {C['border']};")
        gui_vl.addWidget(self.room_name)

        self.room_desc = QTextEdit(); self.room_desc.setReadOnly(True)
        self.room_desc.setFont(QFont("Georgia", 12))
        self.room_desc.setStyleSheet(f"background:{C['bg']}; color:{C['text']}; border:none; padding:10px 14px;")
        self.room_desc.setMaximumHeight(100)
        gui_vl.addWidget(self.room_desc)

        # Puzzle area (hidden by default, shown when puzzle is active)
        self.puzzle_area = QWidget()
        self.puzzle_area.setStyleSheet(f"background:{C['bg3']}; border-top:1px solid {C['border']};")
        self.puzzle_area.hide()
        self.puzzle_vl = QVBoxLayout(self.puzzle_area)
        self.puzzle_vl.setContentsMargins(0, 0, 0, 0)
        gui_vl.addWidget(self.puzzle_area)

        # Action buttons
        actions_frame = QFrame()
        actions_frame.setStyleSheet(f"background:{C['bg2']}; border-top:1px solid {C['border']};")
        self.actions_grid = QGridLayout(actions_frame)
        self.actions_grid.setContentsMargins(8, 8, 8, 8); self.actions_grid.setSpacing(6)
        gui_vl.addWidget(actions_frame)

        # Inventory bar
        inv_frame = QFrame(); inv_frame.setFixedHeight(36)
        inv_frame.setStyleSheet(f"background:{C['bg2']}; border-top:1px solid {C['border']};")
        self.inv_layout = QHBoxLayout(inv_frame)
        self.inv_layout.setContentsMargins(8, 4, 8, 4); self.inv_layout.setSpacing(6)
        self.inv_empty = QLabel("inventory empty")
        self.inv_empty.setStyleSheet(f"color:{C['text3']}; font-size:10px; background:transparent;")
        self.inv_layout.addWidget(self.inv_empty)
        gui_vl.addWidget(inv_frame)

        splitter.addWidget(gui_widget)
        splitter.setSizes([580, 580])
        root.addWidget(splitter, 1)

        # Bottom bar
        botbar = QFrame(); botbar.setFixedHeight(26)
        botbar.setStyleSheet(f"background:#040302; border-top:1px solid {C['border']};")
        bb = QHBoxLayout(botbar); bb.setContentsMargins(14, 0, 14, 0)
        self.bot_db = QLabel("db: arena.db | rooms.json | game.log")
        self.bot_db.setStyleSheet(f"color:{C['text3']}; font-size:10px; background:transparent;")
        langs = QLabel("bash · python · lua · sql · pyqt6")
        langs.setStyleSheet(f"color:{C['text3']}; font-size:10px; background:transparent;")
        bb.addWidget(self.bot_db); bb.addStretch(); bb.addWidget(langs)
        root.addWidget(botbar)

    def _hud_lbl(self, text, layout):
        lbl = QLabel(text)
        lbl.setFont(QFont("Courier New", 10))
        lbl.setStyleSheet(f"color:{C['text2']}; background:transparent;")
        layout.addWidget(lbl)
        return lbl

    # ── Timer ──────────────────────────────────────────────────────────────────
    def _start_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        if self.engine.finished: return
        r = self.engine.remaining
        m, s = divmod(r, 60)
        self.hud_timer.setText(f"{m:02d}:{s:02d}")
        if r <= 60:
            self.hud_timer.setStyleSheet(f"color:{C['red']}; background:transparent;")
        if r <= 0:
            self._timer.stop()
            self._game_over("Time expired")

    def _game_over(self, reason: str):
        fire_event("game_over", self.engine.room_id, reason)
        self._cli_print([
            ("gold",   ""),
            ("red",    "TIME EXPIRED — VAULT LOCKDOWN TRIGGERED"),
            ("dim",    "You will be found."),
        ])
        save_run(self.player["id"], self.engine.elapsed, False, self.engine.room_id)
        self.hud_timer.setText("FAILED")

    # ── Room enter ─────────────────────────────────────────────────────────────
    def _enter_room(self):
        r   = self.engine.room
        evt = fire_event("room_enter", self.engine.room_id)

        # GUI update
        self.room_name.setText(r["name"])
        self.room_desc.setPlainText("\n".join(r["desc"]))
        if evt.get("flavour"):
            self.room_desc.append(f"\n{evt['flavour']}")
        self.room_art.setText(ROOM_ART.get(self.engine.room_id, ""))
        self.db_lbl.setText(f"db: {r['db_indicator']}")
        self.bot_db.setText(f"db: {r['db_indicator']}")
        self._refresh_actions()
        self._refresh_inv()
        self._refresh_hud()
        self._hide_puzzle()

        # CLI output
        out = self.engine.get_room_enter_output()
        self._cli_print(out["lines"])

    # ── CLI ────────────────────────────────────────────────────────────────────
    def _cli_submit(self):
        raw = self.cli_input.text().strip()
        if not raw: return
        self.cli_input.clear()
        # echo
        self._cli_print([("dim", f"vault> "), ("gold", raw)], newline=False)
        self._cli_line()

        result = self.engine.parse(raw)
        self._handle_result(result)

    def _cli_print(self, lines, newline=True):
        cur = self.cli_output.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        for item in lines:
            if len(item) == 2:
                style, text = item
            else:
                style, text = "normal", str(item)
            color = STYLE_MAP.get(style, C["text"])
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cur.setCharFormat(fmt)
            cur.insertText(text + ("\n" if newline else ""))
        self.cli_output.setTextCursor(cur)
        self.cli_output.ensureCursorVisible()

    def _cli_line(self):
        self._cli_print([("dim", "")])

    # ── Result handler (shared by CLI and GUI) ─────────────────────────────────
    def _handle_result(self, result: dict):
        self._cli_print(result["lines"])

        if result.get("state_changed"):
            self._refresh_inv()
            self._refresh_hud()

        if result.get("room_changed"):
            self._enter_room()
            return

        if result.get("puzzle_key"):
            pkey = result["puzzle_key"]
            self._show_puzzle(pkey)

        if result.get("solved_puzzle"):
            pkey = result["solved_puzzle"]
            evt  = fire_event("puzzle_solve", self.engine.room_id, pkey)
            if evt.get("flavour"):
                self._cli_print([("dim", evt["flavour"])])
            self._hide_puzzle()
            self._refresh_actions()

        if result.get("wrong_code"):
            attempts = len([p for p in self.engine.solved[self.engine.room_id]])
            evt = fire_event("puzzle_attempt", self.engine.room_id, str(attempts + 1))
            if evt.get("flavour"):
                self._cli_print([("dim", evt["flavour"])])
            if self._active_puzzle and hasattr(self._active_puzzle, "set_wrong"):
                self._active_puzzle.set_wrong()

        if result.get("escaped"):
            self._on_escaped()

    # ── Puzzle panel ───────────────────────────────────────────────────────────
    def _show_puzzle(self, puzzle_key: str):
        self._active_puzzle_key = puzzle_key
        puzzle = self.engine.room["puzzles"][puzzle_key]
        # clear old
        while self.puzzle_vl.count():
            w = self.puzzle_vl.takeAt(0).widget()
            if w: w.deleteLater()
        pd = PuzzleDialog(puzzle_key, puzzle)
        pd.submitted.connect(self._gui_submit_puzzle)
        pd.cancelled.connect(self._hide_puzzle)
        self._active_puzzle = pd
        self.puzzle_vl.addWidget(pd)
        self.puzzle_area.show()

    def _hide_puzzle(self):
        self.puzzle_area.hide()
        self._active_puzzle_key = None
        self._active_puzzle = None

    def _gui_submit_puzzle(self, puzzle_key: str, code: str):
        self._cli_print([("dim", f"vault> enter {code}")])
        result = self.engine.submit_puzzle(puzzle_key, code)
        self._handle_result(result)

    # ── Action buttons ─────────────────────────────────────────────────────────
    def _refresh_actions(self):
        # clear
        while self.actions_grid.count():
            w = self.actions_grid.takeAt(0).widget()
            if w: w.deleteLater()
        actions = self.engine.get_gui_actions()
        cols = 3
        for i, act in enumerate(actions):
            key_lbl = ["A","B","C","D","E","F","G","H"][i] if i < 8 else str(i)
            text = f"[{key_lbl}] {act['label']}"
            color = {"normal": C["text2"], "warn": C["amber"], "gold": C["gold"]}.get(act["style"], C["text2"])
            border = {"warn": C["amber2"] if C.get("amber2") else C["border2"],
                      "gold": C["gold2"]}.get(act["style"], C["border2"])
            btn = QPushButton(text)
            btn.setStyleSheet(btn_style(color, border))
            btn.setFont(QFont("Courier New", 11))
            cmd = act["cmd"]
            btn.clicked.connect(lambda checked=False, c=cmd: self._gui_action(c))
            self.actions_grid.addWidget(btn, i // cols, i % cols)

    def _gui_action(self, cmd: str):
        self._cli_print([("dim", f"vault> "), ("gold", cmd)], newline=False)
        self._cli_line()
        result = self.engine.parse(cmd)
        self._handle_result(result)

    # ── Inventory bar ──────────────────────────────────────────────────────────
    def _refresh_inv(self):
        while self.inv_layout.count():
            w = self.inv_layout.takeAt(0).widget()
            if w: w.deleteLater()
        if not self.engine.inventory:
            self.inv_empty = QLabel("inventory empty")
            self.inv_empty.setStyleSheet(f"color:{C['text3']}; font-size:10px; background:transparent;")
            self.inv_layout.addWidget(self.inv_empty)
            return
        type_colors = {"key": C["gold"], "item": C["green"], "clue": C["teal"], "weapon": C["red"]}
        for item in self.engine.inventory:
            color = type_colors.get(item["type"], C["text2"])
            tag = QLabel(item["name"])
            tag.setFont(QFont("Courier New", 10))
            tag.setStyleSheet(f"color:{color}; background:{C['bg3']}; border:1px solid {C['border2']};"
                              f" border-radius:3px; padding:1px 7px;")
            self.inv_layout.addWidget(tag)
        self.inv_layout.addStretch()

    # ── HUD ────────────────────────────────────────────────────────────────────
    def _refresh_hud(self):
        rooms    = ["storage", "lab", "server", "vault"]
        room_idx = rooms.index(self.engine.room_id) + 1
        solved   = sum(1 for rid in rooms if all(p in self.engine.solved[rid] for p in ROOMS[rid]["solve_condition"]))
        self.hud_room.setText(f"ROOM {room_idx}/4")
        self.hud_solved.setText(f"SOLVED {solved}/4")
        self.hud_inv.setText(f"ITEMS {len(self.engine.inventory)}")

    # ── Escaped ────────────────────────────────────────────────────────────────
    def _on_escaped(self):
        self._timer.stop()
        evt = fire_event("escape", self.engine.room_id)
        if evt.get("flavour"):
            self._cli_print([("gold", evt["flavour"])])
        save_run(self.player["id"], self.engine.elapsed, True, self.engine.room_id)
        self.hud_timer.setText("ESCAPED")
        self.hud_timer.setStyleSheet(f"color:{C['green']}; background:transparent;")
        game_log(f"ESCAPED: {self.player['username']} in {self.engine.elapsed}s")
        self._show_leaderboard()

    def _show_leaderboard(self):
        board = get_leaderboard()
        self._cli_print([("gold", ""), ("gold", "─── LEADERBOARD ───────────────────────────")])
        for i, row in enumerate(board, 1):
            self._cli_print([("normal", f"  {i:2}. {row['username']:<20} LV{row['level']}  {row['total_xp']} XP  {row['escapes']} escapes")])
        self._cli_print([("gold", "────────────────────────────────────────────")])

    def _do_logout(self):
        self._timer.stop()
        self.logout_requested.emit()


# ─────────────────────────────────────────────────────────────────────────────
# ROOM ASCII ART
# ─────────────────────────────────────────────────────────────────────────────
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
        "│  1101=13      1011=11    │  █████████    │\n"
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


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, cfg: ConfigParser):
        super().__init__()
        self.cfg = cfg
        w = int(cfg.get("ui", "window_w", fallback=1280))
        h = int(cfg.get("ui", "window_h", fallback=760))
        self.setWindowTitle(cfg.get("ui", "window_title", fallback="Vault Zero"))
        self.resize(w, h)
        self.setStyleSheet(BASE_STYLE)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_screen = LoginScreen()
        self.login_screen.login_success.connect(self._on_login)
        self.stack.addWidget(self.login_screen)
        self.stack.setCurrentWidget(self.login_screen)

        self._game_screen = None

    def _on_login(self, player: dict, token: str):
        if self._game_screen:
            self.stack.removeWidget(self._game_screen)
            self._game_screen.deleteLater()
        self._game_screen = GameScreen(player)
        self._game_screen.logout_requested.connect(self._on_logout)
        self.stack.addWidget(self._game_screen)
        self.stack.setCurrentWidget(self._game_screen)

    def _on_logout(self):
        self.stack.setCurrentWidget(self.login_screen)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
def main():
    from configparser import ConfigParser
    import os
    base = os.path.dirname(os.path.abspath(__file__))
    cfg = ConfigParser()
    cfg.read(os.path.join(base, "game.ini"))

    init_db()
    export_quests_json()
    game_log("Application started")

    app = QApplication(sys.argv)
    app.setApplicationName("Vault Zero")

    # Force dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor(C["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor(C["text"]))
    palette.setColor(QPalette.ColorRole.Base,            QColor(C["bg2"]))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(C["bg3"]))
    palette.setColor(QPalette.ColorRole.Text,            QColor(C["text"]))
    palette.setColor(QPalette.ColorRole.Button,          QColor(C["bg2"]))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor(C["text"]))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor(C["gold2"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(C["bg"]))
    app.setPalette(palette)

    win = MainWindow(cfg)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
