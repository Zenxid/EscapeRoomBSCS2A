#!/usr/bin/env bash
# launch.sh — Vault Zero PyQt6 launcher (Bash layer)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN="\033[0;32m"; AMBER="\033[0;33m"; RED="\033[0;31m"; DIM="\033[2m"; RST="\033[0m"
ok()  { echo -e "${GREEN}[OK]${RST}  $*"; }
warn(){ echo -e "${AMBER}[WARN]${RST} $*"; }
err() { echo -e "${RED}[ERR]${RST}  $*"; exit 1; }

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${RST}"
echo -e "${GREEN}║    VAULT ZERO — PyQt6 LAUNCHER       ║${RST}"
echo -e "${GREEN}╚══════════════════════════════════════╝${RST}"
echo ""

# Python
command -v python3 &>/dev/null || err "python3 not found"
ok "Python: $(python3 --version)"

# PyQt6
python3 -c "from PyQt6.QtWidgets import QApplication" 2>/dev/null || {
    warn "PyQt6 not found — installing..."
    pip install PyQt6 --break-system-packages -q
}
ok "PyQt6 ready"

# Lua — try to install if missing
if command -v lua &>/dev/null || command -v lua5.4 &>/dev/null \
   || command -v lua5.3 &>/dev/null || command -v lua5.1 &>/dev/null; then
    LUA_BIN=$(command -v lua5.4 || command -v lua5.3 || command -v lua || command -v lua5.1)
    ok "Lua: $LUA_BIN"
else
    warn "Lua not found — attempting install..."
    if command -v apt-get &>/dev/null; then
        apt-get install -y lua5.4 -q 2>/dev/null && ok "Lua installed via apt" \
            || warn "Could not install Lua — python fallback will be used"
    elif command -v brew &>/dev/null; then
        brew install lua && ok "Lua installed via brew" \
            || warn "Could not install Lua — python fallback will be used"
    else
        warn "No package manager found — install Lua manually for full scripting support"
    fi
fi

# C extension — compile questhash.so if missing or source is newer
SO="$SCRIPT_DIR/questhash.so"
SRC="$SCRIPT_DIR/questhash.c"
if [ -f "$SRC" ]; then
    if [ ! -f "$SO" ] || [ "$SRC" -nt "$SO" ]; then
        if command -v gcc &>/dev/null; then
            echo -e "${DIM}  Compiling questhash.so from C source...${RST}"
            gcc -O2 -shared -fPIC -o "$SO" "$SRC" \
                && ok "C extension compiled: questhash.so" \
                || warn "C compilation failed — python fallback will be used"
        else
            warn "gcc not found — C extension unavailable, python fallback will be used"
        fi
    else
        ok "C extension: questhash.so already compiled"
    fi
else
    warn "questhash.c not found — C extension unavailable"
fi

echo ""
echo -e "${DIM}  Launching Vault Zero...${RST}"
echo ""
cd "$SCRIPT_DIR"
python3 main.py "$@"