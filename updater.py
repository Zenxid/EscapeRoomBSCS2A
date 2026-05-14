"""
updater.py — Single .exe updater for Vault Zero
Downloads complete VaultZero.exe from Git LFS and replaces via helper.
Repository: https://github.com/Zenxid/EscapeRoomBSCS2A
"""

import sys
import os
import urllib.request
import tempfile
import subprocess

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG — UPDATE THESE VALUES BEFORE EACH RELEASE
# ═════════════════════════════════════════════════════════════════════════════
GITHUB_OWNER = "Zenxid"
GITHUB_REPO = "EscapeRoomBSCS2A"
CURRENT_VERSION = "1.0.0"  # ← BUMP THIS before each release

# Git LFS raw download URL (66 MB .exe, no splitting needed)
DOWNLOAD_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/raw/main/dist/VaultZero.exe?download=1"

# ═════════════════════════════════════════════════════════════════════════════
# SHARED PALETTE (matches main.py)
# ═════════════════════════════════════════════════════════════════════════════
C = {
    "bg": "#0a0907", "bg2": "#110f0c", "bg3": "#181410", "bg4": "#1e1a14",
    "border": "#2a2318", "border2": "#3a3020", "border3": "#4a4030",
    "text": "#c9b99a", "text2": "#8a7a65", "text3": "#5a4e3e",
    "gold": "#d4a853", "gold2": "#a07830",
    "green": "#4a8a4a", "red": "#aa4a4a", "amber": "#9a7a2a", "teal": "#3a7a7a",
    "dim": "#5a4e3e",
}

# ═════════════════════════════════════════════════════════════════════════════
# DOWNLOAD WORKER
# ═════════════════════════════════════════════════════════════════════════════
class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    log_line = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    finished_err = pyqtSignal(str)

    def __init__(self, url: str, dest_path: str):
        super().__init__()
        self.url = url
        self.dest = dest_path

    def run(self):
        try:
            self.log_line.emit("Connecting to GitHub...")
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": f"VaultZero-Updater/{CURRENT_VERSION}"}
            )

            with urllib.request.urlopen(req, timeout=300) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 8192

                with open(self.dest, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            self.progress.emit(pct)

            self.progress.emit(100)
            self.finished_ok.emit(self.dest)

        except Exception as e:
            self.finished_err.emit(str(e))


# ═════════════════════════════════════════════════════════════════════════════
# UPDATE DIALOG
# ═════════════════════════════════════════════════════════════════════════════
class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloaded_path = None
        self.worker = None

        self.setWindowTitle("Update Available — Vault Zero")
        self.setMinimumWidth(520)
        self.setMaximumWidth(600)
        self._set_style()

        vl = QVBoxLayout(self)
        vl.setSpacing(14)
        vl.setContentsMargins(24, 24, 24, 24)

        # Header
        hdr = QLabel("★  UPDATE AVAILABLE  ★")
        hdr.setFont(QFont("Georgia", 16, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{C['gold']};")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(hdr)

        # Version info
        info = QLabel(
            f"<b>New version available!</b><br>"
            f"<b>Current:</b> v{CURRENT_VERSION}"
        )
        info.setFont(QFont("Courier New", 10))
        info.setStyleSheet(f"color:{C['text2']};")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        vl.addWidget(info)

        # Note
        note = QLabel("This will download the latest VaultZero.exe (~66 MB)")
        note.setFont(QFont("Courier New", 9))
        note.setStyleSheet(f"color:{C['text3']};")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(note)

        # Progress bar
        self._prog = QProgressBar()
        self._prog.setMaximum(100)
        self._prog.setValue(0)
        self._prog.setTextVisible(True)
        self._prog.setStyleSheet(
            f"QProgressBar{{background:{C['bg3']}; border:1px solid {C['border2']}; "
            f"border-radius:3px; text-align:center; color:{C['text']};}}"
            f"QProgressBar::chunk{{background:{C['green']}; border-radius:3px;}}"
        )
        self._prog.hide()
        vl.addWidget(self._prog)

        # Status label
        self._status = QLabel("")
        self._status.setFont(QFont("Courier New", 9))
        self._status.setStyleSheet(f"color:{C['dim']};")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(self._status)

        # Buttons
        bl = QHBoxLayout()
        bl.setSpacing(10)

        self._btn_later = QPushButton("Remind Me Later")
        self._btn_later.setStyleSheet(self._btn_style(C["text2"], C["border2"]))
        self._btn_later.clicked.connect(self.reject)

        self._btn_update = QPushButton("[ DOWNLOAD & INSTALL ]")
        self._btn_update.setStyleSheet(self._btn_style(C["gold"], C["gold2"]))
        self._btn_update.setDefault(True)
        self._btn_update.clicked.connect(self._start_download)

        bl.addWidget(self._btn_later)
        bl.addWidget(self._btn_update)
        vl.addLayout(bl)

    def _set_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background:{C['bg']}; color:{C['text']}; }}
            QLabel {{ color:{C['text']}; background:transparent; }}
        """)

    def _btn_style(self, color, border):
        return (
            f"QPushButton{{background:transparent;color:{color};border:1px solid {border};"
            f"border-radius:4px;padding:8px 16px;font-family:'Courier New';font-size:11px;}}"
            f"QPushButton:hover{{background:{C['bg4']};color:{C['gold']};border-color:{C['border3']};}}"
            f"QPushButton:pressed{{background:{C['bg3']};}}"
            f"QPushButton:disabled{{color:{C['dim']};border-color:{C['border']};}}"
        )

    def _start_download(self):
        self._btn_update.setEnabled(False)
        self._btn_later.setEnabled(False)
        self._prog.show()
        self._status.setText("Initializing download...")
        self._status.setStyleSheet(f"color:{C['amber']};")

        # Download to temp folder
        tmp_dir = tempfile.gettempdir()
        dest = os.path.join(tmp_dir, "VaultZero_update.exe")

        self.worker = DownloadWorker(DOWNLOAD_URL, dest)
        self.worker.progress.connect(self._prog.setValue)
        self.worker.log_line.connect(self._status.setText)
        self.worker.finished_ok.connect(self._on_download_ok)
        self.worker.finished_err.connect(self._on_download_err)
        self.worker.start()

    def _on_download_ok(self, path: str):
        self.downloaded_path = path
        self._status.setText("Download complete. Installing...")
        self._status.setStyleSheet(f"color:{C['green']};")
        self._install_and_restart()

    def _on_download_err(self, msg: str):
        self._status.setText(f"Download failed: {msg}")
        self._status.setStyleSheet(f"color:{C['red']};")
        self._btn_update.setEnabled(True)
        self._btn_later.setEnabled(True)

    def _install_and_restart(self):
        """Launch updater helper, then exit so it can replace our .exe."""
        try:
            current_exe = sys.executable
            current_dir = os.path.dirname(current_exe)
            helper_exe = os.path.join(current_dir, "VaultZeroUpdater.exe")

            # Check if helper exists
            if not os.path.exists(helper_exe):
                QMessageBox.critical(
                    self, "Error",
                    "VaultZeroUpdater.exe not found.\nPlease re-download the full game package."
                )
                self._btn_update.setEnabled(True)
                self._btn_later.setEnabled(True)
                return

            # Launch helper: passes (new_exe_path, old_exe_path)
            subprocess.Popen(
                [helper_exe, self.downloaded_path, current_exe],
                cwd=current_dir,
                shell=False
            )

            # Exit immediately so helper can do its job
            self._status.setText("Restarting Vault Zero...")
            QTimer.singleShot(800, self._quit_and_exit)

        except Exception as e:
            self._status.setText(f"Install failed: {e}")
            self._status.setStyleSheet(f"color:{C['red']};")
            self._btn_update.setEnabled(True)
            self._btn_later.setEnabled(True)

    def _quit_and_exit(self):
        QApplication.instance().quit()
        sys.exit(0)


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═════════════════════════════════════════════════════════════════════════════
def check_for_update(parent=None, silent=False) -> bool:
    """
    Check for updates. For now, always shows dialog (for testing).
    In production, you could check a version API or file.
    silent=True: only show dialog if update found.
    """
    if silent:
        # For auto-check on startup — skip if you want
        return False

    dlg = UpdateDialog(parent)
    dlg.exec()
    return True


# ═════════════════════════════════════════════════════════════════════════════
# CLEANUP OLD BACKUPS
# ═════════════════════════════════════════════════════════════════════════════
def cleanup_old_backups():
    """Remove .old backup files from previous updates."""
    current_dir = os.path.dirname(sys.executable)
    for item in os.listdir(current_dir):
        if item.endswith(".old"):
            try:
                os.remove(os.path.join(current_dir, item))
            except Exception:
                pass