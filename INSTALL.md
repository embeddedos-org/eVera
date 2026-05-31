# eVera — Installation Guide

eVera is fully self-contained. Every dependency — Python, Ollama, Playwright, system libraries, and Electron — is installed automatically by the setup scripts. No manual configuration is required to get started.

---

## Quick Start

### Linux / macOS — One Command

```bash
curl -fsSL https://raw.githubusercontent.com/embeddedos-org/eVera/main/install.sh | bash
```

This clones the repository, installs Python 3.12, creates a virtual environment, installs all Python packages, installs Ollama, pulls a default offline model, installs Playwright Chromium, and installs the Electron desktop dependencies.

### Windows — One Command (PowerShell)

```powershell
irm https://raw.githubusercontent.com/embeddedos-org/eVera/main/setup.ps1 | iex
```

### After Setup — Start eVera

```bash
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows

python main.py --mode server       # Start the web server
# Open http://localhost:8000
```

---

## Download Pre-Built Installers

Pre-built installers are published automatically on every tagged release via GitHub Actions CI.

| Platform | File | How to Install |
|---|---|---|
| **Windows** | `Vera-Setup-*.exe` | Run the installer — includes Python backend, no dependencies needed |
| **macOS** | `Vera-*.dmg` | Open DMG → drag Vera to Applications |
| **Linux** | `Vera-*.AppImage` | `chmod +x Vera-*.AppImage && ./Vera-*.AppImage` |
| **Linux (deb)** | `Vera-*.deb` | `sudo dpkg -i Vera-*.deb` |
| **Android** | `Vera-*.apk` | Enable "Install from unknown sources" → tap APK |

Download from: [github.com/embeddedos-org/eVera/releases](https://github.com/embeddedos-org/eVera/releases)

---

## Operating Modes

eVera operates in three distinct modes, selectable from the header dropdown.

| Mode | Internet | LLMs Available | Computer Control | LAN Access |
|---|---|---|---|---|
| **LOCAL** | Not required | Ollama, LM Studio, Jan, llama.cpp | Full | No |
| **LAN** | Not required | All offline + LAN-hosted servers | Full | Yes |
| **WWW** | Required | All 100+ models including cloud | Full | Yes |

To set the default mode, edit `.env`:

```env
VERA_SERVER_DEFAULT_MODE=local    # or lan, www
```

---

## Offline LLMs

eVera works completely offline using Ollama. After setup, pull any model:

```bash
# Recommended starter models
ollama pull qwen3:8b          # 5 GB — best general-purpose
ollama pull llama3.2:3b       # 2 GB — fast, low RAM
ollama pull deepseek-r1:7b    # 5 GB — best reasoning
ollama pull qwen2.5-coder:7b  # 5 GB — best code

# Tiny models for very low RAM systems (< 4 GB)
ollama pull qwen3:0.6b        # 400 MB
ollama pull llama3.2:1b       # 700 MB
ollama pull moondream:1.8b    # 1.5 GB — vision

# Large models for powerful hardware
ollama pull qwen3:32b         # 20 GB
ollama pull llama3.3:70b      # 40 GB
```

### LM Studio

1. Download and install [LM Studio](https://lmstudio.ai)
2. Load any model in LM Studio
3. Start the local server (default port 1234)
4. In eVera, select any `lmstudio/` model from the model picker

Configure the URL in `.env` if you use a non-default port:

```env
VERA_LLM_LM_STUDIO_URL=http://localhost:1234
```

### Jan AI

1. Download and install [Jan](https://jan.ai)
2. Load any model in Jan
3. Enable the API server (default port 1337)
4. In eVera, select any `jan/` model from the model picker

```env
VERA_LLM_JAN_URL=http://localhost:1337
```

### llama.cpp Server

1. Build or download [llama.cpp](https://github.com/ggerganov/llama.cpp)
2. Start the server: `./llama-server -m model.gguf --port 8080`
3. In eVera, select any `llamacpp/` model from the model picker

```env
VERA_LLM_LLAMACPP_URL=http://localhost:8080
```

---

## Manual Installation (Step by Step)

If you prefer to install manually or the one-liner fails:

### 1. Clone the Repository

```bash
git clone https://github.com/embeddedos-org/eVera.git
cd eVera
```

### 2. Python Environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows

pip install --upgrade pip
pip install -r requirements.txt
```

### 3. System Packages (Linux)

```bash
sudo apt install -y \
  tesseract-ocr ffmpeg libportaudio2 \
  xdotool wmctrl scrot xclip
```

### 4. Playwright (Browser Automation)

```bash
python -m playwright install chromium --with-deps
```

### 5. Ollama (Offline LLMs)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b
```

### 6. Configuration

```bash
cp .env.example .env
# Edit .env to add optional cloud API keys
# All fields are optional — Ollama works without any keys
```

### 7. Start eVera

```bash
python main.py --mode server
# Open http://localhost:8000
```

---

## Desktop App (Electron)

The Electron desktop app wraps the Python backend into a native window with system tray, global shortcut, and auto-start support.

### Run from Source

```bash
# First, ensure the Python backend is running or let Electron start it
cd electron
npm install
npm start
```

### Build Installer

```bash
# Linux
bash setup.sh --build-desktop
# Produces: electron/dist/Vera-*.AppImage and Vera-*.deb

# Windows (PowerShell)
.\scripts\build_windows.ps1
# Produces: electron\dist\Vera-Setup-*.exe

# macOS
cd electron && npm run build:mac
# Produces: electron/dist/Vera-*.dmg
```

---

## LAN / Network Mode

To allow other computers on your network to access eVera:

```bash
python main.py --mode server --host 0.0.0.0
```

Then open `http://<your-ip>:8000` from any device on the same network.

To require authentication for LAN connections:

```env
VERA_SERVER_ZONE_LAN_AUTH_REQUIRED=true
VERA_SERVER_API_KEY=your-secret-key
```

---

## Environment Variables Reference

All settings use the `VERA_` prefix and are loaded from `.env`. No setting is mandatory — eVera runs fully offline with zero configuration.

| Variable | Default | Description |
|---|---|---|
| `VERA_LLM_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `VERA_LLM_LM_STUDIO_URL` | `http://localhost:1234` | LM Studio server URL |
| `VERA_LLM_JAN_URL` | `http://localhost:1337` | Jan AI server URL |
| `VERA_LLM_LLAMACPP_URL` | `http://localhost:8080` | llama.cpp server URL |
| `VERA_LLM_OPENAI_API_KEY` | _(empty)_ | OpenAI API key (optional) |
| `VERA_LLM_ANTHROPIC_API_KEY` | _(empty)_ | Anthropic API key (optional) |
| `VERA_LLM_GEMINI_API_KEY` | _(empty)_ | Google Gemini API key (optional) |
| `VERA_SERVER_HOST` | `0.0.0.0` | Server bind host |
| `VERA_SERVER_PORT` | `8000` | Server port |
| `VERA_SERVER_API_KEY` | _(empty)_ | API key for LAN/WWW auth |

---

## Troubleshooting

**eVera starts but shows no models:** Run `ollama list` to confirm models are installed. If empty, run `ollama pull qwen3:8b`.

**LM Studio / Jan not detected:** Ensure the local server is running and the port matches `VERA_LLM_LM_STUDIO_URL` / `VERA_LLM_JAN_URL` in `.env`.

**Playwright install fails:** Run `python -m playwright install chromium --with-deps` manually. Browser automation is optional — all other features work without it.

**Port 8000 already in use:** Change the port with `python main.py --mode server --port 8001`.

**Windows: Python not found:** Install Python 3.12 from [python.org](https://www.python.org/downloads/) and check "Add Python to PATH" during installation.

---

## Updating eVera

```bash
git pull origin main
pip install -r requirements.txt   # pick up new Python deps
```

Or re-run the one-liner installer — it updates an existing install automatically.
