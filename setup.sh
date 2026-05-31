#!/usr/bin/env bash
# =============================================================================
#  eVera — One-Command Setup Script  (Linux & macOS)
#  Usage:  bash setup.sh
#          bash setup.sh --minimal        # Skip browser/trading deps
#          bash setup.sh --build-desktop  # Also build the Electron installer
#          bash setup.sh --no-ollama      # Skip Ollama install
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MINIMAL=false
BUILD_DESKTOP=false
SKIP_OLLAMA=false
PYTHON=""
NODE_MIN="18"

# ── Parse flags ──────────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --minimal)       MINIMAL=true ;;
    --build-desktop) BUILD_DESKTOP=true ;;
    --no-ollama)     SKIP_OLLAMA=true ;;
  esac
done

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}  ✔ $*${RESET}"; }
warn() { echo -e "${YELLOW}  ⚠ $*${RESET}"; }
err()  { echo -e "${RED}  ✖ $*${RESET}"; exit 1; }
step() { echo -e "\n${CYAN}${BOLD}[$1] $2${RESET}"; }

echo -e "${CYAN}${BOLD}"
cat << 'BANNER'
  ╔══════════════════════════════════════════════╗
  ║          eVera — AI Personal Agent           ║
  ║         One-Command Setup  (Linux/Mac)       ║
  ╚══════════════════════════════════════════════╝
BANNER
echo -e "${RESET}"

OS="$(uname -s)"
ARCH="$(uname -m)"
echo -e "  Platform: ${BOLD}${OS} ${ARCH}${RESET}"

# ── Step 1: Python 3.11+ ─────────────────────────────────────────────────────
step "1/8" "Checking Python 3.11+"
for py in python3.12 python3.11 python3 python; do
  if command -v "$py" &>/dev/null; then
    VER=$("$py" -c "import sys; print(sys.version_info[:2])" 2>/dev/null || echo "(0, 0)")
    if "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>/dev/null; then
      PYTHON="$py"
      ok "Found $py ($VER)"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  warn "Python 3.11+ not found — installing..."
  if [ "$OS" = "Linux" ]; then
    if command -v apt-get &>/dev/null; then
      sudo apt-get update -qq
      sudo apt-get install -y software-properties-common
      sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
      sudo apt-get update -qq
      sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip
      PYTHON=python3.12
    elif command -v dnf &>/dev/null; then
      sudo dnf install -y python3.12 python3.12-devel
      PYTHON=python3.12
    elif command -v pacman &>/dev/null; then
      sudo pacman -S --noconfirm python
      PYTHON=python3
    else
      err "Cannot auto-install Python. Please install Python 3.11+ manually."
    fi
  elif [ "$OS" = "Darwin" ]; then
    if ! command -v brew &>/dev/null; then
      warn "Installing Homebrew first..."
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python@3.12
    PYTHON=python3.12
  fi
  ok "Python installed: $PYTHON"
fi

# ── Step 2: Virtual environment ───────────────────────────────────────────────
step "2/8" "Setting up Python virtual environment"
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON" -m venv "$VENV_DIR"
  ok "Created .venv"
else
  ok ".venv already exists"
fi
# Activate venv
source "$VENV_DIR/bin/activate"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# ── Step 3: Python dependencies ───────────────────────────────────────────────
step "3/8" "Installing Python dependencies"
"$PIP" install --upgrade pip wheel setuptools -q
if [ "$MINIMAL" = true ]; then
  # Install core only — skip heavy ML/audio/trading deps
  "$PIP" install \
    fastapi uvicorn pydantic pydantic-settings python-dotenv python-multipart websockets \
    litellm langgraph langchain-core \
    httpx duckduckgo-search beautifulsoup4 \
    pyautogui psutil pyperclip \
    Pillow PyPDF2 python-docx chardet \
    faiss-cpu sentence-transformers \
    cryptography -q
  ok "Minimal Python deps installed"
else
  "$PIP" install -r "$SCRIPT_DIR/requirements.txt" -q
  ok "All Python deps installed"
fi

# ── Step 4: System packages (tesseract, ffmpeg, etc.) ─────────────────────────
step "4/8" "Installing system packages"
if [ "$OS" = "Linux" ]; then
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y \
      tesseract-ocr tesseract-ocr-eng \
      ffmpeg \
      libportaudio2 portaudio19-dev \
      xdotool wmctrl \
      libnotify-bin \
      scrot \
      xclip xsel \
      libnss3 libatk-bridge2.0-0 libgtk-3-0 libgbm1 \
      -qq 2>/dev/null || warn "Some system packages failed (non-fatal)"
    ok "System packages installed"
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y tesseract ffmpeg portaudio-devel xdotool wmctrl scrot xclip 2>/dev/null || true
    ok "System packages installed (dnf)"
  elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm tesseract ffmpeg portaudio xdotool wmctrl scrot xclip 2>/dev/null || true
    ok "System packages installed (pacman)"
  fi
elif [ "$OS" = "Darwin" ]; then
  if command -v brew &>/dev/null; then
    brew install tesseract ffmpeg portaudio 2>/dev/null || true
    ok "System packages installed (brew)"
  fi
fi

# ── Step 5: Playwright browsers ───────────────────────────────────────────────
if [ "$MINIMAL" = false ]; then
  step "5/8" "Installing Playwright Chromium (browser automation)"
  "$PYTHON" -m playwright install chromium --with-deps 2>/dev/null || \
    warn "Playwright install failed — browser agent will be limited"
  ok "Playwright ready"
else
  step "5/8" "Skipping Playwright (--minimal mode)"
fi

# ── Step 6: Ollama (offline LLMs) ─────────────────────────────────────────────
step "6/8" "Setting up Ollama (offline LLMs)"
if [ "$SKIP_OLLAMA" = true ]; then
  warn "Skipping Ollama (--no-ollama flag)"
elif command -v ollama &>/dev/null; then
  OLLAMA_VER=$(ollama --version 2>/dev/null || echo "unknown")
  ok "Ollama already installed: $OLLAMA_VER"
else
  warn "Ollama not found — installing..."
  if [ "$OS" = "Linux" ] || [ "$OS" = "Darwin" ]; then
    curl -fsSL https://ollama.com/install.sh | sh
    ok "Ollama installed"
  else
    warn "Please install Ollama manually from https://ollama.com/download"
  fi
fi

# Pull a small default model if Ollama is available and no models exist
if command -v ollama &>/dev/null && [ "$SKIP_OLLAMA" = false ]; then
  MODEL_COUNT=$(ollama list 2>/dev/null | tail -n +2 | wc -l || echo "0")
  if [ "$MODEL_COUNT" -eq 0 ]; then
    echo -e "  ${YELLOW}Pulling default offline model: qwen3:0.6b (400 MB)...${RESET}"
    ollama pull qwen3:0.6b 2>/dev/null || warn "Could not pull default model (run 'ollama pull qwen3:0.6b' manually)"
    ok "Default model ready"
  else
    ok "Ollama models already present ($MODEL_COUNT models)"
  fi
fi

# ── Step 7: Node.js + Electron deps ───────────────────────────────────────────
step "7/8" "Checking Node.js for Electron desktop"
NODE_OK=false
if command -v node &>/dev/null; then
  NODE_VER=$(node --version | sed 's/v//')
  NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
  if [ "$NODE_MAJOR" -ge "$NODE_MIN" ]; then
    ok "Node.js v$NODE_VER"
    NODE_OK=true
  else
    warn "Node.js v$NODE_VER found but v$NODE_MIN+ required"
  fi
fi

if [ "$NODE_OK" = false ]; then
  warn "Installing Node.js 20..."
  if [ "$OS" = "Linux" ]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - 2>/dev/null
    sudo apt-get install -y nodejs 2>/dev/null || \
      (sudo dnf install -y nodejs 2>/dev/null || \
       sudo pacman -S --noconfirm nodejs npm 2>/dev/null) || \
      warn "Could not auto-install Node.js — install from https://nodejs.org"
  elif [ "$OS" = "Darwin" ]; then
    brew install node@20 || warn "Could not install Node.js via brew"
  fi
  command -v node &>/dev/null && ok "Node.js installed: $(node --version)" || warn "Node.js not available — desktop build will be skipped"
fi

# Install Electron npm deps
ELECTRON_DIR="$SCRIPT_DIR/electron"
if [ -f "$ELECTRON_DIR/package.json" ] && command -v npm &>/dev/null; then
  echo "  Installing Electron npm packages..."
  (cd "$ELECTRON_DIR" && npm install --silent 2>/dev/null) && ok "Electron deps installed" || warn "npm install failed in electron/"
fi

# ── Step 8: Data directories + config ─────────────────────────────────────────
step "8/8" "Creating data directories and config"
for dir in data data/faiss_index data/media data/diagrams data/knowledge data/job_profile data/browser_sessions; do
  mkdir -p "$SCRIPT_DIR/$dir"
done
ok "Data directories ready"

# Create .env if missing
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
if [ ! -f "$ENV_FILE" ] && [ -f "$ENV_EXAMPLE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  ok "Created .env from .env.example"
  warn "Edit .env to add API keys (optional — Ollama works without any keys)"
elif [ -f "$ENV_FILE" ]; then
  ok ".env already exists"
fi

# ── Optional: Build Electron desktop installer ────────────────────────────────
if [ "$BUILD_DESKTOP" = true ]; then
  echo -e "\n${CYAN}${BOLD}[BONUS] Building Electron desktop installer...${RESET}"
  if ! command -v npm &>/dev/null; then
    warn "npm not found — skipping desktop build"
  else
    echo "  Building Python backend with PyInstaller..."
    "$PYTHON" "$SCRIPT_DIR/build_backend.py" --clean
    echo "  Building Electron installer..."
    (cd "$ELECTRON_DIR" && npx electron-builder --linux --publish never)
    ok "Desktop installer built → electron/dist/"
  fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}"
cat << 'DONE'
  ╔══════════════════════════════════════════════╗
  ║          ✔  Setup Complete!                  ║
  ╚══════════════════════════════════════════════╝
DONE
echo -e "${RESET}"
echo -e "  ${BOLD}Start eVera:${RESET}"
echo -e "    source .venv/bin/activate"
echo -e "    python main.py --mode server"
echo -e "    Open: ${CYAN}http://localhost:8000${RESET}"
echo ""
echo -e "  ${BOLD}Or run the desktop app:${RESET}"
echo -e "    cd electron && npm start"
echo ""
echo -e "  ${BOLD}Build desktop installer:${RESET}"
echo -e "    bash setup.sh --build-desktop"
echo ""
echo -e "  ${BOLD}Offline LLMs (Ollama):${RESET}"
echo -e "    ollama pull llama3.2:3b     # 2 GB — fast"
echo -e "    ollama pull qwen3:8b        # 5 GB — recommended"
echo -e "    ollama pull llama3.3:70b    # 40 GB — best quality"
echo ""
