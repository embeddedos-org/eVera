# eVera — Setup Guide

> **eVera** is a Jarvis-like AI copilot with 30+ models, personal knowledge base, Chrome extension, and web automation. It runs as a **web app** (recommended) or a **desktop installer**.

---

## Quick Start — Which Mode Should I Use?

| Mode | Best For | Requirements |
|------|----------|-------------|
| **🌐 Web Mode** | Development, corporate machines, daily use | Python 3.11+ |
| **🖥️ Desktop Installer** | Personal machines, sharing with others | Windows 10/11 (no Python needed) |
| **🔌 Chrome Extension** | AI actions on any webpage | Either mode running + Chrome |

---

## 🌐 Option A: Web Mode (Recommended)

The web app runs eVera as a local server and opens the UI in your browser. This is the most reliable method and works on all machines including corporate/managed devices.

### Prerequisites
- Python 3.11 or 3.12
- Git

### Step 1: Clone & Setup

```powershell
git clone https://github.com/srpatcha/eVera.git
cd eVera
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

The setup script automatically:
- ✅ Installs all Python packages (FastAPI, litellm, FAISS, Playwright, etc.)
- ✅ Installs Playwright Chromium browser
- ✅ Creates `.env` from `.env.example`
- ✅ Creates data directories
- ✅ Installs Node.js if needed (for Electron dev mode)

### Step 2: Add API Keys

Edit `.env` and add at least one LLM provider key:

```ini
# Pick one or more (Ollama works without keys if installed locally)
VERA_LLM_OPENAI_API_KEY=sk-...
VERA_LLM_ANTHROPIC_API_KEY=sk-ant-...
VERA_LLM_GEMINI_API_KEY=AI...
VERA_LLM_GROQ_API_KEY=gsk_...
VERA_LLM_DEEPSEEK_API_KEY=sk-...
```

> **No API keys?** eVera falls back to local Ollama models. Install Ollama from https://ollama.ai and run `ollama pull llama3.2`.

### Step 3: Start

```powershell
cd eVera
python main.py --mode server
```

### Step 4: Open

Open **http://localhost:8000** in Chrome (or Edge).

You'll see:
- 💬 Chat interface with WebSocket real-time messaging
- 🤖 3D animated avatar
- 🎙️ Voice input (click mic button, allow microphone)
- 📊 Agent panel with 20 specialized agents
- 🔧 Model selector dropdown (top-right)

### Other Run Modes

```powershell
# Text-only CLI (no browser needed)
python main.py --mode text

# Voice CLI (mic + speaker, no browser)
python main.py --mode cli

# Voice + Server simultaneously
python main.py --mode both

# All modes at once
python main.py --mode all
```

---

## 🖥️ Option B: Desktop Installer (Personal Machines)

The desktop installer packages everything into a single `.exe` — no Python, Node.js, or dependencies needed on the target machine.

### Download

Download **Vera Setup 0.9.0.exe** (304 MB) from:
👉 https://github.com/srpatcha/eVera/releases/tag/v0.9.0

### Install

1. Double-click `Vera Setup 0.9.0.exe`
2. Choose installation directory
3. Click Install
4. Launch Vera from Start Menu

### What You Get

- **System tray icon** — Vera runs in background, click tray to show/hide
- **Global shortcut** — `Ctrl+Shift+V` to toggle Vera from anywhere
- **Auto-start** — Option to launch on Windows boot
- **Splash screen** — Shows loading progress while backend starts
- **Self-contained** — Backend (vera-server.exe) auto-starts with the app

### First Run

On first launch, you'll need to add API keys:
1. Find the installation directory (default: `%LOCALAPPDATA%\Programs\Vera`)
2. Navigate to `resources\backend\`
3. Edit `.env` file and add your API keys
4. Restart Vera

### ⚠️ Known Limitation: Corporate/Managed Machines

The desktop installer may **not work on corporate-managed Windows machines** (e.g., Meta, Google, Microsoft corp devices). Corporate endpoint security software blocks localhost HTTP connections from unsigned/PyInstaller executables.

**Workaround:** Use **Web Mode** (Option A) instead.

---

## 🔌 Chrome Extension Setup

The Chrome extension works with **either** web mode or desktop mode — it connects to the eVera backend at `localhost:8000`.

### Install

1. Open Chrome → navigate to `chrome://extensions`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked**
4. Select the `extension/` folder from the eVera repo:
   ```
   C:\Users\<you>\eVera\extension\
   ```
5. The eVera icon (blue circle with V) appears in the toolbar

### Usage

| Feature | How |
|---------|-----|
| **Quick actions** | Select text on any page → floating toolbar appears |
| **Context menu** | Right-click selected text → Ask eVera / Summarize / Translate / Explain / Fix Grammar |
| **Chat sidebar** | Click eVera icon → "Open Chat Panel" |
| **Settings** | Click eVera icon → "Settings" → change server URL, default model |

### Requirements

- eVera backend must be running (`python main.py --mode server` or desktop app)
- Chrome or Chromium-based browser (Edge, Brave, etc.)

---

## 🤖 Adding LLM Providers

eVera supports 9 providers and 30+ models. Add keys to `.env` for any you want:

| Provider | Env Variable | Free Tier? | Best For |
|----------|-------------|-----------|----------|
| **Ollama** | (no key needed) | ✅ Free (local) | Offline use |
| **OpenAI** | `VERA_LLM_OPENAI_API_KEY` | ❌ Paid | General, vision |
| **Anthropic** | `VERA_LLM_ANTHROPIC_API_KEY` | ❌ Paid | Creative, analysis |
| **Google Gemini** | `VERA_LLM_GEMINI_API_KEY` | ✅ Free tier | General, long context |
| **Groq** | `VERA_LLM_GROQ_API_KEY` | ✅ Free tier | Ultra-fast inference |
| **DeepSeek** | `VERA_LLM_DEEPSEEK_API_KEY` | ✅ Very cheap | Code generation |
| **Mistral** | `VERA_LLM_MISTRAL_API_KEY` | ✅ Free tier | European AI |
| **Together AI** | `VERA_LLM_TOGETHER_API_KEY` | ✅ Free credits | Open-source models |
| **Perplexity** | `VERA_LLM_PERPLEXITY_API_KEY` | ❌ Paid | Web search |

### Auto-Routing

When multiple providers are configured, eVera auto-picks the best model:
- **Code tasks** → DeepSeek
- **Creative writing** → Claude (Anthropic)
- **Fast responses** → Groq
- **Web search** → Perplexity
- **Vision/images** → GPT-4o (OpenAI)
- **Long documents** → Gemini

Or use the **model selector dropdown** in the header to manually choose.

---

## 📚 Knowledge Base (RAG)

Upload your documents and ask questions about them.

### Upload via API

```powershell
# Upload a PDF
curl -X POST http://localhost:8000/knowledge/upload -F "file=@my_document.pdf"

# Upload a Word doc
curl -X POST http://localhost:8000/knowledge/upload -F "file=@report.docx"

# Ask a question
curl -X POST http://localhost:8000/knowledge/query `
  -H "Content-Type: application/json" `
  -d '{"query": "What are the key findings?"}'
```

### Supported Formats
- PDF (`.pdf`)
- Word (`.docx`)
- Text (`.txt`, `.md`, `.markdown`)
- CSV (`.csv`)
- Max file size: 50 MB

---

## 🕷️ Web Automation

Tell eVera to automate browser tasks in natural language:

```powershell
# Plan steps (preview)
curl -X POST http://localhost:8000/automation/plan `
  -H "Content-Type: application/json" `
  -d '{"task": "Search Google for Python tutorials"}'

# Plan and execute
curl -X POST http://localhost:8000/automation/execute `
  -H "Content-Type: application/json" `
  -d '{"task": "Go to GitHub and search for eVera"}'

# Scrape structured data
curl -X POST http://localhost:8000/automation/scrape `
  -H "Content-Type: application/json" `
  -d '{"url": "https://news.ycombinator.com", "data_schema": {"title": "Article title", "url": "Link"}, "max_pages": 2}'
```

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| "No models available" | Add at least one API key to `.env`, or install Ollama |
| Voice not working | Use Chrome (not Firefox). Click mic button and allow microphone permission |
| Black screen in desktop app | Corporate security blocking — use web mode instead |
| "Backend failed to start" | Kill stale processes: `Get-Process python \| Stop-Process -Force`, then restart |
| Extension not connecting | Ensure backend is running on `localhost:8000` before using extension |
| Port 8000 in use | `python main.py --mode server --port 8001` (update extension settings to match) |

---

## 📦 Building From Source

### Build the desktop installer yourself:

```powershell
cd eVera
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -BuildExe
```

Or step by step:

```powershell
# 1. Build Python backend
python -m PyInstaller vera.spec --clean --noconfirm

# 2. Build Electron installer
cd electron
npm install
npx electron-builder --win
# Output: electron/dist/Vera Setup 0.9.0.exe
```

---

## 🔗 Links

- **GitHub**: https://github.com/srpatcha/eVera
- **Releases**: https://github.com/srpatcha/eVera/releases
- **API Docs**: http://localhost:8000/docs (when server is running)
