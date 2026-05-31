# eVera — Your Personal AI Agent

[![Version](https://img.shields.io/badge/version-2.2.0-blue?style=for-the-badge)](https://github.com/embeddedos-org/eVera/releases/latest)
[![Build & Release](https://img.shields.io/github/actions/workflow/status/embeddedos-org/eVera/build.yml?style=for-the-badge&label=Build%20%26%20Release)](https://github.com/embeddedos-org/eVera/actions/workflows/build.yml)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Android%20%7C%20iOS%20%7C%20Web-success?style=for-the-badge)](#download)
[![Offline](https://img.shields.io/badge/works-100%25%20offline-success?style=for-the-badge)](#offline-llms)
[![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)](LICENSE)

eVera is a fully autonomous personal AI agent that works **completely offline**, on your **local network**, or with the **full internet**. It controls your computer, runs 50+ local AI models, and is available on every platform — Web, Desktop, and Mobile.

---

## Download

Pre-built installers are published automatically on every tagged release via GitHub Actions CI. No Python, Node.js, or any other dependency needs to be installed manually.

| Platform | Download | Install |
|---|---|---|
| **Windows** | [`Vera-Setup-*.exe`](https://github.com/embeddedos-org/eVera/releases/latest) | Run the installer — everything is bundled |
| **macOS** | [`Vera-*.dmg`](https://github.com/embeddedos-org/eVera/releases/latest) | Open DMG → drag Vera to Applications |
| **Linux (AppImage)** | [`Vera-*.AppImage`](https://github.com/embeddedos-org/eVera/releases/latest) | `chmod +x Vera-*.AppImage && ./Vera-*.AppImage` |
| **Linux (deb)** | [`Vera-*.deb`](https://github.com/embeddedos-org/eVera/releases/latest) | `sudo dpkg -i Vera-*.deb` |
| **Android** | [`Vera-*.apk`](https://github.com/embeddedos-org/eVera/releases/latest) | Enable "Install from unknown sources" → tap APK |
| **Android Auto** | [`Vera-Auto-*.apk`](https://github.com/embeddedos-org/eVera/releases/latest) | Install on phone → connect to car |
| **Wear OS** | [`Vera-Wear-*.apk`](https://github.com/embeddedos-org/eVera/releases/latest) | Sideload or install via Play Store |
| **iOS** | [`Vera.xcarchive.zip`](https://github.com/embeddedos-org/eVera/releases/latest) | Open in Xcode → distribute to device |
| **Web (PWA)** | [Open in browser](http://localhost:8000) | Install from browser address bar (Chrome/Edge/Safari) |

> All binaries are built and published automatically by GitHub Actions on every `v*` tag push.
> See [Actions](https://github.com/embeddedos-org/eVera/actions) for live build status.

---

## One-Command Install (from source)

### Linux / macOS

```bash
curl -fsSL https://raw.githubusercontent.com/embeddedos-org/eVera/main/install.sh | bash
```

This single command clones the repo, installs Python 3.12, creates a virtual environment, installs all Python packages, installs system libraries (tesseract, ffmpeg, portaudio, xdotool), installs Playwright Chromium, installs Ollama, pulls a default offline model, and installs Electron dependencies. Nothing else is needed.

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/embeddedos-org/eVera/main/setup.ps1 | iex
```

### After Setup

```bash
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate       # Windows

python main.py --mode server
# Open http://localhost:8000
```

For full manual installation steps, see [INSTALL.md](INSTALL.md).

---

## Operating Modes

eVera works in three distinct modes, selectable from the header dropdown at any time.

| Mode | Internet Required | LLMs Available | Computer Control | LAN Access |
|---|---|---|---|---|
| **LOCAL** | No | Ollama, LM Studio, Jan, llama.cpp | Full | No |
| **LAN** | No | All offline + LAN-hosted servers | Full | Yes |
| **WWW** | Yes | All 100+ models including cloud | Full | Yes |

Switch modes without restarting — the agent adapts its tool set and model selection automatically.

---

## Offline LLMs

eVera works completely without internet using Ollama. Pull any model after setup:

```bash
# Recommended — best balance of quality and speed
ollama pull qwen3:8b          # 5 GB
ollama pull llama3.2:3b       # 2 GB — fastest
ollama pull deepseek-r1:7b    # 5 GB — best reasoning
ollama pull qwen2.5-coder:7b  # 5 GB — best code

# Ultra-low RAM (under 4 GB)
ollama pull qwen3:0.6b        # 400 MB
ollama pull llama3.2:1b       # 700 MB

# High-end hardware
ollama pull qwen3:32b         # 20 GB
ollama pull llama3.3:70b      # 40 GB
```

eVera also auto-detects and integrates with:

| Tool | Default Port | Notes |
|---|---|---|
| **LM Studio** | 1234 | Load any GGUF model, start local server |
| **Jan AI** | 1337 | Load any model, enable API server |
| **llama.cpp** | 8080 | `./llama-server -m model.gguf --port 8080` |

All three appear in the model selector under green `🟢` groups, sorted before cloud providers.

---

## Features

### Computer Control (LOCAL mode)
eVera can control any function of the running computer system:

- **Screen**: take screenshots, read screen content, find UI elements
- **Mouse & Keyboard**: click, type, drag, scroll — full desktop automation
- **Files**: read, write, move, search, compress, extract
- **Applications**: launch, close, interact with any app
- **System**: manage processes, services, network interfaces, power state
- **Browser**: full web automation via Playwright (Chromium)
- **Terminal**: execute shell commands, run scripts, manage environments

### 3D Avatar
A real-time 3D holographic avatar (Three.js WebGL) is displayed alongside the chat panel. The avatar:
- Animates through 8 expressions: idle, thinking, speaking, happy, excited, sad, error, listening
- Responds to voice amplitude in real time (mouth movement)
- Falls back to an animated 2D canvas face if WebGL is unavailable
- Is visible on desktop, web, and mobile (bottom tab on mobile)

### Voice — Multi-Accent TTS
All browser-native TTS voices are available in the voice selector, grouped by language and accent. Local (offline) voices are marked with `●`, network voices with `○`. Selection is saved across sessions.

### 39+ Specialized Agents
eVera routes every request to the best-suited agent automatically:

| Category | Agents |
|---|---|
| Research | Web search, academic papers, news, Wikipedia |
| Code | Write, review, debug, execute, explain |
| Files | Read, write, convert, summarize, extract |
| System | Shell, process manager, service control |
| Browser | Navigate, scrape, fill forms, screenshot |
| Memory | Working memory, episodic memory, fact extraction |
| LAN | Network scanner, SSH, file shares, org data |
| Creative | Writing, brainstorming, translation, summarization |

### Memory System
- **Working memory**: current conversation context
- **Episodic memory**: past conversations, searchable
- **Fact memory**: extracted facts about the user and their environment, persisted across sessions

---

## Architecture

```
eVera/
├── main.py                  ← Entry point (server / desktop / cli modes)
├── config.py                ← All settings (Pydantic, .env-driven)
├── setup.sh                 ← One-command Linux/macOS installer
├── install.sh               ← curl-pipe remote installer
├── setup.ps1                ← One-command Windows installer
├── INSTALL.md               ← Full installation guide
├── vera/
│   ├── brain/               ← Agent orchestration, memory, planning
│   │   ├── agents/          ← 39+ specialized agents
│   │   ├── computer_use/    ← Desktop control (mouse, keyboard, screen)
│   │   ├── lan_agent.py     ← LAN network discovery and access
│   │   └── orchestrator.py  ← Multi-agent routing
│   ├── providers/
│   │   ├── models.py        ← 100+ model definitions across 12+ providers
│   │   └── manager.py       ← LiteLLM routing, health checks, streaming
│   ├── operating_mode.py    ← LOCAL / LAN / WWW mode enforcement
│   └── static/              ← Web UI (PWA)
│       ├── index.html
│       ├── app.js           ← Main UI logic, voice, mobile nav
│       ├── face.js          ← Three.js 3D avatar + 2D fallback
│       ├── style.css        ← Glassmorphism design system
│       ├── manifest.json    ← PWA manifest
│       └── sw.js            ← Service worker (offline cache)
├── electron/                ← Desktop app wrapper
│   ├── main.js              ← Electron main process
│   └── package.json         ← electron-builder config
├── mobile/                  ← React Native mobile app
│   ├── android/             ← Android (Phone + Auto + Wear)
│   └── ios/                 ← iOS
└── .github/workflows/
    └── build.yml            ← CI: builds all platforms on every v* tag
```

---

## CI / Build Pipeline

Every push to a `v*` tag triggers a full build across all platforms simultaneously:

| Job | Runner | Output |
|---|---|---|
| Pre-flight | ubuntu-latest | Lint (ruff), pytest, frontend validation |
| Desktop — Windows | windows-latest | `Vera-Setup-*.exe` (NSIS installer) |
| Desktop — macOS | macos-latest | `Vera-*.dmg` |
| Desktop — Linux | ubuntu-latest | `Vera-*.AppImage`, `Vera-*.deb` |
| Android | ubuntu-latest | `Vera-*.apk`, `Vera-Auto-*.apk`, `Vera-Wear-*.apk` |
| iOS | macos-latest | `Vera.xcarchive.zip` (unsigned, for distribution) |
| GitHub Release | ubuntu-latest | Creates release, attaches all artifacts |

The Python backend is bundled into a self-contained binary via PyInstaller before Electron packages it. Users need no Python, Node.js, or any runtime installed.

To trigger a release manually:

```bash
git tag v2.x.x
git push origin v2.x.x
```

---

## Configuration

All settings are in `.env` (copy from `.env.example`). No setting is required — eVera runs fully offline with zero configuration.

| Variable | Default | Description |
|---|---|---|
| `VERA_LLM_OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `VERA_LLM_LM_STUDIO_URL` | `http://localhost:1234` | LM Studio server |
| `VERA_LLM_JAN_URL` | `http://localhost:1337` | Jan AI server |
| `VERA_LLM_LLAMACPP_URL` | `http://localhost:8080` | llama.cpp server |
| `VERA_LLM_OPENAI_API_KEY` | _(empty)_ | OpenAI (optional) |
| `VERA_LLM_ANTHROPIC_API_KEY` | _(empty)_ | Anthropic (optional) |
| `VERA_LLM_GEMINI_API_KEY` | _(empty)_ | Google Gemini (optional) |
| `VERA_SERVER_PORT` | `8000` | Web server port |
| `VERA_SERVER_API_KEY` | _(empty)_ | Auth key for LAN/WWW mode |

---

## Development

```bash
git clone https://github.com/embeddedos-org/eVera.git
cd eVera
bash setup.sh
source .venv/bin/activate
python main.py --mode server
```

Run tests:

```bash
pytest tests/ -v
```

Build desktop app locally (Linux):

```bash
bash setup.sh --build-desktop
# Output: electron/dist/Vera-*.AppImage
```

---

## License

MIT License. See [LICENSE](LICENSE).

---

*eVera is built by [embeddedOS](https://github.com/embeddedos-org) — open, local-first, and fully under your control.*
