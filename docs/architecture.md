# 🏗️ Architecture

## Overview

eVoca is built as a **layered, modular system** with clear separation of concerns:

```
Electron Shell → Web UI → FastAPI Backend → LangGraph Pipeline → Agents → LLM Providers
                                                    ↕                ↕
                                              Memory Vault    Safety Engine
```

See [diagrams.md](diagrams.md) for interactive Mermaid diagrams of each component.

---

## Layer 1: Desktop Shell (Electron)

**Directory:** `electron/`

The Electron shell provides a native desktop experience:

- **Frameless window** with custom title bar
- **System tray** icon with context menu (Show/Hide, Always on Top, Start on Boot, Quit)
- **Global shortcut** `Ctrl+Shift+V` to toggle window from anywhere
- **Single-instance lock** prevents multiple windows
- **Auto-starts** the Python backend as a child process
- **Splash screen** shown while backend initializes
- **Desktop notifications** for proactive scheduler alerts

**Key files:**
- `electron/main.js` — Main process: window, tray, shortcuts, backend lifecycle
- `electron/preload.js` — Secure context bridge for IPC
- `electron/build.js` — Packaging script for electron-builder
- `electron/package.json` — Dependencies and build configuration

---

## Layer 2: Web UI

**Directory:** `voca/static/`

Glassmorphism-themed web UI built with vanilla JavaScript:

- **Animated face** (`face.js`) — Canvas-based with 8 expressions, blinking, bobbing, mouth sync
- **Audio waveform** (`waveform.js`) — Web Audio API visualizer synced to microphone
- **Voice listener** (`listener.js`) — 3 modes: Push-to-Talk, Wake Word, Always On
- **Chat interface** (`app.js`) — Message bubbles with spring animations
- **Agent dashboard** (`agents-view.js`) — 3 visualization modes:
  - Card View — Glass-effect cards with real-time status
  - Timeline View — Vertical timeline with timestamps
  - Constellation View — Canvas network graph with animated particles

---

## Layer 3: FastAPI Backend

**File:** `voca/app.py`

REST + WebSocket + SSE server handling all client interactions:

| Protocol | Path | Purpose |
|----------|------|---------|
| REST | `/chat` | Send transcript, get response |
| REST | `/agents` | List all agents |
| REST | `/status` | System status + memory stats |
| REST | `/health` | Health check |
| REST | `/memory/facts` | Get/set semantic facts |
| REST | `/crew` | Run multi-agent crew |
| REST | `/workflows` | CRUD + execute workflows |
| REST | `/admin/users` | RBAC user management |
| WebSocket | `/ws` | Real-time bidirectional chat |
| SSE | `/events/stream` | Live event stream |
| SSE | `/agents/stream` | Real-time agent status |
| Webhook | `/webhook/*` | TradingView, Slack, Discord, Telegram |

---

## Layer 4: LangGraph Pipeline

**File:** `voca/brain/graph.py`

The heart of eVoca — a LangGraph `StateGraph` with 7 nodes:

1. **enrich_memory** — Query memory layers, correct spelling, detect language, extract user name
2. **classify** — Route to agent via TierRouter (regex → local LLM → cloud LLM → keywords)
3. **safety_check** — Privacy guard (PII anonymization) + policy check (ALLOW/CONFIRM/DENY)
4. **tier0_handler** — Instant regex-based responses (time, date, greeting) — no LLM
5. **agent** — Execute selected agent with tool calling loop
6. **confirmation** — Ask user for approval on sensitive actions
7. **store_memory** — Persist interaction in working + episodic memory
8. **synthesize** — Prepare final response

Conditional routing after `safety_check` determines the path based on tier, safety decision, and confirmation requirement.

---

## Tier-Based LLM Routing

**File:** `voca/brain/router.py`

| Tier | Name | Engine | Cost | Example |
|------|------|--------|------|---------|
| 0 | Reflex | Regex patterns | **Free** | "What time is it?" |
| 1 | Executor | Ollama (local) | **Free** | "Turn off the lights" |
| 2 | Specialist | GPT-4o-mini / Gemini Flash | $ | "Draft an email to John" |
| 3 | Strategist | GPT-4o | $$ | "Analyze my portfolio risk" |

---

## Agent System

**Directory:** `voca/brain/agents/`

All agents extend `BaseAgent` and register `Tool` instances:

- **BaseAgent** provides: LLM tool calling loop, regex fallback, mood extraction, offline responses, system prompt construction
- **Tool** provides: parameter schema, execute method, OpenAI function calling schema
- **AGENT_REGISTRY** maps agent names to instances for lazy initialization

---

## Memory System

**Directory:** `voca/memory/`

| Layer | Class | Storage | Purpose |
|-------|-------|---------|---------|
| Working | `WorkingMemory` | In-memory list | Last 20 conversation turns |
| Episodic | `EpisodicMemory` | FAISS index | Similarity search over past interactions |
| Semantic | `SemanticMemory` | JSON file | Key-value user facts (name, preferences) |
| Secure | `SecureVault` | Encrypted file | Fernet-encrypted credentials |

---

## Safety System

**Directory:** `voca/safety/`

- **PolicyService** (`policy.py`) — Rule-based action approval using `agent.tool` patterns
- **PrivacyGuard** (`privacy.py`) — PII detection (email, phone, SSN, credit card) and anonymization
- **Path sandboxing** — File operations restricted to home directory
- **Command blocking** — 30+ dangerous shell patterns blocked
- **Trade confirmation** — Real broker trades require explicit user approval

---

## Provider System

**Directory:** `voca/providers/`

- **ProviderManager** (`manager.py`) — Multi-LLM completion with automatic fallback
- **ModelTier** enum — REFLEX (0), EXECUTOR (1), SPECIALIST (2), STRATEGIST (3)
- Supports: Ollama (local), OpenAI, Google Gemini via `litellm`

---

## Event System

**Directory:** `voca/events/`

- **EventBus** (`bus.py`) — Central event dispatcher with SSE streaming
- **Agent status queue** — Real-time agent working/done events for dashboard visualization

---

## Proactive Scheduler

**File:** `voca/scheduler.py`

Background loops running on intervals:
- Reminder firing (check every 30s)
- Calendar alerts (15 min warning)
- Stock price alerts (5%+ moves)
- Daily morning briefing
