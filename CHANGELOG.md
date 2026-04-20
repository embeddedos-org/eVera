# Changelog

All notable changes to Voca are documented here.

## [0.5.1] — 2026-04-20

### 🎬 ContentCreator Agent (NEW — 5 tools)
- `generate_script` — AI video/content scripts for YouTube, TikTok, Instagram, LinkedIn, Twitter
- `create_video` — AI video generation via Runway, Pika, HeyGen, D-ID APIs
- `schedule_post` — Schedule social media posts with auto-publishing
- `optimize_seo` — SEO-optimized titles, descriptions, tags, best posting times
- `track_analytics` — Content dashboard: scripts, posts, videos, platform breakdown

### 🏦 Finance Agent (NEW — 6 tools)
- `check_balances` — Bank account balances via Plaid API or manual entry
- `view_transactions` — Recent transactions with category filtering
- `spending_analysis` — Spending breakdown by category with budget comparison
- `set_budget` — Monthly spending limits per category
- `add_account` / `add_transaction` — Manual account and expense tracking
- **Safety:** Money transfers are ALWAYS DENIED by policy

### 📧 Full Email Management (4 new tools added to Life Manager)
- `read_inbox` — Read recent emails via IMAP (unread filter, folder select)
- `read_email` — Read full email body by ID
- `reply_email` — AI-drafted reply with original context quoted
- `search_emails` — Search by keyword, sender, or subject
- Life Manager now has 9 tools (was 5)

### ⏰ Enhanced Proactive Scheduler (3 new background loops)
- **Recurring tasks** — Daily, weekly, and interval-based scheduled tasks from `scheduled_tasks.json`
- **Content auto-publisher** — Publishes scheduled social posts when their time arrives
- **Budget alerts** — Warns at 80% budget usage, alerts when exceeded
- Scheduler now runs 7 background loops (was 4)

### 📊 Stats
- 12 agents (was 10), 115+ tools (was 90+)
- 25+ new intent keywords for routing
- 7 scheduler loops (was 4)

## [0.5.0] — 2026-04-19

### 🖥️ Standalone Desktop App
- **Cross-platform installers**: Windows `.exe` (NSIS), macOS `.dmg`, Linux `.AppImage` + `.deb`
- No Python or Node.js installation required — everything bundled via PyInstaller + electron-builder
- CI/CD build pipeline via GitHub Actions for automated releases

### 💻 12 New System Control Tools (Operator Agent)
- `mouse_click`, `mouse_move`, `mouse_drag`, `scroll` — full mouse automation via pyautogui
- `press_hotkey` — keyboard shortcuts (Ctrl+C, Alt+Tab, Win+D)
- `manage_window` — list, focus, minimize, maximize, close windows (pygetwindow)
- `manage_process` — list, inspect, kill processes (psutil)
- `system_info` — CPU, memory, disk, battery, OS details (psutil)
- `manage_service` — list, start, stop, restart system services
- `network_info` — IP addresses, active connections, ping test
- `clipboard` — read/write system clipboard (pyperclip)
- `send_notification` — OS-level desktop notifications
- Total tools now: **90+** across 10 agents

### 📚 Documentation & Doxygen
- Full `docs/` folder with 9 structured documentation pages
- Doxygen configuration for HTML + PDF generation from docstrings
- 7 Mermaid architecture diagrams (system, pipeline, agents, memory, safety, build, routing)
- Doxygen-compatible `@param`/`@return` docstrings on all key modules
- Formal product release notes document

### ✨ Glassmorphism UI Redesign
- Complete visual overhaul with **glassmorphism theme** — frosted glass panels, `backdrop-filter: blur(20px)`, semi-transparent surfaces
- **Animated particle background** — floating CSS particles with orbital nebula effects
- **Gradient glow ring** around face canvas with rotating border animation
- New layout: face panel (left), agent panel (right), floating input bar (bottom)
- Smooth **spring-based animations** throughout — message bubbles, agent cards, timeline entries
- **Shimmer progress bars** with gradient fills for agent tool execution
- SVG send button, pulsing mic ripple effect, improved responsive breakpoints

### 👁️ Live Agent Visualization (3 Modes)
- **Card View** — Glass-effect agent cards showing real-time status (working/idle/done), current tool call, animated progress bar
- **Timeline View** — Vertical timeline with timestamps, agent icons, color-coded entries, staggered slide-in animations
- **Constellation View** — Canvas-based network graph with agent nodes, connection lines, animated particles along edges, pulsing glow on active agents
- View switcher in agent panel header (Cards | Timeline | Graph)

### 📡 Agent Status Streaming
- New `/agents/stream` SSE endpoint broadcasting real-time agent events
- `BaseAgent.run()` now emits status events: `working` (with tool name/args), `done` (with result preview)
- `_agent_status_queue` in EventBus for cross-component agent status transport
- Frontend `agents-view.js` consumes SSE stream and updates all 3 visualization modes live

### 🖥️ Electron Desktop App
- **Standalone desktop app** via Electron (`electron/` directory)
- Frameless window with system tray icon and context menu (Show/Hide, Always on Top, Start on Boot, Quit)
- **Global shortcut** `Ctrl+Shift+V` to toggle window
- Desktop notifications for proactive scheduler alerts
- Single-instance lock prevents multiple windows
- Build script for Windows `.exe`, macOS `.app`, Linux `.deb` via electron-builder

### 📱 PWA Support
- `manifest.json` with app name, theme colors, icons, shortcuts
- `sw.js` service worker — cache-first for static assets, network-first for API, SSE/WebSocket bypass
- Installable from Chrome/Edge/Safari as standalone app

### 🔧 Fixes
- Fixed Python 3.8 compatibility: `dict[str, Any]` → `Dict[str, Any]` in `bus.py` runtime expressions
- Applied 126 ruff auto-fixes across codebase

### 📁 New Files
- `voca/static/agents-view.js` — Live agent visualization (cards, timeline, constellation)
- `voca/static/manifest.json` — PWA manifest
- `voca/static/sw.js` — Service worker for offline caching
- `electron/main.js` — Electron main process (window, tray, shortcuts)
- `electron/preload.js` — Secure context bridge
- `electron/package.json` — Electron dependencies + build config
- `electron/build.js` — Packaging script

---

## [0.4.1] — 2026-04-18

### 🧪 Comprehensive Test Suite (200+ tests)
- **Foundational tests** (13) — Singleton, components, VocaResponse, VocaState, config defaults, model tiers
- **Security & Data Breach tests** (38) — Auth bypass, data leak prevention, path traversal, command injection, policy enforcement, audit logging, encrypted storage
- **Sanity tests** (19) — All imports, agent basics, router patterns, memory roundtrip
- **Performance tests** (10) — Tier0 <1ms, spell correction <5ms, PII detection <2ms, policy <0.5ms

### 🛡️ Self-Recovery
- Server auto-restarts on crash (up to 10 retries, exponential backoff)
- Browser auto-opens on server start
- Setup script configures 24/7 operation (disable sleep, Task Scheduler / systemd)

### 🔍 Verification Script
- `verify.py` — 130+ checks across 9 categories before pushing to GitHub
- Syntax check, import validation, agent registration, security, language, fallbacks, unit tests, lint, file structure

---

## [0.4.0] — 2026-04-18

### 🚀 Major Features
- **Multi-Agent Crews** — CrewAI/AutoGen-style collaboration with 4 strategies: sequential, parallel, hierarchical, debate. LLM-powered task decomposition across agents.
- **Workflow Engine** — n8n-style JSON pipelines: agent steps, conditions, template variables, persistence, REST API
- **Enterprise RBAC** — User management, 3 roles (admin/user/viewer), per-user API keys, PBKDF2 password hashing, full audit logging
- **Plugin System** — Auto-discovery of custom agents from `plugins/` directory, hot-reload, example plugin template
- **Git Agent** — 9 tools: git status, diff, commit, push, pull, branch, log, stash, AI-powered code review
- **Proactive Scheduler** — Background loops: reminder firing, calendar alerts (15 min warning), stock price alerts (5%+ moves), daily morning briefing
- **Messaging Bots** — Slack, Discord, Telegram webhook handlers: receive commands + push proactive notifications
- **19 Languages** — Speech recognition in 19 languages, auto-detection by script, language selector in UI
- **Spell Correction** — 50+ voice recognition fixes, fuzzy matching against 100+ command vocabulary

### 🐛 Bug Fixes
- Fixed `NameError` in TradingView webhook (`data` → `body`)
- Fixed test_agents.py expecting 9 agents (now 10)
- Fixed CI pipeline — lint/test failures now properly block the pipeline

### 🧪 Testing
- 120+ test cases across 15 test files
- New test files: test_rbac.py, test_workflow.py, test_plugins.py, test_scheduler.py
- Test coverage for RBAC (11 tests), workflow (5), plugins (4), scheduler (5)

### 📊 Stats
- 10 agents (+ unlimited via plugins), 78+ tools
- 20 API endpoints, 4 messaging platforms
- 19 languages, 4 crew strategies

---

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
- Native Python setup (venv + pip)
