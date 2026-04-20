# eVoca Architecture Diagrams

All diagrams are written in [Mermaid](https://mermaid.js.org/) syntax and can be rendered in GitHub, VS Code (with Mermaid extension), or exported to PNG via `mmdc` (mermaid-cli).

---

## 1. System Architecture

High-level component diagram showing how the Electron shell, Web UI, FastAPI backend, LangGraph pipeline, and subsystems connect.

```mermaid
graph TB
    subgraph Electron["📱 Electron Desktop Shell"]
        EMain["main.js<br/>Frameless window<br/>System tray<br/>Global shortcuts"]
        Preload["preload.js<br/>Context bridge"]
    end

    subgraph WebUI["🎭 Web UI (Glassmorphism)"]
        Face["Animated Face<br/>8 expressions"]
        Wave["Waveform Visualizer"]
        Chat["Chat Interface"]
        AgentDash["Agent Dashboard<br/>Cards | Timeline | Graph"]
    end

    subgraph Backend["⚡ FastAPI Backend"]
        REST["REST API<br/>/chat, /agents, /status"]
        WS["WebSocket<br/>/ws"]
        SSE["SSE Streams<br/>/events/stream<br/>/agents/stream"]
        Webhooks["Webhooks<br/>TradingView, Slack<br/>Discord, Telegram"]
    end

    subgraph Brain["🧠 VocaBrain (LangGraph)"]
        Pipeline["StateGraph Pipeline<br/>enrich → classify → safety<br/>→ agent → store → synthesize"]

        subgraph Agents["🤖 10 Agents (90+ tools)"]
            Companion["💬 Companion"]
            Operator["💻 Operator"]
            Browser["🌐 Browser"]
            Researcher["🔍 Researcher"]
            Writer["✍️ Writer"]
            LifeMgr["📅 Life Manager"]
            HomeCtr["🏠 Home Controller"]
            Income["📈 Income"]
            Coder["💻 Coder"]
            Git["📦 Git"]
        end
    end

    subgraph CrossCutting["Cross-Cutting Concerns"]
        Memory["🧠 Memory Vault<br/>4 layers"]
        Safety["🛡️ Safety Engine<br/>Policy + PII"]
        Providers["🔌 Provider Manager<br/>Ollama / OpenAI / Gemini"]
        EventBus["📡 Event Bus<br/>SSE streaming"]
        Scheduler["⏰ Proactive Scheduler"]
    end

    EMain --> WebUI
    WebUI -->|localhost:8000| Backend
    REST --> Pipeline
    WS --> Pipeline
    Pipeline --> Agents
    Pipeline --> Memory
    Pipeline --> Safety
    Pipeline --> Providers
    Agents --> Providers
    EventBus --> SSE
    Scheduler --> WS
```

---

## 2. LangGraph Pipeline Flow

Flowchart showing the complete processing pipeline from user input to final response.

```mermaid
flowchart TD
    Start([User Input]) --> Enrich["🧠 enrich_memory<br/>Query memory layers<br/>Spell correction<br/>Language detection<br/>Name extraction"]
    Enrich --> Classify["🎯 classify<br/>Tier 0: Regex match<br/>Tier 1: Local LLM<br/>Tier 2: Cloud LLM<br/>Fallback: Keywords"]
    Classify --> Safety["🛡️ safety_check<br/>Privacy guard<br/>PII anonymization<br/>Policy evaluation"]

    Safety -->|DENY| StoreD["💾 store_memory"]
    Safety -->|CONFIRM| Confirm["🤔 confirmation<br/>Ask user yes/no<br/>Store pending action"]
    Safety -->|Tier 0| Tier0["⚡ tier0_handler<br/>Regex template response<br/>No LLM needed"]
    Safety -->|ALLOW| Agent["🤖 agent<br/>Execute selected agent<br/>Tool calling loop<br/>Up to 5 iterations"]

    Tier0 --> Store["💾 store_memory<br/>Working memory<br/>Episodic memory"]
    Agent --> Store
    Confirm --> Store
    StoreD --> Synth["✨ synthesize<br/>Prepare final response"]
    Store --> Synth
    Synth --> End([Response to User])
```

---

## 3. Agent Hierarchy

Class diagram showing the BaseAgent abstract class and all concrete agent implementations.

```mermaid
classDiagram
    class BaseAgent {
        <<abstract>>
        +name: str
        +description: str
        +tier: ModelTier
        +system_prompt: str
        +_tools: list~Tool~
        +run(state: VocaState) VocaState
        +respond_offline(state: VocaState) str
        #_setup_tools() void
        -_build_system_prompt(state) str
        -_extract_mood(text) str
    }

    class Tool {
        +name: str
        +description: str
        +parameters: dict
        +execute(**kwargs) dict
        +to_openai_schema() dict
    }

    class CompanionAgent {
        +tools: 4
        chat, joke, mood, activity
    }

    class OperatorAgent {
        +tools: 20
        apps, scripts, files, mouse
        keyboard, windows, processes
        system, services, network
        clipboard, notifications
    }

    class BrowserAgent {
        +tools: 11
        navigate, click, fill_form
        login, screenshot, extract
    }

    class ResearcherAgent {
        +tools: 4
        web_search, summarize
        papers, fact_check
    }

    class WriterAgent {
        +tools: 4
        draft, edit, format, translate
    }

    class LifeManagerAgent {
        +tools: 5
        calendar, reminders, todos
        email, events
    }

    class HomeControllerAgent {
        +tools: 6
        lights, thermostat, locks
        security, media, scenes
    }

    class IncomeAgent {
        +tools: 14
        prices, trading, portfolio
        Alpaca, IBKR, watchlist
    }

    class CoderAgent {
        +tools: 5
        read, write, edit files
        search code, VS Code
    }

    class GitAgent {
        +tools: 9
        status, diff, commit, push
        pull, branch, log, stash
        AI code review
    }

    BaseAgent <|-- CompanionAgent
    BaseAgent <|-- OperatorAgent
    BaseAgent <|-- BrowserAgent
    BaseAgent <|-- ResearcherAgent
    BaseAgent <|-- WriterAgent
    BaseAgent <|-- LifeManagerAgent
    BaseAgent <|-- HomeControllerAgent
    BaseAgent <|-- IncomeAgent
    BaseAgent <|-- CoderAgent
    BaseAgent <|-- GitAgent
    BaseAgent "1" --> "*" Tool : owns
```

---

## 4. Memory Architecture

Layer diagram showing the 4-layer memory system and data flow.

```mermaid
graph LR
    subgraph MemoryVault["🧠 Memory Vault (Facade)"]
        direction TB

        subgraph Working["Layer 1: Working Memory"]
            WM["Conversation Buffer<br/>Last 20 turns<br/>In-memory list"]
        end

        subgraph Episodic["Layer 2: Episodic Memory"]
            EM["FAISS Vector Index<br/>sentence-transformers embeddings<br/>Similarity search (top-k)"]
        end

        subgraph Semantic["Layer 3: Semantic Memory"]
            SM["Key-Value Store<br/>User facts (name, preferences)<br/>JSON persistence"]
        end

        subgraph Secure["Layer 4: Secure Vault"]
            SV["Fernet Encryption<br/>Browser credentials<br/>API keys & passwords"]
        end
    end

    Input["User Transcript"] -->|enrich()| Working
    Input -->|enrich()| Episodic
    Input -->|enrich()| Semantic

    Working -->|context| Pipeline["LangGraph Pipeline"]
    Episodic -->|relevant episodes| Pipeline
    Semantic -->|user facts| Pipeline

    Pipeline -->|store_interaction()| Working
    Pipeline -->|store_interaction()| Episodic
    Pipeline -->|remember_fact()| Semantic
```

---

## 5. Safety & Permission Flow

Decision tree showing how the safety engine evaluates actions.

```mermaid
flowchart TD
    Request["Agent Action Request<br/>(agent_name, tool_name)"] --> Specific{"Specific rule?<br/>agent.tool"}

    Specific -->|Yes| SpecAction["Apply rule action"]
    Specific -->|No| Wildcard{"Wildcard rule?<br/>agent.*"}

    Wildcard -->|Yes| WildAction["Apply wildcard action"]
    Wildcard -->|No| DeniedList{"In denied_actions<br/>list?"}

    DeniedList -->|Yes| DENY["🚫 DENY<br/>Action blocked<br/>Response: reason"]
    DeniedList -->|No| ConfirmList{"In confirm_actions<br/>list?"}

    ConfirmList -->|Yes| CONFIRM["🤔 CONFIRM<br/>Ask user yes/no<br/>Store pending action"]
    ConfirmList -->|No| AllowList{"In allowed_actions<br/>list?"}

    AllowList -->|Yes| ALLOW["✅ ALLOW<br/>Execute immediately"]
    AllowList -->|No| Default["🤔 Default: CONFIRM<br/>Unknown = require approval"]

    SpecAction -->|ALLOW| ALLOW
    SpecAction -->|CONFIRM| CONFIRM
    SpecAction -->|DENY| DENY

    WildAction -->|ALLOW| ALLOW
    WildAction -->|CONFIRM| CONFIRM
    WildAction -->|DENY| DENY

    CONFIRM -->|User says Yes| Execute["Execute Action"]
    CONFIRM -->|User says No| Cancel["Cancel & Notify"]
```

---

## 6. Standalone App Build Pipeline

Sequence diagram showing how the desktop app is built and packaged.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Py as PyInstaller
    participant EB as electron-builder
    participant CI as GitHub Actions

    Dev->>Py: python build_backend.py
    Note over Py: Bundle Python backend<br/>into single executable
    Py->>Py: Collect voca/, config.py, main.py
    Py->>Py: Include dependencies (fastapi, langgraph, etc.)
    Py-->>Dev: dist/voca-server.exe

    Dev->>EB: cd electron && node build.js [platform]
    Note over EB: Package Electron app<br/>with bundled backend
    EB->>EB: Copy voca-server.exe to resources
    EB->>EB: Build Electron app with electron-builder

    alt Windows
        EB-->>Dev: Voca-Setup.exe (NSIS installer)
    else macOS
        EB-->>Dev: Voca.dmg
    else Linux
        EB-->>Dev: Voca.AppImage + Voca.deb
    end

    CI->>CI: On push to main
    CI->>Py: Build backend (all platforms)
    CI->>EB: Package installer (all platforms)
    CI->>CI: Upload release artifacts
```

---

## 7. Tier-Based LLM Routing

Flowchart showing how user input is classified and routed through the tier system.

```mermaid
flowchart TD
    Input["User Transcript"] --> T0{"Tier 0<br/>Regex Match?"}

    T0 -->|"✅ Match<br/>(time, date, hello, bye)"| T0R["⚡ Instant Response<br/>No LLM • Free<br/>Template-based"]

    T0 -->|"❌ No match"| T1["Tier 1<br/>Local LLM (Ollama)"]

    T1 -->|"confidence ≥ 0.6"| T1R["🏠 Local Classification<br/>Free • Fast<br/>Ollama model"]

    T1 -->|"confidence < 0.6<br/>or failure"| T2["Tier 2<br/>Cloud LLM"]

    T2 -->|"success"| T2R["☁️ Cloud Classification<br/>GPT-4o-mini / Gemini Flash<br/>$ per request"]

    T2 -->|"failure"| TK["Tier K<br/>Keyword Fallback"]

    TK --> TKR["🔤 Offline Classification<br/>Regex patterns + word matching<br/>No LLM • Free"]

    T0R --> Execute["Execute Agent"]
    T1R --> Execute
    T2R --> Execute
    TKR --> Execute

    Execute --> Response["Response to User"]

    style T0R fill:#2d6a2d,color:#fff
    style T1R fill:#2d4a6a,color:#fff
    style T2R fill:#6a4a2d,color:#fff
    style TKR fill:#4a2d6a,color:#fff
```
