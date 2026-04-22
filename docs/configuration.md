# ⚙️ Configuration Reference

All eVera settings are loaded from environment variables and/or a `.env` file using Pydantic Settings.

---

## LLM Settings (`VERA_LLM_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VERA_LLM_OLLAMA_URL` | `http://localhost:11434` | Ollama API server URL |
| `VERA_LLM_OLLAMA_MODEL` | `llama3.2` | Default Ollama model name |
| `VERA_LLM_OPENAI_API_KEY` | (none) | OpenAI API key |
| `VERA_LLM_OPENAI_MODEL` | `gpt-4o-mini` | Default OpenAI model |
| `VERA_LLM_GEMINI_API_KEY` | (none) | Google Gemini API key |
| `VERA_LLM_GEMINI_MODEL` | `gemini/gemini-2.0-flash` | Default Gemini model |
| `VERA_LLM_FALLBACK_ORDER` | `["ollama","openai","gemini"]` | Provider fallback priority |

---

## Voice Settings (`VERA_VOICE_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VERA_VOICE_STT_MODEL` | `small` | faster-whisper model size (tiny/base/small/medium/large) |
| `VERA_VOICE_STT_DEVICE` | `cpu` | STT compute device (cpu/cuda) |
| `VERA_VOICE_STT_COMPUTE_TYPE` | `int8` | STT quantization level |
| `VERA_VOICE_TTS_RATE` | `175` | Text-to-speech words per minute |
| `VERA_VOICE_VAD_AGGRESSIVENESS` | `2` | Voice activity detection sensitivity (0-3) |
| `VERA_VOICE_VAD_TRAILING_SILENCE_MS` | `500` | Silence duration before speech endpoint (ms) |
| `VERA_VOICE_SAMPLE_RATE` | `16000` | Audio sample rate in Hz |
| `VERA_VOICE_CHUNK_DURATION_MS` | `30` | Audio chunk duration for VAD (ms) |

---

## Memory Settings (`VERA_MEMORY_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VERA_MEMORY_FAISS_INDEX_PATH` | `data/faiss_index` | FAISS vector index file path |
| `VERA_MEMORY_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model for embeddings |
| `VERA_MEMORY_SEMANTIC_STORE_PATH` | `data/semantic.json` | Semantic memory JSON file |
| `VERA_MEMORY_SECURE_VAULT_PATH` | `data/vault.enc` | Encrypted vault file |
| `VERA_MEMORY_WORKING_MEMORY_MAX_TURNS` | `20` | Max conversation turns in working memory |

---

## Safety Settings (`VERA_SAFETY_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VERA_SAFETY_ALLOWED_ACTIONS` | `["chat","check_mood",...]` | Actions that execute without confirmation |
| `VERA_SAFETY_CONFIRM_ACTIONS` | `["execute_script",...]` | Actions requiring user approval |
| `VERA_SAFETY_DENIED_ACTIONS` | `["transfer_money",...]` | Actions always blocked |

---

## Server Settings (`VERA_SERVER_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VERA_SERVER_HOST` | `127.0.0.1` | Server bind address (use `0.0.0.0` for network) |
| `VERA_SERVER_PORT` | `8000` | Server TCP port |
| `VERA_SERVER_CORS_ORIGINS` | `["http://localhost:8000"]` | Allowed CORS origins |
| `VERA_SERVER_API_KEY` | (empty) | API key for authentication (empty = no auth) |
| `VERA_SERVER_WEBHOOK_SECRET` | (empty) | TradingView webhook verification secret |

---

## General Settings (`VERA_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VERA_DEBUG` | `false` | Enable verbose debug logging |
| `VERA_DATA_DIR` | `data` | Root directory for persistent data |

---

## Example `.env` File

```env
# LLM Providers
VERA_LLM_OLLAMA_URL=http://localhost:11434
VERA_LLM_OLLAMA_MODEL=llama3.2
VERA_LLM_OPENAI_API_KEY=sk-your-key-here
VERA_LLM_OPENAI_MODEL=gpt-4o-mini
VERA_LLM_GEMINI_API_KEY=your-gemini-key
VERA_LLM_FALLBACK_ORDER=["ollama","openai","gemini"]

# Voice
VERA_VOICE_STT_MODEL=small
VERA_VOICE_STT_DEVICE=cpu

# Server
VERA_SERVER_HOST=127.0.0.1
VERA_SERVER_PORT=8000
VERA_SERVER_API_KEY=my-secret-key
VERA_SERVER_WEBHOOK_SECRET=webhook-secret-123

# General
VERA_DEBUG=false
VERA_DATA_DIR=data
```
