<p align="center">
  <pre align="center">
 __     __
 \ \   / /___   ___  __ _
  \ \ / / _ \ / __|/ _` |
   \ V / (_) | (__| (_| |
    \_/ \___/ \___|\__,_|
  </pre>
  <b>Voice-first multi-agent AI assistant that controls everything</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/v0.5.1-release-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Agents-12+-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Tools-115+-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/Electron-28+-9feaf9?style=for-the-badge&logo=electron" />
  <img src="https://img.shields.io/badge/React_Native-0.73-61dafb?style=for-the-badge&logo=react" />
  <img src="https://img.shields.io/badge/License-MIT-red?style=for-the-badge" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-✅-0078D6?style=flat-square&logo=windows" />
  <img src="https://img.shields.io/badge/macOS-✅-000000?style=flat-square&logo=apple" />
  <img src="https://img.shields.io/badge/Linux-✅-FCC624?style=flat-square&logo=linux&logoColor=black" />
  <img src="https://img.shields.io/badge/Android-✅-3DDC84?style=flat-square&logo=android&logoColor=white" />
  <img src="https://img.shields.io/badge/iOS-✅-000000?style=flat-square&logo=ios" />
  <img src="https://img.shields.io/badge/Security-Hardened-brightgreen?style=flat-square&logo=shield" />
  <img src="https://img.shields.io/badge/CI-Passing-brightgreen?style=flat-square&logo=github-actions" />
</p>

---

## 📥 Quick Install

### Desktop App (Recommended — one-click, no Python needed)

| Platform | Download | Install |
|----------|----------|---------|
| **Windows** | [Voca-Setup.exe](https://github.com/patchava-sr/eVoca/releases/latest) | Run the installer |
| **macOS** | [Voca.dmg](https://github.com/patchava-sr/eVoca/releases/latest) | Open DMG → drag to Applications |
| **Linux** | [Voca.AppImage](https://github.com/patchava-sr/eVoca/releases/latest) | `chmod +x Voca-*.AppImage && ./Voca-*.AppImage` |

### From Source (Developer)

```bash
git clone https://github.com/patchava-sr/eVoca.git && cd eVoca
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # Add your API keys
python main.py --mode server                         # Open http://localhost:8000
```

---

## ✨ Features

### 🎙️ Voice Control — 3 Modes
Always-on listening, wake word detection, or push-to-talk. Supports 19 languages with auto spell-correction.

### 🤖 10+ Specialized AI Agents

| Agent | Tools | What It Does |
|-------|-------|-------------|
| 💬 Companion | 4 | Chat, jokes, mood check, activity suggestions |
| 💻 Operator | 20 | Apps, scripts, files, **mouse, keyboard, windows, processes, system info** |
| 🌐 Browser | 11 | Navigate, login, fill forms, post on social media |
| 🔍 Researcher | 4 | Web search, summarize URLs, papers, fact-check |
| ✍️ Writer | 4 | Draft, edit, format, translate |
| 📅 Life Manager | 5 | Calendar, reminders, todos, email |
| 🏠 Home Controller | 6 | Lights, thermostat, locks, security, media |
| 📈 Income | 14 | Real-time prices, paper trading, Alpaca, IBKR |
| 💻 Coder | 5 | Read/write/edit files, search code, VS Code |
| 📦 Git | 9 | Status, diff, commit, push, AI code review |

### 💻 Full System Control (NEW in v0.5.0)
- 🖱️ **Mouse** — click, move, drag, scroll at any screen coordinates
- ⌨️ **Keyboard** — press any hotkey (Ctrl+C, Alt+Tab, Win+D)
- 🪟 **Windows** — list, focus, minimize, maximize, close windows
- ⚙️ **Processes** — list, inspect, kill running processes
- 📊 **System Info** — CPU, memory, disk, battery, OS details
- 🔧 **Services** — list, start, stop, restart system services
- 🌐 **Network** — IP info, connections, ping test
- 📋 **Clipboard** — read/write system clipboard
- 🔔 **Notifications** — send OS-level desktop notifications

### 🎭 Animated Face
8 expressions with blinking, bobbing, and mouth sync on a glassmorphism UI.

### 👁️ Screen Vision
Captures your screen → GPT-4o / Gemini vision analysis. Ask "what's on my screen?"

### 📊 Real Stock Trading
Paper trading, Alpaca, Interactive Brokers, TradingView alerts webhook.

### 🧠 4-Layer Memory
Working memory → Episodic (FAISS vectors) → Semantic (user facts) → Encrypted vault.

### 🛡️ Security Hardened
API auth, PII redaction, path sandboxing, command blocking, encrypted credentials, trade confirmation.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  📱 Desktop App (Electron)                                       │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Auto-starts Python backend • Splash screen • System tray   │ │
│  └──────────┬──────────────────────────────────────────────────┘ │
│             │ localhost:8000                                      │
│  ┌──────────▼──────────────────────────────────────────────────┐ │
│  │              🎭 Web UI (glassmorphism)                       │ │
│  │  Animated Face │ Waveform │ Chat │ Agent Dashboard          │ │
│  └──────────┬──────────────────────────┬───────────────────────┘ │
│             │ WebSocket                │ REST API                 │
│  ┌──────────▼──────────────────────────▼───────────────────────┐ │
│  │              VocaBrain (FastAPI + LangGraph)                 │ │
│  │  Enrich → Classify → Safety → [Agent/Tier0] → Store → Out  │ │
│  │                                                              │ │
│  │  ┌────────────┐  ┌──────────────┐  ┌──────────────────────┐ │ │
│  │  │MemoryVault │  │  10 Agents   │  │ Provider Manager     │ │ │
│  │  │ 4 layers   │  │  90+ tools   │  │ Ollama/OpenAI/Gemini │ │ │
│  │  └────────────┘  └──────────────┘  └──────────────────────┘ │ │
│  │  ┌────────────┐  ┌──────────────┐                           │ │
│  │  │ Safety     │  │ Event Bus    │                           │ │
│  │  │ Policy+PII │  │ SSE stream   │                           │ │
│  │  └────────────┘  └──────────────┘                           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Tier-Based LLM Routing

| Tier | Name | Engine | Cost | Example |
|------|------|--------|------|---------|
| 0 | Reflex | Regex | **Free** | "What time is it?" |
| 1 | Executor | Ollama (local) | **Free** | "Turn off the lights" |
| 2 | Specialist | GPT-4o-mini / Gemini Flash | $ | "Draft an email to John" |
| 3 | Strategist | GPT-4o | $$ | "Analyze my portfolio" |

---

## 🗣️ Voice Commands

### System Control
```
"Open Chrome" / "Launch VS Code" / "Open Spotify"
"Click at 500, 300" / "Double click the button"
"Press Ctrl+C" / "Alt+Tab" / "Win+D"
"List all windows" / "Focus Chrome" / "Minimize Slack"
"What processes are running?" / "Kill notepad"
"What's my CPU usage?" / "How much disk space?"
"Take a screenshot" / "What's on my screen?"
```

### Conversation & Life
```
"Hey Voca, how are you?" / "Tell me a joke"
"Schedule a meeting tomorrow at 3pm"
"Remind me to call Mom in 2 hours"
"Add 'buy groceries' to my todo list"
```

### Web & Research
```
"Go to twitter.com" / "Login to GitHub"
"Search the web for AI news"
"Summarize this URL: ..."
```

### Stock Trading
```
"What's Apple's stock price?"
"Buy 10 shares of Tesla" (paper or real)
"Show my portfolio" / "How's the market?"
```

### Smart Home
```
"Turn on the living room lights"
"Set thermostat to 72 degrees"
"Lock the front door"
```

---

## 🔌 API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/status` | System status + memory stats |
| `GET` | `/agents` | List all agents |
| `POST` | `/chat` | Send transcript, get response |
| `GET` | `/memory/facts` | List semantic facts |
| `POST` | `/memory/facts` | Store a fact |
| `GET` | `/events/stream` | SSE event stream |
| `POST` | `/webhook/tradingview` | TradingView alert webhook |
| `WS` | `/ws` | WebSocket real-time chat |

---

## 🖥️ Platform Support

| Platform | Client | System Control | Voice | CI Tested |
|----------|--------|---------------|-------|-----------|
| Windows | .exe NSIS | Full (20 tools) | ✅ | ✅ |
| macOS | .dmg | Full (20 tools) | ✅ | ✅ |
| Linux | .AppImage + .deb | Full (20 tools) | ✅ | ✅ |
| Android | React Native | Remote (via server) | ✅ Native STT/TTS | — |
| iOS | React Native | Remote (via server) | ✅ Native STT/TTS | — |

---

## 🧪 Testing — 200+ Tests

```bash
python verify.py                    # Pre-push verification (all checks)
pytest tests/ -v                    # All tests
pytest tests/ --cov=voca            # With coverage
ruff check . && ruff format .       # Lint
```

---

## 🔧 Development

### Build from Source

```bash
# 1. Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py --mode server

# 2. Electron app (dev mode)
cd electron && npm install && npm start

# 3. Build standalone installer
python build_backend.py             # Bundle Python backend
cd electron && node build.js win    # Package for Windows
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | LangGraph StateGraph |
| LLM | litellm → Ollama / OpenAI / Gemini |
| Desktop | Electron 28 + PyInstaller |
| GUI Automation | pyautogui + pygetwindow |
| System | psutil + pyperclip |
| STT/TTS | faster-whisper / pyttsx3 / Web Speech |
| Vector Store | FAISS + sentence-transformers |
| Browser | Playwright |
| Trading | yfinance + Alpaca + IBKR |
| Web UI | Vanilla JS + Canvas + Web Audio |
| API | FastAPI + WebSocket + SSE |

---

## 📦 Releases

See [CHANGELOG.md](CHANGELOG.md) for full version history.
See [Release Notes v0.5.0](docs/release_notes_v0.5.0.md) for detailed release notes.

---

## 📚 Documentation

Full documentation is available in the [`docs/`](docs/) folder:

| Document | Description |
|----------|-------------|
| [Documentation Home](docs/index.md) | Index of all documentation |
| [Getting Started](docs/getting_started.md) | Installation, first run, configuration |
| [Architecture](docs/architecture.md) | System design and component overview |
| [Agents Reference](docs/agents.md) | All 10 agents with tools and examples |
| [API Reference](docs/api_reference.md) | REST, WebSocket, and SSE endpoints |
| [Security](docs/security.md) | Safety policies, PII, sandboxing |
| [Configuration](docs/configuration.md) | All environment variables |
| [Development](docs/development.md) | Building, testing, contributing |
| [FAQ](docs/faq.md) | Troubleshooting and common questions |
| [Diagrams](docs/diagrams.md) | 7 Mermaid architecture diagrams |

### Generate API Docs (Doxygen)

```bash
pip install -r docs/requirements.txt
cd docs && doxygen Doxyfile          # HTML → docs/html/index.html
cd latex && make                      # PDF  → docs/latex/refman.pdf
```

| Version | Date | Highlights |
|---------|------|-----------|
| **0.5.0** | 2026-04-19 | **Standalone desktop app** (Win/Mac/Linux), 12 new system control tools, CI/CD builds |
| **0.4.1** | 2026-04-18 | 200+ tests, self-recovery, verify script |
| **0.4.0** | 2026-04-18 | Multi-agent crews, workflow engine, RBAC, Git agent, plugins |
| **0.3.1** | 2026-04-17 | Security hardening: API auth, encrypted credentials |
| **0.3.0** | 2026-04-17 | Browser agent, stock trading, screen vision |
| **0.2.0** | 2026-04-17 | Animated face, always-listening, buddy personality |
| **0.1.0** | 2026-04-16 | Initial release: 7 agents, LangGraph pipeline |

---

## 🤝 Contributing

1. Fork → `git checkout -b feature/amazing`
2. Make changes → `pytest tests/ -v` → `ruff check .`
3. `git commit -m "Add amazing feature"` → Push → Open PR

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>Built with ❤️ by Srikanth Patchava</b><br>
  <i>Voca — Your AI buddy that actually does things.</i>
</p>
