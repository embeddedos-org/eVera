# eVera AI — VS Code Extension

Your personal AI agent inside VS Code. Powered by eVera — works **fully offline** with Ollama, on your LAN, or with cloud LLMs.

## Features

| Feature | Description |
|---|---|
| **Inline Chat** | Full chat sidebar — ask anything, get streaming responses |
| **Explain Code** | Select code → right-click → "eVera: Explain" (or `Ctrl+Shift+X`) |
| **Fix Code** | Select buggy code → right-click → "eVera: Fix" — replaces selection with fixed code |
| **Generate Code** | Select a comment → right-click → "eVera: Generate" — inserts code below |
| **Review File** | Review entire open file for bugs, security issues, and improvements |
| **Inline Completions** | Copilot-style completions as you type (powered by your local Ollama model) |
| **Knowledge Base** | Add any open file to eVera's RAG knowledge base |
| **Model Switcher** | Switch between 150+ models (Ollama offline, LM Studio, OpenAI, Anthropic, etc.) |
| **Mode Switcher** | Switch between LOCAL (offline), LAN (network), WWW (internet) |
| **Agent List** | See all 54 eVera agents in the sidebar |

## Requirements

1. Install and run [eVera](https://github.com/embeddedos-org/eVera):
   ```bash
   bash setup.sh
   python3 main.py --server
   ```
2. The extension connects to `http://localhost:8765` by default.

## Configuration

| Setting | Default | Description |
|---|---|---|
| `evera.serverUrl` | `http://localhost:8765` | eVera server URL |
| `evera.apiKey` | `` | API key (leave empty for local) |
| `evera.model` | `auto` | Model (auto = virtual router picks best) |
| `evera.mode` | `local` | Operating mode: local / lan / www |
| `evera.inlineCompletions` | `true` | Enable Copilot-style completions |
| `evera.autoReview` | `false` | Auto-review files on save |

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+E` | Open Chat |
| `Ctrl+Shift+X` | Explain selected code |
| `Ctrl+Shift+F` | Fix selected code |

## Offline Use

Set `evera.mode` to `local` and make sure Ollama is running:
```bash
ollama serve
ollama pull qwen3:8b
```
eVera will route all requests to Ollama — no internet required.

## License

MIT © embeddedOS Foundation
