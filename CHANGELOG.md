# Changelog

All notable changes to Voca are documented here.

## [0.3.1] — 2026-04-17

### 🔒 Security Hardening (Full Audit + 15 Fixes)

#### CRITICAL Fixes
- **Encrypted credential storage** — Browser passwords now encrypted with Fernet via `SecureVault` instead of plaintext JSON
- **Hardened command execution** — 30+ dangerous patterns blocked (rm, del, format, curl|bash, base64 decode, etc.), `shlex.split()` used instead of `shell=True`
- **Webhook authentication** — `/webhook/tradingview` now requires `X-Webhook-Secret` header verification
- **Shell injection prevention** — Metacharacter injection blocked in Python/PowerShell execution
- **App name sanitization** — Only alphanumeric characters, spaces, and hyphens allowed in app launch commands

#### HIGH Fixes
- **API key authentication** — All REST and WebSocket endpoints protected by `VOCA_SERVER_API_KEY` (Bearer token or query param)
- **Localhost default** — Server binds to `127.0.0.1` instead of `0.0.0.0` — not network-accessible by default
- **Strict CORS** — Default origins changed from `*` to `["http://localhost:8000"]`
- **Path sandboxing** — File read/write/edit restricted to user's home directory and CWD; `.ssh`, `.env`, `.aws`, `.gnupg` directories blocked
- **TypeText injection fix** — Text written to temp file instead of inline PowerShell string; 500 char limit added
- **Encrypted session cookies** — Browser cookies stored alongside encrypted vault

#### Configuration
- New env vars: `VOCA_SERVER_API_KEY`, `VOCA_SERVER_WEBHOOK_SECRET`
- Secure defaults for `VOCA_SERVER_HOST` and `VOCA_SERVER_CORS_ORIGINS`

---

## [0.3.0] — 2026-04-17

### 🚀 Major Features
- **Browser Agent** — Full Playwright automation: navigate sites, login, fill forms, post on social media (11 tools)
- **Stock Trading** — Real broker integration: Alpaca (free), Interactive Brokers, TradingView webhooks (14 tools total)
- **Screen Vision** — Capture screen and analyze with GPT-4o/Gemini vision (3 tools)
- **Code Editing** — Read, write, edit files, search codebases, VS Code integration (5 tools)
- **Native Function Calling** — OpenAI-compatible tool schemas via litellm, regex fallback for Ollama

### 🔧 Improvements
- Home Controller now supports real Home Assistant API with local simulation fallback
- Researcher uses DuckDuckGo search (no API key needed) + arXiv papers
- Life Manager has working calendar, todos, reminders (JSON persistence), email (SMTP)
- All agents upgraded with buddy personality and emoji
- TradingView webhook endpoint at `/webhook/tradingview`
- Paper trading with $100k virtual cash portfolio
- Cross-platform Operator: Windows, macOS, Linux

### 🛡️ Safety
- Real broker trades require user confirmation
- Auto-trade limit ($500 default, configurable)
- Trade audit log in `data/trade_log.json`
- Browser login/form-fill requires confirmation

### 📊 Stats
- 9 agents, 69 tools (up from 7 agents, 31 stub tools)
- New files: `browser.py`, `brokers.py`, `coder.py`, `vision.py`

---

## [0.2.0] — 2026-04-17

### 🚀 Major Features
- **Animated Face** — Canvas-based with 8 expressions, blinking, bobbing, mouth sync
- **Audio Waveform** — Web Audio API visualizer synced to mic input
- **Always-On Listening** — 3 modes: Push-to-Talk, Wake Word ("Hey Voca"), Always On
- **Buddy Personality** — Warm, emoji-rich, name-aware personality across all agents
- **Tool Execution Pipeline** — LLM can now call tools and receive results

### 🔧 Improvements
- Username detection and personalized greetings
- Mood field in all responses driving face expressions
- WebSocket greeting on connect with name awareness
- VocaState TypedDict updated with `mood` and `user_name` fields
- Tier 0 responses updated with buddy personality
- Confirmation flow stores and replays pending actions

### 📁 New Files
- `voca/static/face.js` — Animated face renderer
- `voca/static/waveform.js` — Audio waveform visualizer
- `voca/static/listener.js` — Continuous listening manager

---

## [0.1.0] — 2026-04-16

### 🎉 Initial Release
- 7 agents: companion, operator, researcher, writer, life_manager, home_controller, income
- LangGraph StateGraph pipeline: enrich → classify → safety → agent → store → synthesize
- 4-tier LLM routing: Regex → Ollama → Cloud → Chain
- 4-layer memory vault: Working, Episodic (FAISS), Semantic, Secure
- FastAPI + WebSocket + SSE
- Safety: policy engine + PII detection + privacy guard
- Dark theme web UI with chat + dashboard
- Docker + docker-compose support
