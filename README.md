<p align="center">
  <img src="https://img.shields.io/badge/Agents-9-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Tools-69-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Security-Hardened-brightgreen?style=for-the-badge&logo=shield" />
  <img src="https://img.shields.io/badge/Python-3.11+-yellow?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/License-MIT-red?style=for-the-badge" />
</p>

# 🎙️ Voca — Your AI Buddy That Controls Everything

> **Voice-first, always-listening, multi-agent AI system** with an animated face, 9 specialized agents, 69 real tools, and integrations for system control, web browsing, stock trading, smart home, and more.

Voca isn't a chatbot. It's a **living AI buddy** that sees your screen, browses the web, trades stocks, manages your files, controls your smart home, and remembers everything about you — all through natural voice commands.

---

## ✨ What Can Voca Do?

| Category | Agent | Tools | Examples |
|---|---|---|---|
| 💬 **Conversation** | Companion | 4 | Chat, jokes, mood check, activities |
| 💻 **System Control** | Operator | 8 | Open apps, run commands, manage files, screenshots, screen vision |
| 🌐 **Web Browsing** | Browser | 11 | Navigate sites, login, fill forms, post on social media |
| 🔍 **Research** | Researcher | 4 | Web search, summarize URLs, find papers, fact-check |
| ✍️ **Writing** | Writer | 4 | Draft, edit, format, translate |
| 📅 **Life Management** | Life Manager | 5 | Calendar, reminders, todos, email |
| 🏠 **Smart Home** | Home Controller | 6 | Lights, thermostat, locks, security, media (Home Assistant) |
| 📈 **Stock Trading** | Income | 14 | Real-time prices, paper trading, Alpaca, IBKR, TradingView |
| 💻 **Code Editing** | Coder | 5 | Read/write/edit files, search code, VS Code integration |

### 🔥 Killer Features

- **🎭 Animated Face** — 8 expressions (idle, listening, thinking, speaking, happy, sad, excited, error) with blinking, bobbing, mouth sync
- **📡 Always Listening** — 3 modes: Always On, Wake Word ("Hey Voca"), Push-to-Talk
- **👁️ Screen Vision** — Captures screen → sends to GPT-4o/Gemini vision → understands what you see
- **🌐 Browser Automation** — Full Playwright integration: login to any site, post on social media, fill forms
- **📊 Real Stock Trading** — Alpaca (free), Interactive Brokers, TradingView webhooks, paper trading
- **🧠 4-Layer Memory** — Working (conversation), Episodic (FAISS), Semantic (facts), Secure (encrypted)
- **🔧 Native Function Calling** — OpenAI-compatible tool schemas, regex fallback for Ollama
- **🛡️ Safety Engine** — PII redaction, policy rules (ALLOW/CONFIRM/DENY), dangerous command blocking
- **🏠 Home Assistant** — Real IoT control with JSON simulation fallback
- **🤝 Buddy Personality** — Learns your name, uses emoji, celebrates wins, empathizes with frustrations

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         🎭 Web UI                                │
│  Animated Face │ Waveform │ Chat │ Dashboard │ Mode Selector    │
└────────┬────────────────────────────────┬───────────────────────┘
         │ WebSocket                      │ REST API
┌────────▼────────────────────────────────▼───────────────────────┐
│                      VocaBrain (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              LangGraph StateGraph Pipeline                │   │
│  │  Enrich → Classify → Safety → [Agent/Tier0] → Store → Out│   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│  ┌───────────┐  ┌───────────┼───────────┐  ┌────────────────┐  │
│  │MemoryVault│  │   9 Agents│(69 Tools) │  │ProviderManager │  │
│  │ Working   │  │ companion │ operator  │  │ Ollama (local) │  │
│  │ Episodic  │  │ browser   │ coder     │  │ OpenAI (cloud) │  │
│  │ Semantic  │  │ researcher│ income    │  │ Gemini (cloud) │  │
│  │ Secure    │  │ writer    │ life_mgr  │  │ + fallback     │  │
│  └───────────┘  │ home_ctrl │           │  └────────────────┘  │
│                  └───────────────────────┘                       │
│  ┌────────────────────┐  ┌──────────────────────────────────┐  │
│  │ Safety Engine       │  │ Event Bus (SSE)                   │  │
│  │ Policy + Privacy    │  │ Async event streaming             │  │
│  └────────────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Tier-Based LLM Routing

| Tier | Name | Engine | Cost | Example |
|------|------|--------|------|---------|
| 0 | Reflex | Regex | **Free** | "What time is it?" |
| 1 | Executor | Ollama (local) | **Free** | "Turn off the lights" |
| 2 | Specialist | GPT-4o-mini / Gemini Flash | $ | "Draft an email to John" |
| 3 | Strategist | GPT-4o | $$ | "Analyze my portfolio performance" |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) (optional, for free local LLM)

### 1. Clone & Install

```bash
git clone https://github.com/patchava-sr/eVoca.git && cd eVoca
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Install Optional Dependencies

```bash
# Browser automation
pip install playwright && python -m playwright install chromium

# Stock market data
pip install yfinance

# Web search
pip install duckduckgo-search httpx beautifulsoup4

# Real broker trading
pip install alpaca-trade-api    # Alpaca
pip install ib_insync           # Interactive Brokers
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:
```env
# LLM Providers (at least one required)
VOCA_LLM_OPENAI_API_KEY=sk-...          # GPT-4o for best experience
VOCA_LLM_GEMINI_API_KEY=...             # Google Gemini
VOCA_LLM_OLLAMA_URL=http://localhost:11434  # Free local LLM

# Stock Trading (optional)
VOCA_ALPACA_API_KEY=...                 # Free at alpaca.markets
VOCA_ALPACA_SECRET_KEY=...
VOCA_ALPACA_PAPER=true                  # false for real money
VOCA_AUTO_TRADE_LIMIT=500               # Confirm trades above this $

# Smart Home (optional)
VOCA_HA_URL=http://homeassistant.local:8123
VOCA_HA_TOKEN=...

# Email (optional)
VOCA_SMTP_HOST=smtp.gmail.com
VOCA_SMTP_PORT=587
VOCA_SMTP_USER=you@gmail.com
VOCA_SMTP_PASS=app_password
```

### 4. Run

```bash
# Web UI with animated face (recommended)
python main.py --mode server
# Open http://localhost:8000

# Text mode (terminal, no mic)
python main.py --mode text

# Voice mode (requires microphone)
python main.py --mode cli

# Both voice + web server
python main.py --mode both
```

### 5. Docker

```bash
docker-compose up -d
# Open http://localhost:8000

# If using Ollama:
docker exec -it evoca-ollama-1 ollama pull llama3.2
```

---

## 🗣️ Voice Commands

### Conversation
- "Hey Voca, how are you?"
- "Tell me a joke"
- "My name is Srikanth"
- "I'm feeling tired"

### System Control
- "Open Chrome" / "Launch VS Code" / "Open Spotify"
- "List files in my Documents folder"
- "Take a screenshot"
- "What's on my screen?" *(uses AI vision)*
- "Run `ipconfig` in terminal"

### Web Browsing
- "Go to twitter.com"
- "Login to GitHub"
- "Post on Facebook: Having a great day!"
- "Search YouTube for cooking tutorials"

### Stock Trading
- "What's Apple's stock price?"
- "Buy 10 shares of Tesla" *(paper or real)*
- "Show my portfolio"
- "How's the market doing?"
- "Add NVIDIA to my watchlist"

### Life Management
- "Schedule a meeting tomorrow at 3pm"
- "Remind me to call Mom in 2 hours"
- "Add 'buy groceries' to my todo list"
- "What's on my calendar today?"

### Smart Home
- "Turn on the living room lights"
- "Set thermostat to 72 degrees"
- "Lock the front door"
- "Check security status"

### Code Editing
- "Read the file main.py"
- "Search for 'TODO' in my project"
- "Open app.js in VS Code"

### Research
- "Search the web for AI news"
- "Summarize this URL: ..."
- "Find papers about machine learning"

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

### WebSocket Protocol

```json
// Send
{"type": "transcript", "data": "Buy 5 shares of AAPL"}

// Receive
{
  "type": "response",
  "response": "Done! ✅ Paper trade executed...",
  "agent": "income",
  "tier": 3,
  "intent": "trading",
  "mood": "happy"
}
```

---

## 🧪 Testing

```bash
# All tests
pytest tests/ -v

# Skip slow tests
pytest tests/ -v -m "not slow"

# Coverage report
pytest tests/ --cov=voca --cov-report=html

# Lint
ruff check .

# Format
ruff format .
```

---

## 📁 Project Structure

```
eVoca/
├── main.py                    # Entry point (4 modes)
├── config.py                  # Pydantic Settings
├── voca/
│   ├── core.py                # VocaBrain singleton orchestrator
│   ├── app.py                 # FastAPI + WebSocket + webhooks
│   ├── brain/
│   │   ├── graph.py           # LangGraph pipeline (enrich→classify→safety→agent→store)
│   │   ├── router.py          # 4-tier intent classification
│   │   ├── supervisor.py      # Follow-up detection + routing
│   │   ├── state.py           # VocaState TypedDict
│   │   └── agents/
│   │       ├── base.py        # BaseAgent + native function calling + buddy personality
│   │       ├── companion.py   # Conversation, jokes, mood (4 tools)
│   │       ├── operator.py    # PC control, apps, files, vision (8 tools)
│   │       ├── browser.py     # Web automation, login, social media (11 tools)
│   │       ├── researcher.py  # Web search, papers, fact-check (4 tools)
│   │       ├── writer.py      # Draft, edit, format, translate (4 tools)
│   │       ├── life_manager.py# Calendar, reminders, todos, email (5 tools)
│   │       ├── home_controller.py # IoT + Home Assistant (6 tools)
│   │       ├── income.py      # Stocks, trading, portfolio (14 tools)
│   │       ├── coder.py       # Code editing, VS Code (5 tools)
│   │       ├── brokers.py     # Alpaca, IBKR, TradingView (7 tools)
│   │       └── vision.py      # Screen capture + vision LLM (3 tools)
│   ├── memory/                # 4-layer Contextual Vault
│   │   ├── working.py         # Conversation window
│   │   ├── episodic.py        # FAISS vector store
│   │   ├── semantic.py        # User facts (JSON)
│   │   └── secure.py          # Encrypted vault (Fernet)
│   ├── safety/
│   │   ├── policy.py          # ALLOW/CONFIRM/DENY rules
│   │   └── privacy.py         # PII detection + anonymization
│   ├── providers/
│   │   ├── manager.py         # Multi-LLM with native tool calling
│   │   └── models.py          # Tier definitions
│   ├── perception/            # Audio → VAD → STT
│   ├── action/                # TTS + Tool executor
│   ├── events/                # Async event bus
│   └── static/                # Web UI
│       ├── index.html         # Face-first layout
│       ├── style.css          # Dark theme + face styles
│       ├── app.js             # Main app + module integration
│       ├── face.js            # Animated face renderer (Canvas)
│       ├── waveform.js        # Audio waveform visualizer
│       └── listener.js        # Always-on speech recognition
├── data/                      # Persistent storage
│   ├── calendar.json          # Calendar events
│   ├── todos.json             # Todo list
│   ├── reminders.json         # Reminders
│   ├── portfolio.json         # Paper trading portfolio
│   ├── home_state.json        # Smart home state
│   ├── trade_log.json         # Trade audit log
│   └── browser_sessions/      # Cookies + credentials
├── tests/                     # pytest suite
├── .github/workflows/         # CI/CD
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## 🛡️ Safety & Privacy

| Layer | Protection |
|-------|-----------|
| **API Authentication** | `VOCA_SERVER_API_KEY` — Bearer token or query param auth on all endpoints |
| **Webhook Verification** | `VOCA_SERVER_WEBHOOK_SECRET` — HMAC secret on TradingView webhooks |
| **Localhost by Default** | Binds to `127.0.0.1` — not accessible from network unless explicitly changed |
| **Strict CORS** | Only `localhost:8000` allowed — malicious websites can't make cross-origin requests |
| **PII Detection** | Auto-detects SSN, credit cards, emails, phone numbers, IP addresses |
| **PII Anonymization** | PII replaced with `[REDACTED_TYPE]` before LLM calls |
| **Local Routing** | Sensitive content forced to local Ollama (never leaves machine) |
| **Policy Engine** | Per-agent per-tool rules: ALLOW / CONFIRM / DENY |
| **Command Safety** | 30+ dangerous patterns blocked, `shlex.split()` prevents shell injection |
| **Path Sandboxing** | File read/write restricted to home dir + CWD; `.ssh`, `.env`, `.aws` blocked |
| **Encrypted Credentials** | Browser passwords encrypted with Fernet via `SecureVault` |
| **Trade Safety** | Real broker trades require user confirmation; paper trading is default |
| **Input Sanitization** | App names validated (alphanumeric only); text input length-limited |
| **Ethics** | LLM refuses harmful/hateful/illegal content |

### Remote Access (Optional)

```env
# To allow remote access securely:
VOCA_SERVER_HOST=0.0.0.0                      # Open to network
VOCA_SERVER_API_KEY=your-secret-key-here       # REQUIRED for security
VOCA_SERVER_WEBHOOK_SECRET=webhook-secret       # For TradingView
```

Access from another device: `http://YOUR_IP:8000?api_key=your-secret-key-here`

For internet access, use [Tailscale](https://tailscale.com) (free VPN tunnel) — never expose Voca directly to the internet.

---

## 🔧 Tech Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | LangGraph StateGraph |
| LLM | litellm → Ollama / OpenAI / Gemini |
| Function Calling | Native OpenAI tool schemas + regex fallback |
| STT | faster-whisper (local) |
| TTS | pyttsx3 (local) + Web Speech API |
| Vector Store | FAISS + sentence-transformers |
| Web UI | Vanilla JS + Canvas + Web Audio API |
| Browser Automation | Playwright |
| Stock Data | yfinance |
| Broker APIs | Alpaca, Interactive Brokers (ib_insync) |
| Smart Home | Home Assistant REST API |
| Web Search | DuckDuckGo (no API key) |
| API | FastAPI + WebSocket + SSE |
| Encryption | Fernet (cryptography) |

---

## 📦 Releases

See [CHANGELOG.md](CHANGELOG.md) for version history.

| Version | Date | Highlights |
|---------|------|-----------|
| **0.3.1** | 2026-04-17 | Security hardening: API auth, encrypted credentials, path sandboxing, command injection fixes |
| **0.3.0** | 2026-04-17 | Browser agent, stock trading, screen vision, code editing |
| **0.2.0** | 2026-04-17 | Animated face, always-listening, buddy personality, tool execution |
| **0.1.0** | 2026-04-16 | Initial release: 7 agents, LangGraph pipeline, memory vault |

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Lint: `ruff check .`
6. Commit: `git commit -m "Add amazing feature"`
7. Push: `git push origin feature/amazing-feature`
8. Open a Pull Request

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>Built with ❤️ by Srikanth Patchava</b><br>
  <i>Voca — Your AI buddy that actually does things.</i>
</p>
