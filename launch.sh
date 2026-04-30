#!/usr/bin/env bash
# launch.sh — Vault Zero PyQt6 launcher (Bash layer)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN="\033[0;32m"; AMBER="\033[0;33m"; RED="\033[0;31m"; DIM="\033[2m"; RST="\033[0m"
ok()  { echo -e "${GREEN}[OK]${RST}  $*"; }
warn(){ echo -e "${AMBER}[WARN]${RST} $*"; }
err() { echo -e "${RED}[ERR]${RST}  $*"; exit 1; }
echo -e "${GREEN}╔══════════════════════════════════════╗${RST}"
echo -e "${GREEN}║    VAULT ZERO — PyQt6 LAUNCHER       ║${RST}"
echo -e "${GREEN}╚══════════════════════════════════════╝${RST}"
command -v python3 &>/dev/null || err "python3 not found"
ok "Python: $(python3 --version)"
python3 -c "from PyQt6.QtWidgets import QApplication" 2>/dev/null || {
    warn "PyQt6 not found — installing..."
    pip install PyQt6 --break-system-packages -q
}
ok "PyQt6 ready"
if command -v lua &>/dev/null || command -v lua5.4 &>/dev/null || command -v lua5.3 &>/dev/null; then
    ok "Lua found — event scripting active"
else
    warn "Lua not found — Python fallback will be used for event scripting"
fi
echo ""
echo -e "${DIM}  Launching Vault Zero...${RST}"
cd "$SCRIPT_DIR"
python3 main.py "$@"
