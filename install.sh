#!/usr/bin/env bash
# =============================================================================
#  eVera — Remote One-Liner Installer
#  Usage:  curl -fsSL https://raw.githubusercontent.com/embeddedos-org/eVera/main/install.sh | bash
#          curl -fsSL .../install.sh | bash -s -- --minimal
#          curl -fsSL .../install.sh | bash -s -- --build-desktop
# =============================================================================
set -euo pipefail

REPO="https://github.com/embeddedos-org/eVera.git"
INSTALL_DIR="${EVERA_DIR:-$HOME/eVera}"
BRANCH="${EVERA_BRANCH:-main}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}  ✔ $*${RESET}"; }
warn() { echo -e "${YELLOW}  ⚠ $*${RESET}"; }
err()  { echo -e "${RED}  ✖ $*${RESET}"; exit 1; }

echo -e "${CYAN}${BOLD}"
cat << 'BANNER'
  ╔══════════════════════════════════════════════╗
  ║          eVera — AI Personal Agent           ║
  ║          Remote Installer  v2.2              ║
  ╚══════════════════════════════════════════════╝
BANNER
echo -e "${RESET}"

# Check git
command -v git &>/dev/null || err "git is required. Install it with: sudo apt install git"

# Clone or update
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "  Updating existing install at $INSTALL_DIR..."
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH" 2>/dev/null || \
    git -C "$INSTALL_DIR" fetch origin && git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
  ok "Repository updated"
else
  echo "  Cloning eVera to $INSTALL_DIR..."
  git clone --depth 1 --branch "$BRANCH" "$REPO" "$INSTALL_DIR"
  ok "Repository cloned"
fi

# Run the full setup script
bash "$INSTALL_DIR/setup.sh" "$@"
