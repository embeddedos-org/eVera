# 🚀 Getting Started

## System Requirements

| Requirement | Minimum |
|-------------|---------|
| **OS** | Windows 10+, macOS 12+, Ubuntu 20.04+ |
| **Python** | 3.11+ (for development only) |
| **Node.js** | 18+ (for Electron development only) |
| **RAM** | 4 GB (8 GB recommended for local LLM) |
| **Disk** | 500 MB (2 GB with Ollama models) |

---

## Option 1: Desktop App (Recommended)

No Python or Node.js required — everything is bundled into a single installer.

### Download

| Platform | File | Install |
|----------|------|---------|
| **Windows** | [Voca-Setup.exe](https://github.com/patchava-sr/eVoca/releases/latest) | Run the installer |
| **macOS** | [Voca.dmg](https://github.com/patchava-sr/eVoca/releases/latest) | Open DMG → drag to Applications |
| **Linux** | [Voca.AppImage](https://github.com/patchava-sr/eVoca/releases/latest) | `chmod +x Voca-*.AppImage && ./Voca-*.AppImage` |

### First Launch

1. Launch the app — it will show a splash screen while the backend starts
2. The main window opens automatically at `localhost:8000`
3. Type or speak to start interacting with Voca

### Global Shortcut

Press `Ctrl+Shift+V` to toggle the Voca window from anywhere.

---

## Option 2: From Source (Developer)

### Clone and Install

```bash
git clone https://github.com/patchava-sr/eVoca.git
cd eVoca
python -m venv .venv

# Activate virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configure API Keys

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# Required: at least one LLM provider
VOCA_LLM_OPENAI_API_KEY=sk-your-key-here
VOCA_LLM_GEMINI_API_KEY=your-gemini-key

# Optional: local Ollama (free, no API key)
VOCA_LLM_OLLAMA_URL=http://localhost:11434
VOCA_LLM_OLLAMA_MODEL=llama3.2

# Optional: API security
VOCA_SERVER_API_KEY=my-secret-key
```

### Run

```bash
# Start the server
python main.py --mode server

# Open http://localhost:8000 in your browser
```

### Run with Electron (Dev Mode)

```bash
# Terminal 1: Start backend
python main.py --mode server

# Terminal 2: Start Electron
cd electron
npm install
npm start
```

---

## Configuration

See [Configuration Reference](configuration.md) for all environment variables.

### Key Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `VOCA_LLM_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `VOCA_LLM_OPENAI_API_KEY` | (none) | OpenAI API key |
| `VOCA_LLM_GEMINI_API_KEY` | (none) | Gemini API key |
| `VOCA_SERVER_HOST` | `127.0.0.1` | Server bind address |
| `VOCA_SERVER_PORT` | `8000` | Server port |
| `VOCA_SERVER_API_KEY` | (empty) | API authentication key |

---

## Next Steps

- [Architecture Overview](architecture.md) — Understand how eVoca works
- [Agents Reference](agents.md) — See all 10 agents and their tools
- [API Reference](api_reference.md) — REST and WebSocket endpoint docs
- [Development Guide](development.md) — Build from source and contribute
