# eVoca — Voice-First Multi-Agent AI Assistant {#mainpage}

## Abstract

**eVoca** (pronounced "ee-VOH-kah") is an open-source, voice-first multi-agent AI assistant designed to be a single unified interface for controlling your entire digital life. Built on a LangGraph pipeline with 10+ specialized agents, 90+ tools, and a 4-layer memory system, eVoca can open applications, automate your desktop, browse the web, trade stocks, manage your calendar, control smart home devices, and hold natural conversations — all triggered by voice or text. It ships as a standalone desktop app for Windows, macOS, and Linux.

---

## Introduction

### The Problem

Modern users juggle dozens of apps and interfaces daily — calendar, email, browser, file manager, terminal, smart home dashboard, trading platform. Each requires context switching, manual interaction, and cognitive overhead. Voice assistants like Siri and Alexa handle simple queries but lack deep system control, multi-step reasoning, and extensibility.

### The Solution

eVoca provides a **single AI buddy** that understands natural language and routes requests to the right specialized agent. Whether you say "Open Chrome and go to GitHub" or "Buy 10 shares of Apple," eVoca classifies intent, checks safety policies, selects the appropriate agent, and executes the action — all through a 4-tier LLM routing system that balances cost and capability.

### Target Users

- **Power users** who want voice-driven PC automation
- **Developers** looking for an extensible agent framework
- **Traders** needing hands-free market monitoring and execution
- **Anyone** who wants a smart, always-available AI companion

---

## Architecture Overview

eVoca follows a modular, layered architecture:

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
| `voca.core` | VocaBrain singleton — orchestrates all components |
| `voca.app` | FastAPI application factory with REST/WebSocket endpoints |
| `voca.brain.graph` | LangGraph StateGraph processing pipeline |
| `voca.brain.router` | Tier-based intent classification (Regex → LLM → Keywords) |
| `voca.brain.supervisor` | SupervisorAgent for LLM-based classification |
| `voca.brain.agents` | All 10+ agent implementations |
| `voca.brain.agents.base` | BaseAgent abstract class and Tool dataclass |
| `voca.brain.agents.operator` | OperatorAgent — 20 PC automation tools |
| `voca.brain.agents.companion` | CompanionAgent — conversation and emotional support |
| `voca.brain.agents.browser` | BrowserAgent — Playwright web automation |
| `voca.brain.agents.income` | IncomeAgent — stock trading and market monitoring |
| `voca.brain.agents.coder` | CoderAgent — file read/write/edit and VS Code |
| `voca.brain.agents.git_agent` | GitAgent — git operations and AI code review |
| `voca.brain.agents.researcher` | ResearcherAgent — web search and summarization |
| `voca.brain.agents.writer` | WriterAgent — drafting and editing text |
| `voca.brain.agents.life_manager` | LifeManagerAgent — calendar, reminders, email |
| `voca.brain.agents.home_controller` | HomeControllerAgent — IoT device control |
| `voca.brain.agents.vision` | Screen capture and AI vision analysis tools |
| `voca.brain.crew` | Multi-agent crew collaboration (sequential, parallel, hierarchical, debate) |
| `voca.brain.workflow` | n8n-style JSON workflow engine |
| `voca.brain.plugins` | Plugin auto-discovery from `plugins/` directory |
| `voca.brain.language` | Language detection and spell correction |
| `voca.brain.state` | VocaState TypedDict definition |
| `voca.memory.vault` | MemoryVault facade over all memory layers |
| `voca.memory.working` | WorkingMemory — conversation context buffer |
| `voca.memory.episodic` | EpisodicMemory — FAISS vector search |
| `voca.memory.semantic` | SemanticMemory — key-value user facts |
| `voca.memory.secure` | SecureVault — Fernet-encrypted credential storage |
| `voca.safety.policy` | PolicyService — action approval rules engine |
| `voca.safety.privacy` | PrivacyGuard — PII detection and anonymization |
| `voca.providers.manager` | ProviderManager — multi-LLM completion with fallback |
| `voca.providers.models` | ModelTier enum and LLM response models |
| `voca.events.bus` | EventBus — SSE event streaming and agent status queue |
| `voca.scheduler` | ProactiveScheduler — reminders, alerts, morning briefing |
| `voca.messaging` | Slack, Discord, Telegram webhook handlers |
| `voca.rbac` | Role-based access control and audit logging |
| `voca.action.executor` | Action execution utilities |
| `voca.action.tts` | Text-to-speech output |
| `voca.perception.stt` | Speech-to-text (faster-whisper) |
| `voca.perception.vad` | Voice Activity Detection |
| `voca.perception.audio_stream` | Audio stream capture |
| `config` | Pydantic Settings with environment variable loading |

---

## Getting Started

### Desktop App (Recommended)

Download the installer for your platform from the [Releases page](https://github.com/patchava-sr/eVoca/releases/latest):

| Platform | File | Install |
|----------|------|---------|
| Windows | `Voca-Setup.exe` | Run the installer |
| macOS | `Voca.dmg` | Open DMG → drag to Applications |
| Linux | `Voca.AppImage` | `chmod +x Voca-*.AppImage && ./Voca-*.AppImage` |

### From Source

```bash
git clone https://github.com/patchava-sr/eVoca.git && cd eVoca
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # Add your API keys
python main.py --mode server                         # Open http://localhost:8000
```

### Configuration

Copy `.env.example` to `.env` and set your API keys:

```
VOCA_LLM_OPENAI_API_KEY=sk-...
VOCA_LLM_GEMINI_API_KEY=...
VOCA_SERVER_API_KEY=my-secret-key
```

See `docs/configuration.md` for all environment variables.

---

## Usage Examples

### 1. Casual Conversation
```
User: "Hey Voca, how are you?"
Voca: "I'm doing great, buddy! 😊 What's on your mind today?"
```

### 2. System Control
```
User: "Open Chrome and go to GitHub"
Voca: "Done! ✅ Opening Chrome for you! 🚀"
```

### 3. Stock Trading
```
User: "What's Apple's stock price?"
Voca: "AAPL is at $187.50 (↑2.3% today) 📈"
```

### 4. Smart Home
```
User: "Turn on the living room lights and set thermostat to 72"
Voca: "Done! Lights on and thermostat set to 72°F 🏠"
```

### 5. Voice-Triggered Automation
```
User: "Click at 500, 300 then press Ctrl+C"
Voca: "Clicked at (500, 300) and pressed Ctrl+C! ✅"
```

---

## Security Model

eVoca implements defense-in-depth security:

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
