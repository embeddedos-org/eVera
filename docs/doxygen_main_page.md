# eVera — Voice-First Multi-Agent AI Assistant {#mainpage}

## Abstract

**eVera** (pronounced "ee-VOH-kah") is an open-source, voice-first multi-agent AI assistant designed to be a single unified interface for controlling your entire digital life. Built on a LangGraph pipeline with 10+ specialized agents, 90+ tools, and a 4-layer memory system, eVera can open applications, automate your desktop, browse the web, trade stocks, manage your calendar, control smart home devices, and hold natural conversations — all triggered by voice or text. It ships as a standalone desktop app for Windows, macOS, and Linux.

---

## Introduction

### The Problem

Modern users juggle dozens of apps and interfaces daily — calendar, email, browser, file manager, terminal, smart home dashboard, trading platform. Each requires context switching, manual interaction, and cognitive overhead. Voice assistants like Siri and Alexa handle simple queries but lack deep system control, multi-step reasoning, and extensibility.

### The Solution

eVera provides a **single AI buddy** that understands natural language and routes requests to the right specialized agent. Whether you say "Open Chrome and go to GitHub" or "Buy 10 shares of Apple," eVera classifies intent, checks safety policies, selects the appropriate agent, and executes the action — all through a 4-tier LLM routing system that balances cost and capability.

### Target Users

- **Power users** who want voice-driven PC automation
- **Developers** looking for an extensible agent framework
- **Traders** needing hands-free market monitoring and execution
- **Anyone** who wants a smart, always-available AI companion

---

## Architecture Overview

eVera follows a modular, layered architecture:

1. **Electron Desktop Shell** — Frameless window with system tray, global shortcuts, and splash screen
2. **Web UI** — Glassmorphism design with animated face, waveform visualizer, chat, and live agent dashboard
3. **FastAPI Backend** — REST + WebSocket + SSE endpoints for all interactions
4. **LangGraph Pipeline** — State graph processing: `enrich → classify → safety → [tier0 | agent | confirm] → store → synthesize`
5. **10 Specialized Agents** — Each with dedicated tools and system prompts
6. **4-Layer Memory Vault** — Working (conversation), Episodic (FAISS vectors), Semantic (user facts), Secure (Fernet encryption)
7. **Safety Engine** — Policy-based action approval, PII detection, path sandboxing, command blocking
8. **Provider Manager** — Multi-LLM support via litellm: Ollama (local), OpenAI, Google Gemini

See `docs/architecture.md` and `docs/diagrams.md` for detailed component diagrams.

---

## Module Index

| Package | Description |
|---------|-------------|
| `vera.core` | VeraBrain singleton — orchestrates all components |
| `vera.app` | FastAPI application factory with REST/WebSocket endpoints |
| `vera.brain.graph` | LangGraph StateGraph processing pipeline |
| `vera.brain.router` | Tier-based intent classification (Regex → LLM → Keywords) |
| `vera.brain.supervisor` | SupervisorAgent for LLM-based classification |
| `vera.brain.agents` | All 10+ agent implementations |
| `vera.brain.agents.base` | BaseAgent abstract class and Tool dataclass |
| `vera.brain.agents.operator` | OperatorAgent — 20 PC automation tools |
| `vera.brain.agents.companion` | CompanionAgent — conversation and emotional support |
| `vera.brain.agents.browser` | BrowserAgent — Playwright web automation |
| `vera.brain.agents.income` | IncomeAgent — stock trading and market monitoring |
| `vera.brain.agents.coder` | CoderAgent — file read/write/edit and VS Code |
| `vera.brain.agents.git_agent` | GitAgent — git operations and AI code review |
| `vera.brain.agents.researcher` | ResearcherAgent — web search and summarization |
| `vera.brain.agents.writer` | WriterAgent — drafting and editing text |
| `vera.brain.agents.life_manager` | LifeManagerAgent — calendar, reminders, email |
| `vera.brain.agents.home_controller` | HomeControllerAgent — IoT device control |
| `vera.brain.agents.vision` | Screen capture and AI vision analysis tools |
| `vera.brain.crew` | Multi-agent crew collaboration (sequential, parallel, hierarchical, debate) |
| `vera.brain.workflow` | n8n-style JSON workflow engine |
| `vera.brain.plugins` | Plugin auto-discovery from `plugins/` directory |
| `vera.brain.language` | Language detection and spell correction |
| `vera.brain.state` | VeraState TypedDict definition |
| `vera.memory.vault` | MemoryVault facade over all memory layers |
| `vera.memory.working` | WorkingMemory — conversation context buffer |
| `vera.memory.episodic` | EpisodicMemory — FAISS vector search |
| `vera.memory.semantic` | SemanticMemory — key-value user facts |
| `vera.memory.secure` | SecureVault — Fernet-encrypted credential storage |
| `vera.safety.policy` | PolicyService — action approval rules engine |
| `vera.safety.privacy` | PrivacyGuard — PII detection and anonymization |
| `vera.providers.manager` | ProviderManager — multi-LLM completion with fallback |
| `vera.providers.models` | ModelTier enum and LLM response models |
| `vera.events.bus` | EventBus — SSE event streaming and agent status queue |
| `vera.scheduler` | ProactiveScheduler — reminders, alerts, morning briefing |
| `vera.messaging` | Slack, Discord, Telegram webhook handlers |
| `vera.rbac` | Role-based access control and audit logging |
| `vera.action.executor` | Action execution utilities |
| `vera.action.tts` | Text-to-speech output |
| `vera.perception.stt` | Speech-to-text (faster-whisper) |
| `vera.perception.vad` | Voice Activity Detection |
| `vera.perception.audio_stream` | Audio stream capture |
| `config` | Pydantic Settings with environment variable loading |

---

## Getting Started

### Desktop App (Recommended)

Download the installer for your platform from the [Releases page](https://github.com/patchava-sr/eVera/releases/latest):

| Platform | File | Install |
|----------|------|---------|
| Windows | `Vera-Setup.exe` | Run the installer |
| macOS | `Vera.dmg` | Open DMG → drag to Applications |
| Linux | `Vera.AppImage` | `chmod +x Vera-*.AppImage && ./Vera-*.AppImage` |

### From Source

```bash
git clone https://github.com/patchava-sr/eVera.git && cd eVera
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # Add your API keys
python main.py --mode server                         # Open http://localhost:8000
```

### Configuration

Copy `.env.example` to `.env` and set your API keys:

```
VERA_LLM_OPENAI_API_KEY=sk-...
VERA_LLM_GEMINI_API_KEY=...
VERA_SERVER_API_KEY=my-secret-key
```

See `docs/configuration.md` for all environment variables.

---

## Usage Examples

### 1. Casual Conversation
```
User: "Hey Vera, how are you?"
Vera: "I'm doing great, buddy! 😊 What's on your mind today?"
```

### 2. System Control
```
User: "Open Chrome and go to GitHub"
Vera: "Done! ✅ Opening Chrome for you! 🚀"
```

### 3. Stock Trading
```
User: "What's Apple's stock price?"
Vera: "AAPL is at $187.50 (↑2.3% today) 📈"
```

### 4. Smart Home
```
User: "Turn on the living room lights and set thermostat to 72"
Vera: "Done! Lights on and thermostat set to 72°F 🏠"
```

### 5. Voice-Triggered Automation
```
User: "Click at 500, 300 then press Ctrl+C"
Vera: "Clicked at (500, 300) and pressed Ctrl+C! ✅"
```

---

## Security Model

eVera implements defense-in-depth security:

- **API Authentication** — Bearer token or query parameter API key on all endpoints
- **Safety Policy Engine** — Per-agent, per-tool rules: ALLOW / CONFIRM / DENY
- **PII Detection** — Automatic redaction of emails, phone numbers, SSNs, credit cards
- **Path Sandboxing** — File operations restricted to home directory; `.ssh`, `.env`, `.aws` blocked
- **Command Blocking** — 30+ dangerous shell patterns blocked (`rm -rf`, `curl|bash`, etc.)
- **Encrypted Storage** — Fernet encryption for browser credentials and sensitive data
- **Trade Confirmation** — Real broker trades require explicit user approval

See `docs/security.md` for the complete security documentation.

---

## References

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Electron Documentation](https://www.electronjs.org/docs)
- [PyInstaller Documentation](https://pyinstaller.org/)
- [litellm Documentation](https://docs.litellm.ai/)
- [FAISS (Facebook AI Similarity Search)](https://github.com/facebookresearch/faiss)
- [Playwright Documentation](https://playwright.dev/python/)
- [pyautogui Documentation](https://pyautogui.readthedocs.io/)
