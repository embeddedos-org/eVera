<p align="center">
  <pre align="center">
         __     __
   ___  \ \   / /___  _ __  __ _
  / _ \  \ \ / // _ \| '__|/ _` |
 |  __/   \ V /|  __/| |  | (_| |
  \___|    \_/  \___||_|   \__,_|
  </pre>
  <b>Voice-first multi-agent AI assistant that controls everything</b>
</p>

<p align="center">
  <a href="https://github.com/embeddedos-org/eVera/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/embeddedos-org/eVera/ci.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/embeddedos-org/eVera/actions/workflows/codeql.yml"><img src="https://img.shields.io/github/actions/workflow/status/embeddedos-org/eVera/codeql.yml?style=for-the-badge&label=CodeQL" alt="CodeQL"></a>
  <img src="https://img.shields.io/badge/v1.0.0-release-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Agents-43+-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Tools-278+-green?style=for-the-badge" />
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

[![Book](https://github.com/embeddedos-org/eVera/actions/workflows/book-build.yml/badge.svg)](https://github.com/embeddedos-org/eVera/actions/workflows/book-build.yml)

### Desktop App (Recommended — one-click, no Python needed)

| Platform | Download | Install |
|----------|----------|---------|
| **Windows** | [Vera-Setup.exe](https://github.com/srpatcha/eVera/releases/latest) | Run the installer |
| **macOS** | [Vera.dmg](https://github.com/srpatcha/eVera/releases/latest) | Open DMG → drag to Applications |
| **Linux** | [Vera.AppImage](https://github.com/srpatcha/eVera/releases/latest) | `chmod +x Vera-*.AppImage && ./Vera-*.AppImage` |

### From Source (Developer)

```bash
git clone https://github.com/srpatcha/eVera.git && cd eVera
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # Add your API keys
python main.py --mode server                         # Open http://localhost:8000
```

---

## ✨ Features

### 🎙️ Voice Control — 3 Modes
Always-on listening, wake word detection, or push-to-talk. Supports 19 languages with auto spell-correction.

### 🤖 24+ Specialized AI Agents — 183+ Tools

#### Core Agents (always loaded)

| Agent | Tools | What It Does |
|-------|-------|-------------|
| 💬 Companion | 4 | Chat, jokes, mood check, activity suggestions |
| 💻 Operator | 26 | Apps, scripts, files, mouse, keyboard, windows, processes, admin, GUI dialogs |
| 🌐 Browser | 11 | Navigate, login, fill forms, post on social media (auto-installs Playwright) |
| 🔍 Researcher | 4 | Web search, summarize URLs, papers, fact-check |
| ✍️ Writer | 4 | Draft, edit, format, translate |
| 📅 Life Manager | 9 | Calendar, reminders, todos, email (IMAP read/reply/search) |
| 🏠 Home Controller | 7 | Lights, thermostat, locks, security, media, setup wizard |
| 📈 Income | 15 | Real-time prices, paper trading, Alpaca, IBKR, trading setup wizard |
| 💻 Coder | 5 | Read/write/edit files, search code, VS Code (path overrides) |
| 📦 Git | 10 | Status, diff, commit, push, AI code review, **create PRs** |
| 🎬 Content Creator | 5 | Video scripts, AI video generation, social media scheduling, SEO |
| 🏦 Finance | 6 | Bank balances, transactions, spending analysis, budgets |
| 📋 Planner | 8 | Morning plans, daily/weekly/monthly reviews, goal setting, Eisenhower matrix |
| 🧘 Wellness | 7 | Focus sessions (pomodoro), breaks, screen time, energy tracking, burnout prevention |
| 📰 Digest | 6 | RSS feeds, news digests, reading lists, thread summarization |
| 🌍 Language Tutor | 5 | Language lessons, vocabulary, grammar, pronunciation, quizzes (16+ languages) |
| 🗺️ Codebase Indexer | 4 | **Project indexing, architecture analysis, definition extraction, related files** |
| 📝 Meeting | 3 | **Extract action items, parse meeting notes, create tasks from transcripts** |
| 📊 Diagram | 4 | **Call graphs, class diagrams, flowcharts, export to SVG/PNG/PDF** |

#### Conditional Agents (enabled via config)

| Agent | Tools | Enabled By | What It Does |
|-------|-------|-----------|-------------|
| 📱 Mobile Controller | 6 | `VERA_MOBILE_CONTROL_ENABLED` | Send notifications, open apps, set alarms, toggle settings |
| 💼 Job Hunter | 12 | `VERA_JOB_ENABLED` | Autonomous job search, resume matching, auto-apply, application tracking |
| 🎫 Jira | 7 | `VERA_JIRA_ENABLED` | **Tickets, sprints, create/update issues, JQL search, comments** |
| 🚀 Work Pilot | 3 | `VERA_JIRA_ENABLED` | **Autonomous ticket→branch→code→PR→Jira workflow** |
| 🎨 Media Factory | 12 | `VERA_MEDIA_ENABLED` | **Image gen (Pollinations/DALL-E), photo editing, video assembly, subtitles, voiceovers, YouTube/Instagram/TikTok upload** |

### 💻 Full System Control (v0.5.0+)
- 🖱️ **Mouse** — click, move, drag, scroll at any screen coordinates
- ⌨️ **Keyboard** — press any hotkey (Ctrl+C, Alt+Tab, Win+D)
- 🪟 **Windows** — list, focus, minimize, maximize, close windows
- ⚙️ **Processes** — list, inspect, kill running processes
- 📊 **System Info** — CPU, memory, disk, battery, OS details
- 🔧 **Services** — list, start, stop, restart system services
- 🌐 **Network** — IP info, connections, ping test
- 📋 **Clipboard** — read/write system clipboard
- 🔔 **Notifications** — send OS-level desktop notifications

### 🆕 New in v0.9.0 — 3D Holographic Avatar

- 🎭 **3D Avatar** — Full Three.js WebGL humanoid replacing 2D canvas face: procedural body, holographic shaders, particle aura
- 🤖 **8 Gesture Animations** — Chin stroke, wave, thumbs up, open palms, clasped hands, defensive, droop — auto-triggered by expression
- ✨ **Holographic Materials** — Custom GLSL shaders with fresnel glow, circuit-line patterns, energy pulse waves
- 🛡️ **Production Hardened** — WebGL/Three.js fallback, Page Visibility API, FPS monitoring, CSP headers, SRI CDN, error boundaries
- 🔒 **Security Upgrade** — Content Security Policy meta tag, X-Content-Type-Options, Referrer-Policy, crossorigin CDN loading

### 🆕 New in v0.8.0 — eVera Rebrand

- 🏷️ **Full rebrand** — eSri → eVera across 165 files, all imports, class names, configs, UI, and CI/CD
- 📦 **Unified versioning** — All packages (Python, Electron, mobile) synced to v0.8.0
- 🔄 **CI/CD overhaul** — Consolidated workflows, automated cross-platform releases

### 🆕 v0.7.0 — Office Work Automation

- 🎫 **Jira Integration** — Full REST API: get/create/update tickets, sprint boards, JQL search, comments
- 🚀 **Work Pilot** — Autonomous pipeline: fetch ticket → create branch → commit → push → create PR → update Jira
- 📝 **Meeting Agent** — Extract action items from transcripts, auto-create todos + Jira tickets
- 🗺️ **Codebase Indexer** — Index projects, extract definitions, architecture summaries, find related files
- 💬 **Slack Channel Monitor** — Poll channels for activity, @mention alerts, message summaries
- 🔀 **PR Creation** — `git_create_pr` tool via `gh` CLI or GitHub REST API fallback
- ⏰ **2 New Scheduler Loops** — Automatic ticket scanning + channel monitoring
- ⚙️ **4 New Config Blocks** — `VERA_JIRA_*`, `VERA_CHANNEL_*`, `VERA_CODEBASE_*`, `VERA_MEETING_*`

### 🎭 3D Holographic Avatar (v0.9.0)
Full **Three.js WebGL** humanoid avatar replacing the 2D canvas face:
- Procedural geometric mannequin body — head, torso, neck, arms, hands with 5 fingers
- **Holographic ShaderMaterial** — fresnel rim glow, circuit-line UV grid, energy pulse wave, wireframe overlay
- **8 gesture animations** auto-triggered by expression — chin stroke, wave, thumbs up, open palms, clasped hands, defensive, droop, rest
- **200-particle aura** with orbital motion and additive blending
- Idle breathing, head micro-bob, shoulder sway, finger micro-curl
- **Production hardened** — WebGL fallback, Page Visibility API (pauses when tab hidden), FPS monitoring with adaptive quality, CSP headers, SRI-protected CDN with local fallback, complete resource cleanup on destroy, error boundaries

### 👁️ Screen Vision + Real-time Monitoring
Captures your screen → GPT-4o / Gemini vision analysis. Ask "what's on my screen?"
Enable `VERA_VISION_MONITOR_ENABLED=true` for continuous background monitoring with hash-based debounce.

### 📊 Real Stock Trading
Paper trading, Alpaca, Interactive Brokers, TradingView alerts webhook.

### 🧠 4-Layer Memory
Working memory → Episodic (FAISS vectors) → Semantic (user facts) → Encrypted vault.

### 🛡️ Security Hardened
API auth, PII redaction, path sandboxing, command blocking, encrypted credentials, trade confirmation.

### 🧠 Emotional Intelligence
Sentiment analysis (keyword + LLM hybrid), mood tracking, pattern detection, proactive empathy notifications.

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
│  │              VeraBrain (FastAPI + LangGraph)                 │ │
│  │  Enrich → Classify → Safety → [Agent/Tier0] → Store → Out  │ │
│  │                                                              │ │
│  │  ┌────────────┐  ┌──────────────┐  ┌──────────────────────┐ │ │
│  │  │MemoryVault │  │ 24+ Agents   │  │ Provider Manager     │ │ │
│  │  │ 4 layers   │  │ 183+ tools   │  │ Ollama/OpenAI/Gemini │ │ │
│  │  └────────────┘  └──────────────┘  └──────────────────────┘ │ │
│  │  ┌────────────┐  ┌──────────────┐  ┌──────────────────────┐ │ │
│  │  │ Safety     │  │ Event Bus    │  │ Proactive Scheduler  │ │ │
│  │  │ Policy+PII │  │ SSE stream   │  │ 15 background loops  │ │ │
│  │  └────────────┘  └──────────────┘  └──────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Tier-Based LLM Routing

| Tier | Name | Engine | Cost | Example |
|------|------|--------|------|---------|
| 0 | Reflex | Regex | **Free** | "What time is it?" |
| 1 | Executor | Ollama (local) | **Free** | "Turn off the lights" |
| 2 | Specialist | GPT-4o-mini / Gemini Flash | $ | "Draft an email to John" |
| 3 | Strategist | GPT-4o | $$ | "Start work on ticket PROJ-123" |

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
"Hey Vera, how are you?" / "Tell me a joke"
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

### Office & Work (v0.7.0+)
```
"Show my Jira tickets" / "Get ticket PROJ-123"
"Create a ticket: fix login bug"
"Check the sprint board"
"Start work on PROJ-456" → Creates branch, tracks state
"Complete work on PROJ-456" → Commits, pushes, creates PR, updates Jira
"Extract action items from these meeting notes: ..."
"Create tasks from this transcript: ..."
"Index the project at /path/to/repo"
"What's the architecture of this project?"
"Find files related to authentication"
"Create a PR for this branch"
```

### Media Creation (v0.8.1+)
```
"Generate an image of a sunset over the ocean"
"Edit image — resize to 1080x1920" / "Make it grayscale" / "Remove the background"
"Add text overlay: Breaking News"
"Create a voiceover: Welcome to today's update"
"Assemble a video from these images with Ken Burns transitions"
"Add subtitles to this video"
"Create a reel about AI trends and upload to YouTube"
"Upload this video to Instagram as a reel"
```

### Productivity
```
"Plan my day" / "Daily review" / "Set a goal"
"Start a focus session" / "Take a break"
"Generate my daily digest" / "What's the news?"
"Teach me Spanish" / "Quiz me on French vocabulary"
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
| `WS` | `/ws/voice` | Voice I/O (PCM16 in, TTS audio out) |
| `WS` | `/ws/mobile` | Mobile device control ([protocol docs](docs/mobile_protocol.md)) |

---

## 🖥️ Platform Support

| Platform | Client | System Control | Voice | CI Tested |
|----------|--------|---------------|-------|-----------|
| Windows | .exe NSIS | Full (26 tools) | ✅ | ✅ |
| macOS | .dmg | Full (26 tools) | ✅ | ✅ |
| Linux | .AppImage + .deb | Full (26 tools) | ✅ | ✅ |
| Android | React Native | Remote (via server) | ✅ Native STT/TTS | — |
| iOS | React Native | Remote (via server) | ✅ Native STT/TTS | — |

---

## ⚙️ Configuration — Office Automation & Media

Add to your `.env` file to enable advanced features:

```bash
# Jira Integration
VERA_JIRA_ENABLED=true
VERA_JIRA_BASE_URL=https://myorg.atlassian.net
VERA_JIRA_USERNAME=you@company.com
VERA_JIRA_API_TOKEN=your_jira_api_token
VERA_JIRA_PROJECT_KEY=PROJ
VERA_JIRA_BOARD_ID=1
VERA_JIRA_SCAN_INTERVAL_MINUTES=15

# Slack Channel Monitoring
VERA_CHANNEL_ENABLED=true
VERA_CHANNEL_CHANNELS=["C01ABC123","C02DEF456"]
VERA_CHANNEL_POLL_INTERVAL_MIN=5
VERA_CHANNEL_SUMMARIZE=true
VERA_CHANNEL_MENTION_ALERT=true

# Codebase Indexer (enabled by default)
VERA_CODEBASE_DEFAULT_PROJECT_PATH=/path/to/your/project
VERA_CODEBASE_MAX_FILES=500

# Meeting Agent (enabled by default)
VERA_MEETING_AUTO_CREATE_TICKETS=false
VERA_MEETING_AUTO_CREATE_TODOS=true

# Media Factory (enabled by default)
VERA_MEDIA_ENABLED=true
VERA_MEDIA_DALLE_API_KEY=              # Optional: premium image gen (free Pollinations used by default)
VERA_MEDIA_YOUTUBE_CLIENT_SECRETS_PATH= # Path to YouTube OAuth client_secret.json
VERA_MEDIA_INSTAGRAM_ACCESS_TOKEN=      # Instagram Graph API token
VERA_MEDIA_DEFAULT_VOICE=en-US-AriaNeural
VERA_MEDIA_DEFAULT_ASPECT_RATIO=9:16
VERA_MEDIA_DEFAULT_IMAGE_PROVIDER=pollinations  # pollinations (free) or dalle
```

---

## 🔒 Security

eVera includes multiple security layers to prevent misuse and protect sensitive data:

| Layer | Description |
|-------|------------|
| **Policy Engine** | Rule-based ALLOW/CONFIRM/DENY per agent.tool pattern (`vera/safety/policy.py`) |
| **Path Sandboxing** | All file operations validated against ALLOWED_ROOTS and BLOCKED_PATHS |
| **PII Detection** | Real-time PII scanning with auto-redaction before LLM calls |
| **RBAC** | Role-based access control (admin/user/viewer) with API key auth |
| **Command Blocking** | 50+ dangerous shell patterns blocked (rm -rf, format, dd, etc.) |
| **Injection Prevention** | PowerShell/AppleScript input escaping, shlex parsing for sudo |
| **Audit Logging** | Every tool execution and elevated action logged with timestamps |

---

## 🧪 Testing — 600+ Tests

```bash
python verify.py                    # Pre-push verification (all checks)
pytest tests/ -v                    # All tests (600+ pass)
pytest tests/ --cov=vera            # With coverage
ruff check . && ruff format .       # Lint
python test_api_e2e.py              # E2E API integration tests (26 endpoints)
```

---

## 🚀 Deployment

### Server Modes

```bash
python main.py --mode server        # REST API + WebSocket (default port 8000)
python main.py --mode cli            # Voice-only CLI loop (mic → STT → brain → TTS)
python main.py --mode both           # Server + voice simultaneously
python main.py --mode text           # Text-only CLI (no mic needed)
python main.py --mode server --port 8001  # Custom port
```

### Staging Deployment

1. **Install dependencies and configure:**
   ```bash
   git clone https://github.com/embeddedos-org/eVera.git && cd eVera
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env              # Fill in API keys
   ```

2. **Start the staging server:**
   ```bash
   python main.py --mode server --port 8001
   ```

3. **Run integration tests:**
   ```bash
   # In a second terminal:
   python test_api_e2e.py            # 26 endpoint tests (uses TestClient, no live server needed)
   pytest tests/ -v -m "not slow"    # Full test suite
   ```

4. **Verify live endpoints:**
   ```bash
   curl http://localhost:8001/health           # {"status": "ok"}
   curl http://localhost:8001/status           # Version, agents, scheduler loops
   curl http://localhost:8001/agents           # 19+ registered agents
   curl -X POST http://localhost:8001/chat \
     -H "Content-Type: application/json" \
     -d '{"transcript": "Hello Vera!"}'        # Chat response
   ```

### Production Deployment

1. **Set environment variables** (see `.env.example` for all 20+ config sections):
   ```bash
   export VERA_SERVER_HOST=0.0.0.0           # Bind to all interfaces
   export VERA_SERVER_PORT=8000
   export VERA_SERVER_API_KEY=your-secret    # Enable API authentication
   export VERA_LLM_OPENAI_API_KEY=sk-...    # At least one LLM provider
   ```

2. **Start with production settings:**
   ```bash
   python main.py --mode server --host 0.0.0.0 --port 8000
   ```

3. **Health monitoring:**
   - `GET /health` — returns `{"status": "ok"}`
   - `GET /status` — returns version, agent count, active scheduler loops, memory stats
   - `GET /agents` — lists all registered agents with descriptions
   - `GET /models/health` — checks all configured LLM providers

### Desktop App Build

```bash
python deploy.py --desktop           # Electron + PyInstaller (current platform)
python deploy.py --desktop --platform win   # Windows .exe
python deploy.py --desktop --platform mac   # macOS .dmg
python deploy.py --desktop --platform linux # Linux .AppImage
```

### Mobile App Build

```bash
python deploy.py --mobile            # Android APK + iOS IPA
python deploy.py --android-only      # Android only
python deploy.py --ios-only           # iOS only (requires macOS + Xcode)
```

### CI/CD Pipeline

Pushing to `master` triggers 3 GitHub Actions workflows:

| Workflow | Jobs | What It Checks |
|----------|------|---------|
| **eVera CI** | Lint, Format, Security, Tests (4 matrix), Frontend | Ruff, Bandit, pytest on Python 3.11+3.12 × Ubuntu+Windows, static assets |
| **CodeQL** | Static analysis | SAST security scanning |
| **OSSF Scorecard** | Supply chain | OpenSSF security best practices |

Tagging `v*` (e.g., `v1.0.0`) triggers the **Build & Release** workflow which builds Desktop (Win/Mac/Linux) + Android + iOS and creates a GitHub Release.

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
| STT/TTS | faster-whisper / pyttsx3 / edge-tts / Web Speech |
| Vector Store | FAISS + sentence-transformers |
| Browser | Playwright |
| Trading | yfinance + Alpaca + IBKR |
| Tickets | Jira Cloud REST API + httpx |
| Web UI | Vanilla JS + Three.js WebGL + Canvas + Web Audio |
| API | FastAPI + WebSocket + SSE |

---

## 📦 Releases

See [CHANGELOG.md](CHANGELOG.md) for full version history.

| Version | Date | Highlights |
|---------|------|-----------|
| **1.0.0** | 2026-04-28 | **Production ready**: 52 gaps fixed, 43 agents, 278+ tools, conditional scheduler, keyword routing fixes, safety policies, 100% changeset coverage |
| **0.9.0** | 2026-04-24 | **3D Avatar**: Three.js holographic mannequin, gesture animations, production hardening, CSP security |
| **0.8.0** | 2026-04-22 | **Rebrand**: eSri → eVera, unified versioning, CI/CD overhaul |
| **0.7.0** | 2026-04-22 | **Office automation**: Jira agent (7 tools), Work Pilot (ticket→PR), Meeting agent, Codebase Indexer, Slack channel monitor, PR creation, 4 new config blocks |
| **0.6.0** | 2026-04-21 | Vision monitor, voice server, admin ops, GUI tools, path overrides, Playwright auto-install, setup wizards, mobile control |
| **0.5.1** | 2026-04-20 | Content creator, finance agent, email management, enhanced scheduler |
| **0.5.0** | 2026-04-19 | **Standalone desktop app** (Win/Mac/Linux), 12 new system control tools, CI/CD builds |
| **0.4.1** | 2026-04-18 | 200+ tests, self-recovery, verify script |
| **0.4.0** | 2026-04-18 | Multi-agent crews, workflow engine, RBAC, Git agent, plugins |
| **0.3.1** | 2026-04-17 | Security hardening: API auth, encrypted credentials |
| **0.3.0** | 2026-04-17 | Browser agent, stock trading, screen vision |
| **0.2.0** | 2026-04-17 | Animated face, always-listening, buddy personality |
| **0.1.0** | 2026-04-16 | Initial release: 7 agents, LangGraph pipeline |

---

## 📚 Documentation

Full documentation is available in the [`docs/`](docs/) folder:

| Document | Description |
|----------|-------------|
| [Documentation Home](docs/index.md) | Index of all documentation |
| [Getting Started](docs/getting_started.md) | Installation, first run, configuration |
| [Architecture](docs/architecture.md) | System design and component overview |
| [Agents Reference](docs/agents.md) | All 24+ agents with tools and examples |
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
  <i>eVera — Your AI assistant that actually does things.</i>
</p>

## Security

Please see [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Contributing

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.


---
Part of the [EmbeddedOS Organization](https://embeddedos-org.github.io).
