# 🚀 eVera v0.9.0 — Jarvis-like AI Copilot

The biggest release yet! eVera transforms from a basic assistant into a full **Jarvis-like AI copilot** with multi-model intelligence, personal knowledge base, Chrome extension, and autonomous web automation.

## ⬇️ Download

| File | Description |
|------|-------------|
| **Vera Setup 0.9.0.exe** | Windows installer (includes everything — no Python/Node needed) |

## ✨ What's New

### 🤖 Multi-Model Routing (30+ Models across 9 Providers)
- **9 providers**: OpenAI, Anthropic (Claude), Google Gemini, Groq, DeepSeek, Mistral, Together AI, Perplexity, Ollama
- **Intelligent auto-routing**: Code → DeepSeek, Creative → Claude, Fast → Groq, Vision → GPT-4o, Web Search → Perplexity
- **Model selector** in the Web UI header — pick any model or let eVera choose
- **Provider health checks** — see which providers are online
- **Per-model metadata**: context window, vision support, tool support, cost tracking, speed tier

### 📚 Personal Knowledge Base (RAG)
- **Upload documents**: PDF, DOCX, TXT, Markdown, CSV (up to 50MB)
- **Smart chunking**: 512-token chunks with 64-token overlap for optimal retrieval
- **Vector search**: sentence-transformers + FAISS for fast similarity search
- **RAG answers with citations**: Answers reference which document and chunk the info came from
- **Persistent storage**: Documents survive server restarts

### 🌐 Chrome Extension
- **Text selection toolbar**: Select text on any webpage → floating toolbar with 5 AI actions
- **Actions**: 📝 Summarize, 🌐 Translate, 💡 Explain, ✏️ Fix Grammar, 🤖 Ask eVera
- **Right-click context menus** for all actions
- **Side Panel chat**: Full chat interface in Chrome's sidebar
- **Settings page**: Configure server URL, default model, toggle overlay
- **Glassmorphism UI** matching the desktop app

### 🕷️ Web Automation Agent
- **Natural language → browser automation**: "Search Google for Python tutorials" → plans and executes multi-step sequences
- **LLM-powered task planner**: Decomposes intent into navigate/click/type/scroll steps
- **Screenshot verification**: Takes screenshots after each step to verify success
- **Auto-retry & re-planning**: Falls back to alternative selectors or re-plans on failure
- **Web scraper**: Extract structured data from any page with a JSON schema

### 🏗️ Fixed Windows Desktop App
- Backend now bundles correctly with PyInstaller (20+ hidden imports added)
- `.env` resolution works in frozen exe mode (`_MEIPASS` + `%APPDATA%`)
- No more duplicate browser window opening in Electron
- `waitForBackend()` properly rejects on timeout with error dialog
- Data directories auto-created on first run
- One-click `scripts/setup.ps1` setup script

## 📊 By the Numbers

| Metric | Value |
|--------|-------|
| Files changed | 38 |
| Lines added | 8,294 |
| New files | 24 |
| LLM providers | 9 |
| Models supported | 30+ |
| Agents | 20 |
| Extension files | 10 |
| Test coverage | 21/21 passing |

## 🛠️ Setup

### Quick Start (from source)
```powershell
git clone https://github.com/srpatcha/eVera.git
cd eVera
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
python main.py --mode server
# Open http://localhost:8000 in Chrome
```

### Desktop App
```powershell
cd electron
npm start
```

### Add API Keys
Edit `.env` and add your provider keys:
```
VERA_LLM_OPENAI_API_KEY=sk-...
VERA_LLM_ANTHROPIC_API_KEY=sk-ant-...
VERA_LLM_GROQ_API_KEY=gsk_...
VERA_LLM_DEEPSEEK_API_KEY=sk-...
```

### Chrome Extension
1. Open `chrome://extensions`
2. Enable Developer Mode
3. Click "Load unpacked" → select `extension/` folder

## 🔧 API Endpoints (New)

| Endpoint | Description |
|----------|-------------|
| `GET /models` | List 30+ models with availability status |
| `POST /models/select` | Auto-pick best model for a task type |
| `GET /models/health` | Provider health check |
| `POST /knowledge/upload` | Upload document to knowledge base |
| `GET /knowledge/documents` | List indexed documents |
| `POST /knowledge/query` | RAG query with citations |
| `POST /extension/summarize` | Summarize text |
| `POST /extension/translate` | Translate text |
| `POST /extension/explain` | Explain text |
| `POST /extension/grammar` | Fix grammar |
| `POST /extension/rewrite` | Rewrite text |
| `POST /automation/plan` | Plan browser automation |
| `POST /automation/execute` | Execute browser automation |
| `POST /automation/scrape` | Scrape structured data |

---

**Full Changelog**: https://github.com/srpatcha/eVera/compare/v0.6.0...v0.9.0
