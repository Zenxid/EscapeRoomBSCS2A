"""
main_menu.py — Vault Zero Main Menu & Dashboard
Language : Python (PyQt6)
Screens  : MainMenuScreen   → full dashboard after login
           ModeSelectScreen → CLI / GUI / MIXED chooser before game starts
"""
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QProgressBar, QSizePolicy,
)
from PyQt6.QtCore  import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui   import QFont, QColor, QPainter, QPen

from db               import get_leaderboard, game_log
from questhash_bridge import quest_hash, is_available as c_available

# ── Shared palette ────────────────────────────────────────────────────────────
C = {
    "bg":     "#0a0907", "bg2": "#110f0c", "bg3": "#181410", "bg4": "#1e1a14",
    "border": "#2a2318", "border2": "#3a3020", "border3": "#4a4030",
    "text":   "#c9b99a", "text2": "#8a7a65", "text3": "#5a4e3e",
    "gold":   "#d4a853", "gold2": "#a07830",
    "green":  "#4a8a4a", "red": "#aa4a4a", "amber": "#9a7a2a", "teal": "#3a7a7a",
    "dim":    "#4a3e2e",
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def _btn(text_col=None, border_col=None, size=12):
    tc = text_col  or C["text2"]
    bc = border_col or C["border2"]
    return (
        f"QPushButton{{background:transparent;color:{tc};border:1px solid {bc};"
        f"border-radius:5px;padding:7px 14px;font-family:'Courier New';font-size:{size}px;"
        f"letter-spacing:1px;}}"
        f"QPushButton:hover{{background:{C['bg4']};color:{C['gold']};"
        f"border-color:{C['border3']};}}"
        f"QPushButton:pressed{{background:{C['bg3']};}}"
        f"QPushButton:disabled{{color:{C['dim']};border-color:{C['border']};}}"
    )

def _lbl(text, color, size=11, bold=False,
         align=Qt.AlignmentFlag.AlignLeft):
    w = QFont.Weight.Bold if bold else QFont.Weight.Normal
    l = QLabel(text)
    l.setFont(QFont("Courier New", size, w))
    l.setStyleSheet(f"color:{color};background:transparent;")
    l.setAlignment(align)
    return l

def _sep():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(
        f"color:{C['border']};background:{C['border']};"
        f"max-height:1px;border:none;"
    )
    return f


# ─────────────────────────────────────────────────────────────────────────────
# ANIMATED ASCII TITLE
# ─────────────────────────────────────────────────────────────────────────────
class AnimatedTitle(QWidget):
    _LINES = [
        "██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗",
        "██║   ██║██╔══██╗██║   ██║██║     ██╔══╝",
        "██║   ██║███████║██║   ██║██║     ██║   ",
        "╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║   ",
        " ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║   ",
        "  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ",
        "",
        "     Z  E  R  O  —  E  S  C  A  P  E    ",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(130)
        self._frame = 0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(90)

    def _tick(self):
        self._frame = (self._frame + 1) % 24
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(C["bg"]))
        if self._frame < 2:
            p.fillRect(self.rect(), QColor(255, 255, 255, 5))
        fnt = QFont("Courier New", 9, QFont.Weight.Bold)
        p.setFont(fnt)
        fm  = p.fontMetrics()
        lh  = fm.height() + 1
        for i, line in enumerate(self._LINES):
            if not line.strip():
                continue
            col = (QColor(C["gold"])
                   if (i + self._frame // 4) % 3 != 0
                   else QColor(C["gold2"]))
            p.setPen(QPen(col))
            x = (self.width() - fm.horizontalAdvance(line)) // 2
            p.drawText(x, 14 + i * lh, line)
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# STAT CARD
# ─────────────────────────────────────────────────────────────────────────────
class StatCard(QFrame):
    def __init__(self, label, value, color=None):
        super().__init__()
        self.setStyleSheet(
            f"QFrame{{background:{C['bg3']};border:1px solid {C['border2']};"
            f"border-radius:6px;}}"
        )
        vl = QVBoxLayout(self)
        vl.setContentsMargins(14, 10, 14, 10)
        vl.setSpacing(2)
        lbl_w = QLabel(label)
        lbl_w.setFont(QFont("Courier New", 9))
        lbl_w.setStyleSheet(
            f"color:{C['text3']};background:transparent;letter-spacing:1px;"
        )
        self._val = QLabel(value)
        self._val.setFont(QFont("Courier New", 20, QFont.Weight.Bold))
        self._val.setStyleSheet(
            f"color:{color or C['text']};background:transparent;"
        )
        vl.addWidget(lbl_w)
        vl.addWidget(self._val)

    def set_value(self, v):
        self._val.setText(v)


# ─────────────────────────────────────────────────────────────────────────────
# LEADERBOARD WIDGET
# ─────────────────────────────────────────────────────────────────────────────
class LeaderboardWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border2']};"
            f"border-radius:8px;}}"
        )
        vl = QVBoxLayout(self)
        vl.setContentsMargins(14, 12, 14, 12)
        vl.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.addWidget(_lbl("TOP VAULT RUNNERS", C["gold"], 10, bold=True))
        ref = QPushButton("↻")
        ref.setFixedSize(24, 24)
        ref.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text3']};"
            f"border:none;font-size:14px;}}"
            f"QPushButton:hover{{color:{C['gold']};}}"
        )
        ref.clicked.connect(self.load)
        hdr.addStretch(); hdr.addWidget(ref)
        vl.addLayout(hdr)
        vl.addWidget(_sep())

        self._rows_vl = QVBoxLayout()
        self._rows_vl.setSpacing(3)
        vl.addLayout(self._rows_vl)
        self.load()

    # Rank table mirrored here for LeaderboardWidget (no access to self of screen)
    _RANKS = [
        (0,      "Rookie",  "#8a7a65", "◈"),
        (1000,   "Agent",   "#4a8a4a", "◉"),
        (3000,   "Breaker", "#4a7ab0", "◆"),
        (7000,   "Ghost",   "#7a5ab0", "✦"),
        (15000,  "Phantom", "#d4a853", "★"),
        (30000,  "Wraith",  "#aa4a4a", "☿"),
        (60000,  "Specter", "#3a7a7a", "⬡"),
        (120000, "Cipher",  "#d4a853", "⬟"),
    ]

    def _get_rank(self, xp):
        rank = self._RANKS[0]
        for entry in self._RANKS:
            if xp >= entry[0]: rank = entry
        return rank  # (min_xp, name, color, badge)

    def load(self):
        while self._rows_vl.count():
            w = self._rows_vl.takeAt(0).widget()
            if w: w.deleteLater()
        rows = get_leaderboard()
        pos_col = [C["gold"], "#9a9a9a", "#9a6a3a"]
        pos_medal = ["🥇", "🥈", "🥉"]
        if not rows:
            self._rows_vl.addWidget(
                _lbl("No runs yet — be the first to escape.", C["text3"], 10)
            )
            return
        for i, row in enumerate(rows):
            pc   = pos_col[i] if i < 3 else C["text2"]
            rank = self._get_rank(row["total_xp"])

            rw = QWidget(); rw.setStyleSheet("background:transparent;")
            hl = QHBoxLayout(rw); hl.setContentsMargins(0, 2, 0, 2); hl.setSpacing(4)

            # Position medal or number
            pos_lbl = QLabel(pos_medal[i] if i < 3 else f"#{i+1}")
            pos_lbl.setFont(QFont("Courier New", 10))
            pos_lbl.setFixedWidth(24)
            pos_lbl.setStyleSheet(f"color:{pc};background:transparent;")
            hl.addWidget(pos_lbl)

            # Rank badge
            badge_lbl = QLabel(rank[3])
            badge_lbl.setFont(QFont("Courier New", 10))
            badge_lbl.setFixedWidth(16)
            badge_lbl.setStyleSheet(f"color:{rank[2]};background:transparent;")
            hl.addWidget(badge_lbl)

            # Username
            name_lbl = QLabel(row["username"])
            name_lbl.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
            name_lbl.setStyleSheet(f"color:{C['text']};background:transparent;")
            hl.addWidget(name_lbl)
            hl.addStretch()

            # Rank name + level
            rank_lbl = QLabel(f"{rank[1]}")
            rank_lbl.setFont(QFont("Courier New", 9))
            rank_lbl.setStyleSheet(f"color:{rank[2]};background:transparent;")
            hl.addWidget(rank_lbl)

            lv_lbl = QLabel(f"  LV{row['level']}")
            lv_lbl.setFont(QFont("Courier New", 9))
            lv_lbl.setStyleSheet(f"color:{C['text3']};background:transparent;")
            hl.addWidget(lv_lbl)

            xp_lbl = QLabel(f"  {row['total_xp']}XP")
            xp_lbl.setFont(QFont("Courier New", 9))
            xp_lbl.setStyleSheet(f"color:{C['amber']};background:transparent;")
            hl.addWidget(xp_lbl)

            self._rows_vl.addWidget(rw)


# ─────────────────────────────────────────────────────────────────────────────
# MODE CARD
# ─────────────────────────────────────────────────────────────────────────────
_MODE_DATA = {
    "mixed": {
        "label":  "MIXED",
        "sub":    "Split-pane · CLI + GUI side by side",
        "icon":   "[ CLI | GUI ]",
        "color":  C["gold"],
        "border": C["gold2"],
        "desc": (
            "The full Vault Zero experience.\n\n"
            "Left panel  → real terminal input.\n"
            "Right panel → GUI scene art & buttons.\n\n"
            "Both panels share one engine — always in sync.\n"
            "Recommended for first-time players."
        ),
    },
    "gui": {
        "label":  "GUI ONLY",
        "sub":    "Point-and-click · no typing required",
        "icon":   "[   GUI   ]",
        "color":  C["teal"],
        "border": "#2a5a5a",
        "desc": (
            "Pure graphical interface.\n\n"
            "Room art, narrative text, action buttons.\n"
            "Puzzle dialogs with on-screen input.\n"
            "Inventory bar always visible.\n\n"
            "Good for casual or new players."
        ),
    },
    "cli": {
        "label":  "CLI ONLY",
        "sub":    "Terminal purist · keyboard only",
        "icon":   "[   CLI   ]",
        "color":  C["green"],
        "border": "#2a5a2a",
        "desc": (
            "Pure command-line interface.\n\n"
            "Full-width terminal — no GUI panels.\n"
            "Commands: look, examine, open, use, go n…\n\n"
            "For players who want the authentic\n"
            "terminal feel.  Hard mode."
        ),
    },
}

class ModeCard(QFrame):
    selected = pyqtSignal(str)

    def __init__(self, key):
        super().__init__()
        self._key  = key
        self._data = _MODE_DATA[key]
        self._sel  = False
        self._build()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(190)
        self.setFixedHeight(270)

    def _build(self):
        d  = self._data
        vl = QVBoxLayout(self)
        vl.setContentsMargins(18, 18, 18, 18)
        vl.setSpacing(8)

        icon = QLabel(d["icon"])
        icon.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"color:{d['color']};background:transparent;letter-spacing:2px;"
        )
        lbl = QLabel(d["label"])
        lbl.setFont(QFont("Georgia", 14, QFont.Weight.Bold))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color:{d['color']};background:transparent;")
        sub = QLabel(d["sub"])
        sub.setFont(QFont("Courier New", 9))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{C['text3']};background:transparent;")
        desc = QLabel(d["desc"])
        desc.setFont(QFont("Courier New", 10))
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{C['text2']};background:transparent;")
        desc.setAlignment(Qt.AlignmentFlag.AlignLeft)

        vl.addWidget(icon)
        vl.addWidget(lbl)
        vl.addWidget(sub)
        vl.addWidget(_sep())
        vl.addWidget(desc, 1)
        self._refresh_style()

    def _refresh_style(self):
        d = self._data
        if self._sel:
            self.setStyleSheet(
                f"QFrame{{background:{C['bg4']};border:2px solid {d['color']};"
                f"border-radius:10px;}}"
            )
        else:
            self.setStyleSheet(
                f"QFrame{{background:{C['bg2']};border:1px solid {C['border2']};"
                f"border-radius:10px;}}"
                f"QFrame:hover{{background:{C['bg3']};"
                f"border:1px solid {d['border']};}}"
            )

    def set_selected(self, v):
        self._sel = v
        self._refresh_style()

    def mousePressEvent(self, e):
        self.selected.emit(self._key)
        super().mousePressEvent(e)


# ─────────────────────────────────────────────────────────────────────────────
# MODE SELECT SCREEN
# ─────────────────────────────────────────────────────────────────────────────
class ModeSelectScreen(QWidget):
    mode_chosen = pyqtSignal(object)  # (mode, difficulty) tuple or "back" string

    def __init__(self, player):
        super().__init__()
        self.player = player
        self._mode  = "mixed"
        self._cards = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame(); hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            f"background:{C['bg2']};border-bottom:1px solid {C['border']};"
        )
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0)
        back = QPushButton("← Back to Dashboard")
        back.setStyleSheet(_btn())
        back.clicked.connect(lambda: self.mode_chosen.emit("back"))
        hl.addWidget(back); hl.addStretch()
        hl.addWidget(_lbl("CHOOSE YOUR INTERFACE", C["gold"], 13, bold=True,
                           align=Qt.AlignmentFlag.AlignCenter))
        hl.addStretch()
        root.addWidget(hdr)

        # Body
        body = QWidget(); body.setStyleSheet(f"background:{C['bg']};")
        bvl  = QVBoxLayout(body)
        bvl.setContentsMargins(40, 28, 40, 28)
        bvl.setSpacing(18)

        bvl.addWidget(_lbl(
            f"Logged in as  {self.player['username']}  ·  "
            f"LV {self.player['level']}  ·  {self.player['escapes']} escapes",
            C["text2"], 11, align=Qt.AlignmentFlag.AlignCenter
        ))

        # Cards row
        cards_row = QHBoxLayout(); cards_row.setSpacing(16)
        for key in ("mixed", "gui", "cli"):
            card = ModeCard(key)
            card.selected.connect(self._select)
            self._cards[key] = card
            cards_row.addWidget(card)
        bvl.addLayout(cards_row)

        # C extension badge
        c_ok  = c_available()
        c_txt = ("[ C ] questhash.so loaded — FNV-1a hash · 5th language active"
                  if c_ok else
                  "[ C ] questhash.so not found — Python fallback active")
        bvl.addWidget(_lbl(c_txt, C["green"] if c_ok else C["amber"],
                           10, align=Qt.AlignmentFlag.AlignCenter))
        bvl.addWidget(_sep())

        # ── Difficulty selector ────────────────────────────────────────────────
        bvl.addWidget(_lbl("SELECT DIFFICULTY", C["gold"], 11, bold=True,
                           align=Qt.AlignmentFlag.AlignCenter))
        self._difficulty = "normal"
        self._diff_btns  = {}
        diff_row = QHBoxLayout(); diff_row.setSpacing(8)
        from game_data import DIFFICULTIES
        for dkey, ddata in DIFFICULTIES.items():
            db = QPushButton(f"{ddata['label']}")
            db.setCheckable(True)
            db.setFont(QFont("Courier New", 11))
            db.setStyleSheet(
                f"QPushButton{{background:transparent;color:{ddata['color']};"
                f"border:1px solid {ddata['color']};border-radius:5px;padding:6px 10px;}}"
                f"QPushButton:checked{{background:{C['bg4']};border-width:2px;}}"
                f"QPushButton:hover{{background:{C['bg3']};}}"
            )
            db.clicked.connect(lambda c=False, k=dkey: self._select_diff(k))
            diff_row.addWidget(db)
            self._diff_btns[dkey] = db
        bvl.addLayout(diff_row)

        self._diff_desc = _lbl(
            DIFFICULTIES["normal"]["desc"],
            C["text2"], 10, align=Qt.AlignmentFlag.AlignCenter
        )
        bvl.addWidget(self._diff_desc)

        # XP preview strip
        self._xp_preview = _lbl(
            "Escape XP: 400  ·  Per puzzle: 25  ·  Per room: 50  ·  Time: 15:00",
            C["amber"], 10, align=Qt.AlignmentFlag.AlignCenter
        )
        bvl.addWidget(self._xp_preview)
        bvl.addWidget(_sep())

        # Selection label
        self._sel_lbl = _lbl(
            "Selected: MIXED — Split-pane CLI + GUI",
            C["gold"], 11, align=Qt.AlignmentFlag.AlignCenter
        )
        bvl.addWidget(self._sel_lbl)

        # Launch button
        self._launch_btn = QPushButton("[ ENTER VAULT ZERO ]")
        self._launch_btn.setFixedHeight(46)
        self._launch_btn.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._launch_btn.setStyleSheet(_btn(C["gold"], C["gold2"], size=14))
        self._launch_btn.clicked.connect(self._launch)
        bvl.addWidget(self._launch_btn)

        bvl.addWidget(_lbl(
            "stack: python · sql · lua · bash · c (questhash.so)",
            C["text3"], 10, align=Qt.AlignmentFlag.AlignCenter
        ))
        root.addWidget(body, 1)
        self._select("mixed")
        self._select_diff("normal")

    def _select(self, key):
        self._mode = key
        for k, card in self._cards.items():
            card.set_selected(k == key)
        labels = {
            "mixed": "MIXED — Split-pane CLI + GUI",
            "gui":   "GUI ONLY — Point-and-click",
            "cli":   "CLI ONLY — Terminal purist",
        }
        self._sel_lbl.setText(f"Selected: {labels[key]}")

    def _select_diff(self, key: str):
        from game_data import DIFFICULTIES
        self._difficulty = key
        ddata = DIFFICULTIES[key]
        for k, btn in self._diff_btns.items():
            btn.setChecked(k == key)
        self._diff_desc.setText(ddata["desc"])
        mins, secs = divmod(ddata["time_limit"], 60)
        self._xp_preview.setText(
            f"Escape XP: {ddata['xp_escape']}  ·  "
            f"Per puzzle: {ddata['xp_per_puzzle']}  ·  "
            f"Per room: {ddata['xp_per_room']}  ·  "
            f"Time: {mins:02d}:{secs:02d}"
        )

    def _launch(self):
        game_log(f"Mode={self._mode} diff={self._difficulty} player={self.player['username']}")
        self.mode_chosen.emit((self._mode, self._difficulty))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN MENU / DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
class MainMenuScreen(QWidget):
    play_requested   = pyqtSignal(object)  # (mode, difficulty) tuple
    logout_requested = pyqtSignal()

    def __init__(self, player):
        super().__init__()
        self.player = player
        self._build_shell()
        self._show_dashboard()

    # ── Shell (persistent header + status bar) ─────────────────────────────────
    def _build_shell(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        hdr = QFrame(); hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            f"background:{C['bg2']};border-bottom:1px solid {C['border']};"
        )
        hl = QHBoxLayout(hdr); hl.setContentsMargins(20, 0, 20, 0); hl.setSpacing(14)
        title = QLabel("VAULT ZERO")
        title.setFont(QFont("Georgia", 14, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color:{C['gold']};letter-spacing:3px;background:transparent;"
        )
        ver = QLabel("v1.0")
        ver.setFont(QFont("Courier New", 9))
        ver.setStyleSheet(
            f"color:{C['text3']};background:transparent;margin-top:4px;"
        )
        hl.addWidget(title); hl.addWidget(ver); hl.addStretch()

        for label, slot in [
            ("Dashboard",   self._show_dashboard),
            ("Leaderboard", self._show_leaderboard),
            ("Settings",    self._show_settings),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(_btn())
            b.clicked.connect(slot)
            hl.addWidget(b)

        logout = QPushButton("Logout")
        logout.setStyleSheet(_btn(C["red"], C["red"]))
        logout.clicked.connect(self.logout_requested.emit)
        hl.addWidget(logout)
        root.addWidget(hdr)

        # Body container
        self._body = QWidget()
        self._body.setStyleSheet(f"background:{C['bg']};")
        self._body_vl = QVBoxLayout(self._body)
        self._body_vl.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._body, 1)

        # Status bar
        bot = QFrame(); bot.setFixedHeight(26)
        bot.setStyleSheet(
            f"background:#040302;border-top:1px solid {C['border']};"
        )
        bl = QHBoxLayout(bot); bl.setContentsMargins(14, 0, 14, 0)
        self._status = _lbl(
            "db: arena.db | game.log | questhash.so", C["text3"], 10
        )
        langs = _lbl(
            "python · sql · lua · bash · c",
            C["text3"], 10, align=Qt.AlignmentFlag.AlignRight
        )
        bl.addWidget(self._status); bl.addStretch(); bl.addWidget(langs)
        root.addWidget(bot)

    def _clear_body(self):
        while self._body_vl.count():
            w = self._body_vl.takeAt(0).widget()
            if w: w.deleteLater()

    # ── Dashboard ──────────────────────────────────────────────────────────────
    def _show_dashboard(self):
        self._clear_body()
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea{{background:{C['bg']};border:none;}}"
            f"QWidget#inner{{background:{C['bg']};}}"
        )
        inner = QWidget(); inner.setObjectName("inner")
        inner.setStyleSheet(f"background:{C['bg']};")
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(40, 24, 40, 30)
        vl.setSpacing(20)

        # Animated ASCII title
        vl.addWidget(AnimatedTitle())

        # Greeting + session token from C layer
        tok = quest_hash("storage", "welcome", 0)
        vl.addWidget(_lbl(
            f"Welcome back,  {self.player['username']}   ·   session: {tok}",
            C["text2"], 11, align=Qt.AlignmentFlag.AlignCenter
        ))
        vl.addWidget(_sep())

        # Stat cards row
        sr = QHBoxLayout(); sr.setSpacing(12)
        current_rank, next_rank, xp_left, pct = self._rank_info()
        for lbl, val, col in [
            ("LEVEL",    str(self.player["level"]),    C["gold"]),
            ("TOTAL XP", str(self.player["total_xp"]), C["amber"]),
            ("ESCAPES",  str(self.player["escapes"]),  C["teal"]),
            ("RANK",     f"{current_rank[3]} {current_rank[1]}", current_rank[2]),
        ]:
            sr.addWidget(StatCard(lbl, val, col))
        vl.addLayout(sr)

        # Rank progress bar
        vl.addWidget(_build_rank_progress(self.player, self))

        # Big play button
        play = QPushButton("[ PLAY VAULT ZERO ]")
        play.setFixedHeight(52)
        play.setFont(QFont("Courier New", 15, QFont.Weight.Bold))
        play.setStyleSheet(_btn(C["gold"], C["gold2"], size=15))
        play.clicked.connect(self._show_mode_select)
        vl.addWidget(play)
        vl.addWidget(_lbl(
            "You will choose  CLI / GUI / Mixed  before the game starts",
            C["text3"], 10, align=Qt.AlignmentFlag.AlignCenter
        ))
        vl.addWidget(_sep())

        # Two-column: tips + leaderboard
        cols = QHBoxLayout(); cols.setSpacing(16)

        # Left column: session info + rank ladder
        lf = QFrame()
        lf.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border2']};"
            f"border-radius:8px;}}"
        )
        lvl = QVBoxLayout(lf); lvl.setContentsMargins(14, 12, 14, 12); lvl.setSpacing(6)

        # Session info
        lvl.addWidget(_lbl("PLAYER INFO", C["gold"], 10, bold=True))
        lvl.addWidget(_sep())
        last = self.player.get("last_login") or "First login"
        for k, v in [
            ("Username",   self.player["username"]),
            ("Last login", str(last)[:19]),
            ("Level",      str(self.player["level"])),
            ("Total XP",   str(self.player["total_xp"])),
        ]:
            lvl.addWidget(_lbl(f"{k:<12}: {v}", C["text2"], 10))

        # Rank ladder
        lvl.addSpacing(6)
        lvl.addWidget(_sep())
        lvl.addWidget(_lbl("RANK LADDER", C["gold"], 10, bold=True))
        lvl.addWidget(_sep())
        xp_now = self.player.get("total_xp", 0)
        for min_xp, rname, rcol, rbadge in self.RANK_TABLE:
            is_current = self._rank_name_for(xp_now) == rname
            is_achieved = xp_now >= min_xp
            is_next     = (not is_achieved and
                           self._rank_name_for(xp_now) ==
                           self.RANK_TABLE[max(0, self.RANK_TABLE.index(
                               next(r for r in self.RANK_TABLE if r[1] == self._rank_name_for(xp_now))
                           ) )][1])
            row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
            rhl   = QHBoxLayout(row_w)
            rhl.setContentsMargins(0, 1, 0, 1); rhl.setSpacing(6)

            # Badge
            badge_lbl = QLabel(rbadge)
            badge_lbl.setFont(QFont("Courier New", 11))
            badge_lbl.setFixedWidth(18)
            badge_lbl.setStyleSheet(
                f"color:{rcol if is_achieved else C['dim']};background:transparent;")
            rhl.addWidget(badge_lbl)

            # Rank name
            name_lbl = QLabel(rname)
            name_lbl.setFont(QFont("Courier New", 10,
                QFont.Weight.Bold if is_current else QFont.Weight.Normal))
            name_lbl.setStyleSheet(
                f"color:{rcol if is_achieved else C['dim']};background:transparent;")
            rhl.addWidget(name_lbl)
            rhl.addStretch()

            # XP threshold
            xp_lbl = QLabel(f"{min_xp} XP")
            xp_lbl.setFont(QFont("Courier New", 9))
            xp_lbl.setStyleSheet(
                f"color:{C['text3'] if not is_achieved else C['dim']};background:transparent;")
            rhl.addWidget(xp_lbl)

            # Current marker
            if is_current:
                cur_lbl = QLabel("◄ you")
                cur_lbl.setFont(QFont("Courier New", 9))
                cur_lbl.setStyleSheet(f"color:{rcol};background:transparent;")
                rhl.addWidget(cur_lbl)

            lvl.addWidget(row_w)

        lvl.addStretch()
        cols.addWidget(lf, 1)
        cols.addWidget(LeaderboardWidget(), 1)
        vl.addLayout(cols)

        # C extension status row
        c_ok = c_available()
        cr = QHBoxLayout()
        cr.addWidget(_lbl(
            "●", C["green"] if c_ok else C["amber"], 12
        ))
        cr.addWidget(_lbl(
            (f"C extension (questhash.so) — active · FNV-1a hashing · 5th language"
             if c_ok else
             "C extension (questhash.so) — not found · Python fallback active"),
            C["green"] if c_ok else C["amber"], 10
        ))
        cr.addStretch()
        vl.addLayout(cr)
        vl.addStretch()

        scroll.setWidget(inner)
        self._body_vl.addWidget(scroll)

    # ── Rank system ────────────────────────────────────────────────────────────
    RANK_TABLE = [
        # (min_xp, name,       color,        badge)
        # Thresholds inflated so ranks feel earned across many runs
        (0,      "Rookie",    "#8a7a65",    "◈"),   # starting rank
        (1000,   "Agent",     "#4a8a4a",    "◉"),   # ~1 easy full run
        (3000,   "Breaker",   "#4a7ab0",    "◆"),   # ~3 easy / 1 normal
        (7000,   "Ghost",     "#7a5ab0",    "✦"),   # ~2 normal full runs
        (15000,  "Phantom",   "#d4a853",    "★"),   # ~1 hard full run
        (30000,  "Wraith",    "#aa4a4a",    "☿"),   # ~2 hard runs
        (60000,  "Specter",   "#3a7a7a",    "⬡"),   # ~1 nightmare full run
        (120000, "Cipher",    "#d4a853",    "⬟"),   # elite — multiple nightmare
    ]

    def _rank_info(self, xp=None):
        """Return (current_rank, next_rank, xp_to_next, progress_pct) for given XP."""
        xp = xp if xp is not None else self.player.get("total_xp", 0)
        current = self.RANK_TABLE[0]
        next_rank = None
        for i, entry in enumerate(self.RANK_TABLE):
            if xp >= entry[0]:
                current = entry
                next_rank = self.RANK_TABLE[i + 1] if i + 1 < len(self.RANK_TABLE) else None
            else:
                break
        if next_rank:
            span     = max(1, next_rank[0] - current[0])
            earned   = xp - current[0]
            pct      = min(100, int((earned / span) * 100))
            xp_left  = next_rank[0] - xp
        else:
            pct     = 100
            xp_left = 0
        return current, next_rank, xp_left, pct

    def _rank(self):
        current, _, _, _ = self._rank_info()
        return current[1]

    def _rank_badge(self, xp=None):
        current, _, _, _ = self._rank_info(xp)
        return current[3]

    def _rank_name_for(self, xp):
        current, _, _, _ = self._rank_info(xp)
        return current[1]

    def _rank_color_for(self, xp):
        current, _, _, _ = self._rank_info(xp)
        return current[2]

    # ── Mode select ────────────────────────────────────────────────────────────
    def _show_mode_select(self):
        self._clear_body()
        ms = ModeSelectScreen(self.player)
        ms.mode_chosen.connect(self._on_mode)
        self._body_vl.addWidget(ms)

    def _on_mode(self, mode):
        if mode == "back":
            self._show_dashboard()
        else:
            self.play_requested.emit(mode)

    # ── Leaderboard ────────────────────────────────────────────────────────────
    def _show_leaderboard(self):
        self._clear_body()
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea{{background:{C['bg']};border:none;}}"
            f"QWidget{{background:{C['bg']};}}"
        )
        inner = QWidget(); inner.setStyleSheet(f"background:{C['bg']};")
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(40, 28, 40, 28)
        vl.setSpacing(14)

        vl.addWidget(_lbl(
            "GLOBAL LEADERBOARD", C["gold"], 16, bold=True,
            align=Qt.AlignmentFlag.AlignCenter
        ))
        vl.addWidget(_sep())

        _RANKS = [
            (0,      "Rookie",  "#8a7a65", "◈"),
            (1000,   "Agent",   "#4a8a4a", "◉"),
            (3000,   "Breaker", "#4a7ab0", "◆"),
            (7000,   "Ghost",   "#7a5ab0", "✦"),
            (15000,  "Phantom", "#d4a853", "★"),
            (30000,  "Wraith",  "#aa4a4a", "☿"),
            (60000,  "Specter", "#3a7a7a", "⬡"),
            (120000, "Cipher",  "#d4a853", "⬟"),
        ]
        def get_rank(xp):
            r = _RANKS[0]
            for entry in _RANKS:
                if xp >= entry[0]: r = entry
            return r

        rows = get_leaderboard()
        medals = ["🥇", "🥈", "🥉"]
        pos_col = [C["gold"], "#9a9a9a", "#9a6a3a"]
        if not rows:
            vl.addWidget(_lbl(
                "No runs yet. Be the first to escape.",
                C["text3"], 12, align=Qt.AlignmentFlag.AlignCenter
            ))
        for i, row in enumerate(rows):
            is_me  = row["username"] == self.player["username"]
            rank   = get_rank(row["total_xp"])
            pc     = pos_col[i] if i < 3 else C["text2"]

            rf = QFrame()
            rf.setStyleSheet(
                f"QFrame{{background:{'#1e1808' if is_me else C['bg2']};"
                f"border:1px solid {rank[2] if is_me else C['border2']};"
                f"border-radius:6px;}}"
            )
            rl = QHBoxLayout(rf); rl.setContentsMargins(14, 10, 14, 10); rl.setSpacing(6)

            # Position
            pos_w = QLabel(medals[i] if i < 3 else f"#{i+1}")
            pos_w.setFont(QFont("Courier New", 13))
            pos_w.setFixedWidth(30)
            pos_w.setStyleSheet(f"color:{pc};background:transparent;")
            rl.addWidget(pos_w)

            # Rank badge
            badge_w = QLabel(rank[3])
            badge_w.setFont(QFont("Courier New", 14))
            badge_w.setFixedWidth(22)
            badge_w.setStyleSheet(f"color:{rank[2]};background:transparent;")
            rl.addWidget(badge_w)

            # Name + you marker
            name_w = QLabel(row["username"] + ("  ← you" if is_me else ""))
            name_w.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
            name_w.setStyleSheet(f"color:{C['text']};background:transparent;")
            rl.addWidget(name_w); rl.addStretch()

            # Rank name
            rname_w = QLabel(rank[1])
            rname_w.setFont(QFont("Courier New", 11))
            rname_w.setStyleSheet(f"color:{rank[2]};background:transparent;")
            rl.addWidget(rname_w)

            # Level, XP, escapes
            for val, col in [
                (f"  LV {row['level']}",        C["text3"]),
                (f"  {row['total_xp']} XP",     C["amber"]),
                (f"  {row['escapes']} escapes",  C["teal"]),
            ]:
                sl = QLabel(val)
                sl.setFont(QFont("Courier New", 10))
                sl.setStyleSheet(f"color:{col};background:transparent;")
                rl.addWidget(sl)
            vl.addWidget(rf)

        back = QPushButton("← Back to Dashboard")
        back.setStyleSheet(_btn())
        back.clicked.connect(self._show_dashboard)
        vl.addStretch(); vl.addWidget(back)
        scroll.setWidget(inner)
        self._body_vl.addWidget(scroll)

    # ── Settings ───────────────────────────────────────────────────────────────
    def _show_settings(self):
        self._clear_body()
        inner = QWidget(); inner.setStyleSheet(f"background:{C['bg']};")
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(40, 28, 40, 28)
        vl.setSpacing(16)

        vl.addWidget(_lbl(
            "SETTINGS & SYSTEM INFO", C["gold"], 16, bold=True,
            align=Qt.AlignmentFlag.AlignCenter
        ))
        vl.addWidget(_sep())

        # System info
        sf = QFrame()
        sf.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border2']};"
            f"border-radius:8px;}}"
        )
        sg = QGridLayout(sf); sg.setContentsMargins(20, 16, 20, 16); sg.setSpacing(10)
        c_ok = c_available()
        items = [
            ("Game",         "Vault Zero v1.0"),
            ("Python",       sys.version.split()[0]),
            ("GUI Layer",    "PyQt6"),
            ("Database",     "SQLite (arena.db)"),
            ("Config",       "game.ini"),
            ("Event Scripts","quests/events.lua  (Lua)"),
            ("C Extension",  f"questhash.so  ({'loaded ✓' if c_ok else 'not found'})"),
            ("Languages",    "Python · SQL · Lua · Bash · C"),
            ("DB Formats",   "SQLite · INI · JSON · CSV · TXT"),
        ]
        for r, (k, v) in enumerate(items):
            sg.addWidget(_lbl(k, C["text2"], 11), r, 0)
            sg.addWidget(_lbl(v, C["text"],  11), r, 1)
        vl.addWidget(sf)

        # Live C extension test
        if c_ok:
            cf = QFrame()
            cf.setStyleSheet(
                f"QFrame{{background:{C['bg3']};border:1px solid {C['border2']};"
                f"border-radius:6px;}}"
            )
            cvl = QVBoxLayout(cf); cvl.setContentsMargins(14, 12, 14, 12); cvl.setSpacing(6)
            cvl.addWidget(_lbl("C EXTENSION — LIVE HASH TEST", C["gold"], 10, bold=True))
            cvl.addWidget(_sep())
            for rm, pz in [("storage","toolbox"),("lab","specimenCabinet"),("vault","briefcase")]:
                h = quest_hash(rm, pz, 0)
                cvl.addWidget(_lbl(
                    f"quest_hash({rm}, {pz}, 0)  →  0x{h}",
                    C["green"], 10
                ))
            vl.addWidget(cf)

        back = QPushButton("← Back to Dashboard")
        back.setStyleSheet(_btn())
        back.clicked.connect(self._show_dashboard)
        vl.addStretch(); vl.addWidget(back)
        self._body_vl.addWidget(inner)


# Alias so main.py can do: from main_menu import MainMenu
MainMenu = MainMenuScreen

def _build_rank_progress(player: dict, screen) -> QFrame:
    """
    Builds a rank progress bar widget showing:
    - Current rank badge + name
    - XP progress bar toward next rank
    - Next rank badge + name + XP needed
    - Full rank ladder preview (all future ranks)
    """
    current, next_rank, xp_left, pct = screen._rank_info()
    xp_now = player.get("total_xp", 0)

    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:{C['bg2']};border:1px solid {C['border2']};"
        f"border-radius:8px;}}"
    )
    vl = QVBoxLayout(frame); vl.setContentsMargins(14, 12, 14, 12); vl.setSpacing(8)

    # Header
    vl.addWidget(_lbl("RANK PROGRESS", C["gold"], 10, bold=True))

    # Current → Next rank row
    top_row = QHBoxLayout(); top_row.setSpacing(8)

    # Current rank
    cur_box = QFrame()
    cur_box.setStyleSheet(
        f"QFrame{{background:{C['bg3']};border:1px solid {current[2]};"
        f"border-radius:5px;}}"
    )
    cb = QVBoxLayout(cur_box); cb.setContentsMargins(10, 6, 10, 6); cb.setSpacing(2)
    cb_badge = QLabel(current[3])
    cb_badge.setFont(QFont("Courier New", 18))
    cb_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cb_badge.setStyleSheet(f"color:{current[2]};background:transparent;")
    cb_name = QLabel(current[1])
    cb_name.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
    cb_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cb_name.setStyleSheet(f"color:{current[2]};background:transparent;")
    cb_label = QLabel("CURRENT")
    cb_label.setFont(QFont("Courier New", 8))
    cb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    cb_label.setStyleSheet(f"color:{C['text3']};background:transparent;")
    cb.addWidget(cb_badge); cb.addWidget(cb_name); cb.addWidget(cb_label)
    top_row.addWidget(cur_box)

    # Progress bar + XP text
    prog_col = QVBoxLayout(); prog_col.setSpacing(4)
    prog_col.addStretch()

    xp_text_row = QHBoxLayout()
    xp_text_row.addWidget(_lbl(f"{xp_now} XP", current[2], 9))
    xp_text_row.addStretch()
    if next_rank:
        xp_text_row.addWidget(_lbl(f"{next_rank[0]} XP", next_rank[2], 9))
    prog_col.addLayout(xp_text_row)

    # Animated QProgressBar — animates from 0 → pct on show
    from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
    anim_bar = QProgressBar()
    anim_bar.setFixedHeight(12)
    anim_bar.setMinimum(0)
    anim_bar.setMaximum(100)
    anim_bar.setValue(0)          # start at 0, animate to pct
    anim_bar.setTextVisible(False)
    anim_bar.setStyleSheet(
        f"QProgressBar{{background:{C['bg3']};border:1px solid {C['border']};"
        f"border-radius:5px;}}"
        f"QProgressBar::chunk{{background:qlineargradient("
        f"x1:0,y1:0,x2:1,y2:0,"
        f"stop:0 {current[2]},stop:1 {next_rank[2] if next_rank else current[2]});"
        f"border-radius:5px;}}"
    )
    prog_col.addWidget(anim_bar)

    # Animate fill after a short delay (so widget is visible when animation runs)
    def _start_anim():
        anim = QPropertyAnimation(anim_bar, b"value")
        anim.setDuration(900)
        anim.setStartValue(0)
        anim.setEndValue(pct)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        # Keep reference alive so GC doesn't kill it mid-animation
        anim_bar._anim = anim

    QTimer.singleShot(120, _start_anim)

    if next_rank:
        prog_col.addWidget(_lbl(
            f"{xp_left} XP to {next_rank[1]}",
            C["text3"], 9, align=Qt.AlignmentFlag.AlignCenter
        ))
    else:
        prog_col.addWidget(_lbl(
            "Maximum rank achieved", C["gold"], 9,
            align=Qt.AlignmentFlag.AlignCenter
        ))

    prog_col.addStretch()
    top_row.addLayout(prog_col, 1)

    # Next rank box (or max rank)
    if next_rank:
        nxt_box = QFrame()
        nxt_box.setStyleSheet(
            f"QFrame{{background:{C['bg3']};border:1px solid {C['border2']};"
            f"border-radius:5px;}}"
        )
        nb = QVBoxLayout(nxt_box); nb.setContentsMargins(10, 6, 10, 6); nb.setSpacing(2)
        nb_badge = QLabel(next_rank[3])
        nb_badge.setFont(QFont("Courier New", 18))
        nb_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nb_badge.setStyleSheet(f"color:{C['dim']};background:transparent;")
        nb_name = QLabel(next_rank[1])
        nb_name.setFont(QFont("Courier New", 10))
        nb_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nb_name.setStyleSheet(f"color:{C['dim']};background:transparent;")
        nb_label = QLabel("NEXT")
        nb_label.setFont(QFont("Courier New", 8))
        nb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nb_label.setStyleSheet(f"color:{C['text3']};background:transparent;")
        nb.addWidget(nb_badge); nb.addWidget(nb_name); nb.addWidget(nb_label)
        top_row.addWidget(nxt_box)

    vl.addLayout(top_row)

    # Future ranks preview strip
    future_ranks = [r for r in screen.RANK_TABLE if r[0] > xp_now]
    if future_ranks:
        vl.addWidget(_sep())
        vl.addWidget(_lbl("UPCOMING RANKS", C["text3"], 9, bold=True))
        strip = QHBoxLayout(); strip.setSpacing(6)
        for fr in future_ranks[:5]:   # show up to 5 future ranks
            fb = QFrame()
            fb.setStyleSheet(
                f"QFrame{{background:{C['bg3']};border:1px solid {C['border']};"
                f"border-radius:4px;}}"
            )
            fb_vl = QVBoxLayout(fb); fb_vl.setContentsMargins(6, 4, 6, 4); fb_vl.setSpacing(1)
            fb_badge = QLabel(fr[3])
            fb_badge.setFont(QFont("Courier New", 12))
            fb_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fb_badge.setStyleSheet(f"color:{C['dim']};background:transparent;")
            fb_name = QLabel(fr[1])
            fb_name.setFont(QFont("Courier New", 8))
            fb_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fb_name.setStyleSheet(f"color:{C['dim']};background:transparent;")
            fb_xp = QLabel(f"{fr[0]}XP")
            fb_xp.setFont(QFont("Courier New", 7))
            fb_xp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fb_xp.setStyleSheet(f"color:{C['text3']};background:transparent;")
            fb_vl.addWidget(fb_badge); fb_vl.addWidget(fb_name); fb_vl.addWidget(fb_xp)
            strip.addWidget(fb)
        strip.addStretch()
        vl.addLayout(strip)

    return frame