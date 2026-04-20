# 🔧 Development Guide

## Prerequisites

| Tool | Version | Required For |
|------|---------|-------------|
| Python | 3.11+ | Backend |
| Node.js | 18+ | Electron app |
| Git | 2.30+ | Version control |
| Ollama | Latest | Local LLM (optional) |

---

## Project Structure

```
eVoca/
├── config.py               # Pydantic Settings (env vars)
├── main.py                 # Entry point (server/desktop modes)
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata
├── build_backend.py        # PyInstaller build script
├── verify.py               # Pre-push verification (130+ checks)
├── voca/
│   ├── core.py             # VocaBrain singleton orchestrator
│   ├── app.py              # FastAPI application factory
│   ├── brain/
│   │   ├── graph.py        # LangGraph StateGraph pipeline
│   │   ├── router.py       # Tier-based intent routing
│   │   ├── supervisor.py   # LLM-based classification
│   │   ├── state.py        # VocaState TypedDict
│   │   ├── crew.py         # Multi-agent crew collaboration
│   │   ├── workflow.py     # n8n-style workflow engine
│   │   ├── language.py     # Language detection + spell correction
│   │   ├── plugins.py      # Plugin auto-discovery
│   │   └── agents/
│   │       ├── base.py     # BaseAgent + Tool classes
│   │       ├── companion.py
│   │       ├── operator.py
│   │       ├── browser.py
│   │       ├── researcher.py
│   │       ├── writer.py
│   │       ├── life_manager.py
│   │       ├── home_controller.py
│   │       ├── income.py
│   │       ├── brokers.py
│   │       ├── coder.py
│   │       ├── git_agent.py
│   │       └── vision.py
│   ├── memory/
│   │   ├── vault.py        # MemoryVault facade
│   │   ├── working.py      # Conversation buffer
│   │   ├── episodic.py     # FAISS vector search
│   │   ├── semantic.py     # Key-value facts
│   │   └── secure.py       # Fernet encryption
│   ├── safety/
│   │   ├── policy.py       # Action approval rules
│   │   └── privacy.py      # PII detection
│   ├── providers/
│   │   ├── manager.py      # Multi-LLM provider
│   │   └── models.py       # ModelTier enum
│   ├── events/
│   │   └── bus.py          # EventBus + agent status queue
│   ├── perception/
│   │   ├── stt.py          # Speech-to-text
│   │   ├── vad.py          # Voice activity detection
│   │   └── audio_stream.py # Mic capture
│   ├── action/
│   │   ├── executor.py     # Action execution
│   │   └── tts.py          # Text-to-speech
│   ├── static/             # Web UI files
│   ├── scheduler.py        # Proactive alerts
│   ├── messaging.py        # Slack/Discord/Telegram
│   └── rbac.py             # User management
├── electron/
│   ├── main.js             # Electron main process
│   ├── preload.js          # Context bridge
│   ├── build.js            # Packaging script
│   └── package.json        # Electron deps
├── plugins/
│   └── _example_plugin.py  # Plugin template
├── tests/                  # 200+ test cases
└── docs/                   # Documentation
```

---

## Building from Source

### Backend Only

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure API keys
python main.py --mode server
```

### Electron App (Dev Mode)

```bash
# Terminal 1: Backend
python main.py --mode server

# Terminal 2: Electron
cd electron && npm install && npm start
```

### Build Standalone Installer

```bash
# 1. Bundle Python backend
python build_backend.py

# 2. Package Electron app
cd electron
node build.js win    # Windows
node build.js mac    # macOS
node build.js linux  # Linux
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=voca --cov-report=term-missing

# Specific test file
pytest tests/test_agents.py -v

# Pre-push verification (all checks)
python verify.py
```

### Test Categories

| File | Tests | Focus |
|------|-------|-------|
| `test_foundation.py` | 13 | Core components, singleton, config |
| `test_security.py` | 38 | Auth bypass, data leaks, injection |
| `test_sanity.py` | 19 | Imports, agent basics, memory |
| `test_performance.py` | 10 | Latency benchmarks |
| `test_agents.py` | 15+ | Agent registration, tool counts |
| `test_api.py` | 10+ | REST endpoint testing |
| `test_router.py` | 10+ | Intent classification |
| `test_memory.py` | 10+ | Memory layer operations |
| `test_safety.py` | 10+ | Policy engine rules |
| `test_graph.py` | 5+ | Pipeline flow |
| `test_rbac.py` | 11 | User management, roles |
| `test_workflow.py` | 5 | Workflow engine |
| `test_plugins.py` | 4 | Plugin discovery |
| `test_scheduler.py` | 5 | Proactive scheduling |

---

## Linting

```bash
ruff check .          # Check for issues
ruff format .         # Auto-format
ruff check . --fix    # Auto-fix issues
```

---

## Creating a Plugin Agent

1. Create a file in the `plugins/` directory (e.g., `plugins/my_agent.py`)
2. Define a class extending `BaseAgent`
3. Set `name`, `description`, `tier`, and implement `_setup_tools()`
4. The agent is auto-discovered and registered at startup

```python
from voca.brain.agents.base import BaseAgent, Tool
from voca.providers.models import ModelTier

class MyTool(Tool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="Does something useful",
            parameters={"input": {"type": "str", "description": "Input text"}},
        )

    async def execute(self, **kwargs):
        return {"status": "success", "result": kwargs.get("input", "")}

class MyAgent(BaseAgent):
    name = "my_agent"
    description = "My custom agent"
    tier = ModelTier.EXECUTOR
    system_prompt = "You are a helpful custom agent."

    def _setup_tools(self):
        self._tools = [MyTool()]
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing`
3. Make changes and add tests
4. Run verification: `python verify.py`
5. Commit: `git commit -m "Add amazing feature"`
6. Push and open a Pull Request

### Code Style

- Follow PEP 8 with `ruff` enforcement
- Use type hints everywhere
- Add docstrings to all public classes and functions
- Use Doxygen-compatible `@param` / `@return` tags in docstrings

---

## Generating Documentation

### HTML (Doxygen)

```bash
pip install -r docs/requirements.txt
cd docs && doxygen Doxyfile
# Open docs/html/index.html
```

### PDF (Doxygen + LaTeX)

```bash
cd docs && doxygen Doxyfile
cd latex && make
# Output: docs/latex/refman.pdf
```

### Diagram Images

```bash
npm install -g @mermaid-js/mermaid-cli
python docs/generate_diagrams.py
# Output: docs/images/*.png
```
