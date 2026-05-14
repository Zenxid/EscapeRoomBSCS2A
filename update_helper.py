"""
update_helper.py — Replaces running VaultZero.exe after it exits
"""

import sys
import os
import time
import shutil
import subprocess

def main():
    if len(sys.argv) < 3:
        print("Usage: update_helper.exe <new_exe> <old_exe>")
        sys.exit(1)

    new_exe = sys.argv[1]
    old_exe = sys.argv[2]
    old_backup = old_exe + ".old"

    time.sleep(2)  # Wait for main game to exit

    try:
        if os.path.exists(old_backup):
            os.remove(old_backup)

        os.rename(old_exe, old_backup)
        shutil.move(new_exe, old_exe)

        subprocess.Popen([old_exe], cwd=os.path.dirname(old_exe))
        print("Update complete!")

    except Exception as e:
        if os.path.exists(old_backup) and not os.path.exists(old_exe):
            os.rename(old_backup, old_exe)
        print(f"Failed: {e}")
        input("Press Enter...")

if __name__ == "__main__":
    main()