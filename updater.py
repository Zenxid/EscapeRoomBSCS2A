"""
updater.py — GitHub Repository ZIP auto-updater for Vault Zero
Downloads the entire repo as ZIP, extracts it, and replaces files.
Repository: https://github.com/Zenxid/EscapeRoomBSCS2A
"""

import sys
import os
import json
import urllib.request
import urllib.error
import tempfile
import shutil
import subprocess
import zipfile
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG — UPDATE THESE VALUES
# ═════════════════════════════════════════════════════════════════════════════
GITHUB_OWNER = "Zenxid"
GITHUB_REPO  = "EscapeRoomBSCS2A"
CURRENT_VERSION = "1.0.2"        # ← BUMP THIS before each release
BRANCH = "main"                  # ← Branch to download (main, master, etc.)

# GitHub API URL for latest commit on branch (to check if update needed)
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{BRANCH}"
# GitHub ZIP download URL
GITHUB_ZIP_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{BRANCH}.zip"

# Files/folders to extract and replace (relative to repo root)
# The ZIP extracts to: EscapeRoomBSCS2A-main/  ← adjust if your branch name differs
REPO_FOLDER_NAME = f"{GITHUB_REPO}-{BRANCH}"  # e.g., "EscapeRoomBSCS2A-main"

# ═════════════════════════════════════════════════════════════════════════════
# VERSION / COMMIT CHECK
# ═════════════════════════════════════════════════════════════════════════════
def get_latest_commit_info():
    """Fetch latest commit SHA and message from GitHub API."""
    req = urllib.request.Request(
        GITHUB_API_URL,
        headers={
            "User-Agent": f"VaultZero-Updater/{CURRENT_VERSION}",
            "Accept": "application/vnd.github+json",
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {
        "sha": data.get("sha", "")[:7],
        "message": data.get("commit", {}).get("message", "No message"),
        "date": data.get("commit", {}).get("committer", {}).get("date", "")[:10],
    }

def load_local_version():
    """Load last known commit SHA from local file."""
    version_file = os.path.join(os.path.dirname(sys.executable), ".version")
    if os.path.exists(version_file):
        with open(version_file, "r") as f:
            return f.read().strip()
    return CURRENT_VERSION  # fallback

def save_local_version(sha):
    """Save commit SHA to local file after successful update."""
    version_file = os.path.join(os.path.dirname(sys.executable), ".version")
    with open(version_file, "w") as f:
        f.write(sha)

# ═════════════════════════════════════════════════════════════════════════════
# SHARED PALETTE
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

            with urllib.request.urlopen(req, timeout=120) as resp:
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
    def __init__(self, commit_info: dict, parent=None):
        super().__init__(parent)
        self.commit = commit_info
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
            f"<b>New commit:</b> {self.commit['sha']}<br>"
            f"<b>Date:</b> {self.commit['date']}<br>"
            f"<b>Current:</b> v{CURRENT_VERSION}"
        )
        info.setFont(QFont("Courier New", 10))
        info.setStyleSheet(f"color:{C['text2']};")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        vl.addWidget(info)

        # Commit message
        vl.addWidget(QLabel("LATEST CHANGES:"))
        msg_box = QTextEdit()
        msg_box.setReadOnly(True)
        msg_box.setFont(QFont("Courier New", 10))
        msg_box.setText(self.commit["message"])
        msg_box.setMaximumHeight(80)
        msg_box.setStyleSheet(
            f"background:{C['bg']}; color:{C['text2']}; "
            f"border:1px solid {C['border']}; border-radius:4px; padding:8px;"
        )
        vl.addWidget(msg_box)

        # Note about ZIP download
        note = QLabel(
            "This will download the latest repository ZIP (~5-15 MB)\n"
            "and extract the updated files."
        )
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

        self._btn_update = QPushButton("[ DOWNLOAD & UPDATE ]")
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
        self._status.setText("Downloading repository ZIP...")
        self._status.setStyleSheet(f"color:{C['amber']};")

        # Download to temp folder
        tmp_dir = tempfile.gettempdir()
        dest = os.path.join(tmp_dir, f"VaultZero_repo_{self.commit['sha']}.zip")

        self.worker = DownloadWorker(GITHUB_ZIP_URL, dest)
        self.worker.progress.connect(self._prog.setValue)
        self.worker.log_line.connect(self._status.setText)
        self.worker.finished_ok.connect(self._on_download_ok)
        self.worker.finished_err.connect(self._on_download_err)
        self.worker.start()

    def _on_download_ok(self, path: str):
        self.downloaded_path = path
        self._status.setText("Download complete. Extracting...")
        self._status.setStyleSheet(f"color:{C['green']};")
        self._extract_and_install()

    def _on_download_err(self, msg: str):
        self._status.setText(f"Download failed: {msg}")
        self._status.setStyleSheet(f"color:{C['red']};")
        self._btn_update.setEnabled(True)
        self._btn_later.setEnabled(True)

    def _extract_and_install(self):
        """Extract ZIP and copy updated files to game directory."""
        try:
            current_dir = os.path.dirname(sys.executable)
            temp_extract = tempfile.mkdtemp(prefix="vaultzero_update_")

            # Extract ZIP
            self._status.setText("Extracting ZIP...")
            with zipfile.ZipFile(self.downloaded_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract)

            # Find the extracted folder (e.g., EscapeRoomBSCS2A-main)
            extracted_folder = os.path.join(temp_extract, REPO_FOLDER_NAME)
            if not os.path.exists(extracted_folder):
                # Try to find any folder that matches
                items = os.listdir(temp_extract)
                for item in items:
                    if os.path.isdir(os.path.join(temp_extract, item)):
                        extracted_folder = os.path.join(temp_extract, item)
                        break

            if not os.path.exists(extracted_folder):
                raise Exception(f"Could not find extracted folder. Expected: {REPO_FOLDER_NAME}")

            # Files to update (whitelist approach — safer)
            files_to_update = [
                "main.py", "main_menu.py", "game_engine.py", "game_data.py",
                "db.py", "lua_bridge.py", "c_bridge.py", "audio.py",
                "icon_gen.py", "questhash_bridge.py", "updater.py",
                "events.lua", "game.ini", "quests.json",
                "assets",  # folder
            ]

            self._status.setText("Replacing files...")
            updated_count = 0

            for item in files_to_update:
                src = os.path.join(extracted_folder, item)
                dst = os.path.join(current_dir, item)

                if not os.path.exists(src):
                    continue  # skip if not in repo

                try:
                    if os.path.isdir(src):
                        # Remove old folder and copy new one
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                    else:
                        # Backup old file
                        if os.path.exists(dst):
                            backup = dst + ".old"
                            if os.path.exists(backup):
                                os.remove(backup)
                            os.rename(dst, backup)
                        # Copy new file
                        shutil.copy2(src, dst)
                    updated_count += 1
                except Exception as e:
                    self._status.setText(f"Warning: Could not update {item}: {e}")

            # Save new version
            save_local_version(self.commit["sha"])

            self._status.setText(f"Update complete! ({updated_count} files updated)")
            
            # Ask to restart
            self._ask_restart()

        except Exception as e:
            self._status.setText(f"Install failed: {e}")
            self._status.setStyleSheet(f"color:{C['red']};")
            self._btn_update.setEnabled(True)
            self._btn_later.setEnabled(True)

    def _ask_restart(self):
        """Show restart dialog."""
        reply = QMessageBox.question(
            self,
            "Restart Required",
            "Update installed successfully!\n\nRestart Vault Zero now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._restart_game()
        else:
            self.reject()

    def _restart_game(self):
        """Restart the game executable."""
        exe_path = sys.executable
        current_dir = os.path.dirname(exe_path)
        subprocess.Popen([exe_path], cwd=current_dir, shell=False)
        QApplication.instance().quit()
        sys.exit(0)


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═════════════════════════════════════════════════════════════════════════════
def check_for_update(parent=None, silent=False) -> bool:
    """
    Check GitHub for updates by comparing commit SHA.
    silent=True: only show dialog if update found.
    Returns True if update dialog was shown.
    """
    try:
        latest = get_latest_commit_info()
        local_sha = load_local_version()

        # Compare SHAs (or version strings)
        if latest["sha"] == local_sha:
            if not silent:
                QMessageBox.information(
                    parent,
                    "No Update Available",
                    f"<b>Vault Zero</b> is up to date.<br><br>"
                    f"Current version: <b>v{CURRENT_VERSION}</b><br>"
                    f"Commit: <b>{local_sha}</b>",
                )
            return False

        dlg = UpdateDialog(latest, parent)
        dlg.exec()
        return True

    except urllib.error.HTTPError as e:
        msg = f"GitHub API error (HTTP {e.code}).\n\n"
        if e.code == 404:
            msg += "Repository or branch not found. Check your settings."
        elif e.code == 403:
            msg += "API rate limit exceeded. Try again later."
        else:
            msg += str(e)
        if not silent:
            QMessageBox.warning(parent, "Update Check Failed", msg)
        return False

    except Exception as e:
        if not silent:
            QMessageBox.warning(
                parent,
                "Update Check Failed",
                f"Could not check for updates:<br><br>{e}"
            )
        return False


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