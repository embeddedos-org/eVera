# 🚀 eVera v0.8.0 — Release Distribution Guide

## Download

| Platform | Installer | Size | Requirements |
|----------|-----------|------|-------------|
| **Windows 10/11** | [Vera Setup 0.8.0.exe](https://github.com/srpatcha/eVera/releases/download/v0.8.0/Vera.Setup.0.8.0.exe) | ~91 MB | None |
| **macOS 12+** | [Vera-0.8.0.dmg](https://github.com/srpatcha/eVera/releases/download/v0.8.0/Vera-0.8.0.dmg) | ~110 MB | None |
| **Linux** | [Vera-0.8.0.AppImage](https://github.com/srpatcha/eVera/releases/download/v0.8.0/Vera-0.8.0.AppImage) | ~130 MB | None |
| **Android** | [Vera-0.8.0.apk](https://github.com/srpatcha/eVera/releases/download/v0.8.0/Vera-0.8.0.apk) | ~25 MB | Android 8+ |
| **iOS** | TestFlight (coming soon) | — | iOS 15+ |
| **Source** | [v0.8.0.zip](https://github.com/srpatcha/eVera/archive/refs/tags/v0.8.0.zip) | ~2 MB | Python 3.11+ |

> **Note:** Desktop installers are built automatically via CI/CD on each tagged release. Mobile builds are included when available.

---

## Installation

### Windows

1. Download `Vera Setup 0.8.0.exe`
2. Double-click to run the installer
3. Choose installation directory (or use default)
4. Launch **Vera** from the Start Menu or Desktop shortcut
5. Press `Ctrl+Shift+V` anytime to toggle the window

**First launch:** The app shows a splash screen while the Python backend starts (~5 seconds).

### macOS

1. Download `Vera-0.8.0.dmg`
2. Open the DMG file
3. Drag **Vera** to the **Applications** folder
4. Launch from Applications
5. If blocked by Gatekeeper: **System Settings → Privacy & Security → Open Anyway**

### Linux

```bash
chmod +x Vera-0.8.0.AppImage
./Vera-0.8.0.AppImage
```

Or install the `.deb` package:
```bash
sudo dpkg -i Vera-0.8.0-amd64.deb
```

### Android

1. Download `Vera-0.8.0.apk` to your phone
2. Open the APK → tap **Install** (enable "Install from unknown sources" if prompted)
3. Launch Vera → enter your PC's IP in Settings
4. Grant microphone permission when prompted
5. Start talking!

### From Source (Developer)

```bash
git clone https://github.com/srpatcha/eVera.git && cd eVera
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # Add your API keys
python main.py --mode server                         # Open http://localhost:8000
```

---

## First-Time Setup

### 1. Configure an LLM Provider

eVera needs at least one LLM provider. Options (in order of recommendation):

| Provider | Cost | Setup |
|----------|------|-------|
| **Ollama** (local) | Free | Install [Ollama](https://ollama.ai), run `ollama pull llama3.2` |
| **OpenAI** | $0.15/1M tokens | Get API key from [platform.openai.com](https://platform.openai.com) |
| **Google Gemini** | $0.075/1M tokens | Get API key from [aistudio.google.com](https://aistudio.google.com) |

**Desktop app:** Click ⚙️ Settings → enter your API key
**Source install:** Edit `.env` file:
```env
VERA_LLM_OPENAI_API_KEY=sk-your-key-here
# or
VERA_LLM_GEMINI_API_KEY=your-gemini-key
```

### 2. Test It

Type or say any of these:
```
"Hey Vera, what time is it?"
"Open Chrome"
"Tell me a joke"
"What's Apple's stock price?"
"Remind me to call Mom in 2 hours"
```

### 3. Mobile Setup (Optional)

To use Vera from your phone:

1. On your PC, set `VERA_SERVER_HOST=0.0.0.0` in `.env`
2. Restart the server
3. Find your PC's IP: run `ipconfig` (Windows) or `ifconfig` (Mac/Linux)
4. On your phone, open the Vera app → Settings → enter your PC's IP
5. Tap "Test & Connect"

---

## What's Included

### Desktop App
- Frameless Electron window with system tray
- Global shortcut `Ctrl+Shift+V`
- Bundled Python backend (no Python installation needed)
- Auto-start on boot (optional)
- Desktop notifications for proactive alerts

### 23+ AI Agents — 165+ Tools

| Agent | Tools | Capabilities |
|-------|-------|-------------|
| 💬 Companion | 4 | Chat, jokes, mood, activities |
| 💻 Operator | 26 | Apps, mouse, keyboard, windows, processes, system info, services, admin |
| 🌐 Browser | 11 | Navigate, login, forms, social media |
| 🔍 Researcher | 4 | Web search, summarize, papers, fact-check |
| ✍️ Writer | 4 | Draft, edit, format, translate |
| 📅 Life Manager | 9 | Calendar, reminders, todos, email (IMAP) |
| 🏠 Home Controller | 7 | Lights, thermostat, locks, security, media |
| 📈 Income | 15 | Stocks, trading, Alpaca, IBKR, TradingView |
| 💻 Coder | 5 | Read/write/edit files, VS Code |
| 📦 Git | 10 | Status, diff, commit, push, AI review, PRs |
| 🎬 Content Creator | 5 | Video scripts, AI video, social scheduling, SEO |
| 🏦 Finance | 6 | Balances, transactions, spending, budgets |
| 📋 Planner | 8 | Morning plans, reviews, goals, Eisenhower matrix |
| 🧘 Wellness | 7 | Focus sessions, breaks, screen time, energy |
| 📰 Digest | 6 | RSS feeds, news, reading lists |
| 🌍 Language Tutor | 5 | Lessons, vocabulary, grammar, quizzes (16+ languages) |
| 🗺️ Codebase Indexer | 4 | Project indexing, architecture, definitions |
| 📝 Meeting | 3 | Action items, task creation, summaries |
| 📱 Mobile | 6 | Notifications, apps, alarms, settings (conditional) |
| 💼 Job Hunter | 12 | Job search, resume matching, auto-apply (conditional) |
| 🎫 Jira | 7 | Tickets, sprints, JQL search, comments (conditional) |
| 🚀 Work Pilot | 3 | Ticket→branch→code→PR→Jira (conditional) |

### Security
- API key authentication on all endpoints
- Safety policy engine (ALLOW / CONFIRM / DENY per action)
- PII detection and anonymization
- Path sandboxing and command blocking
- Encrypted credential storage
- Trade confirmation for real broker orders

---

## System Requirements

| | Minimum | Recommended |
|--|---------|-------------|
| **OS** | Windows 10 / macOS 12 / Ubuntu 20.04 | Windows 11 / macOS 14 / Ubuntu 22.04 |
| **RAM** | 4 GB | 8 GB (16 GB for local LLM) |
| **Disk** | 500 MB | 2 GB (with Ollama models) |
| **Network** | Internet for cloud LLM | LAN for mobile app connection |

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| App won't start | Check system tray for existing instance; kill and relaunch |
| "Connection refused" | Ensure server is running on port 8000 |
| No voice response | Check `VERA_LLM_*` API keys in `.env` |
| Mobile can't connect | Set `VERA_SERVER_HOST=0.0.0.0` and use same WiFi network |
| macOS Gatekeeper blocks | System Settings → Privacy & Security → Open Anyway |
| Linux AppImage won't run | `chmod +x Vera-*.AppImage` |
| Slow responses | Use smaller Ollama model or switch to cloud provider |

---

## Links

- **GitHub:** [github.com/srpatcha/eVera](https://github.com/srpatcha/eVera)
- **Releases:** [github.com/srpatcha/eVera/releases](https://github.com/srpatcha/eVera/releases)
- **Documentation:** [docs/index.md](docs/index.md)
- **API Reference:** [docs/api_reference.md](docs/api_reference.md)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

---

## Version History

| Version | Date | Highlights |
|---------|------|-----------|
| **0.8.0** | 2026-04-22 | Rebrand eSri → eVera, unified versioning, CI/CD overhaul |
| **0.7.0** | 2026-04-22 | Office automation: Jira, Work Pilot, Meeting, Codebase Indexer |
| **0.6.0** | 2026-04-21 | Vision monitor, voice server, admin ops, setup wizards, mobile, 6 new agents |
| **0.5.1** | 2026-04-20 | Content creator, finance agent, email management, scheduler |
| **0.5.0** | 2026-04-19 | Standalone desktop app, mobile app, 12 new system tools, docs, CI/CD |
| 0.4.1 | 2026-04-18 | 200+ tests, self-recovery, verify script |
| 0.4.0 | 2026-04-18 | Multi-agent crews, workflows, RBAC, Git agent, plugins |
| 0.3.1 | 2026-04-17 | Security hardening, encrypted credentials |
| 0.3.0 | 2026-04-17 | Browser agent, stock trading, screen vision |
| 0.2.0 | 2026-04-17 | Animated face, always-listening, buddy personality |
| 0.1.0 | 2026-04-16 | Initial release: 7 agents, LangGraph pipeline |

---

<p align="center">
  <b>Built with ❤️ by Srikanth Patchava</b><br>
  <i>eVera — Your AI assistant that actually does things.</i>
</p>
