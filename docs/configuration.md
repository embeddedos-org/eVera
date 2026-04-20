# ⚙️ Configuration Reference

All eVoca settings are loaded from environment variables and/or a `.env` file using Pydantic Settings.

---

## LLM Settings (`VOCA_LLM_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VOCA_LLM_OLLAMA_URL` | `http://localhost:11434` | Ollama API server URL |
| `VOCA_LLM_OLLAMA_MODEL` | `llama3.2` | Default Ollama model name |
| `VOCA_LLM_OPENAI_API_KEY` | (none) | OpenAI API key |
| `VOCA_LLM_OPENAI_MODEL` | `gpt-4o-mini` | Default OpenAI model |
| `VOCA_LLM_GEMINI_API_KEY` | (none) | Google Gemini API key |
| `VOCA_LLM_GEMINI_MODEL` | `gemini/gemini-2.0-flash` | Default Gemini model |
| `VOCA_LLM_FALLBACK_ORDER` | `["ollama","openai","gemini"]` | Provider fallback priority |

---

## Voice Settings (`VOCA_VOICE_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VOCA_VOICE_STT_MODEL` | `small` | faster-whisper model size (tiny/base/small/medium/large) |
| `VOCA_VOICE_STT_DEVICE` | `cpu` | STT compute device (cpu/cuda) |
| `VOCA_VOICE_STT_COMPUTE_TYPE` | `int8` | STT quantization level |
| `VOCA_VOICE_TTS_RATE` | `175` | Text-to-speech words per minute |
| `VOCA_VOICE_VAD_AGGRESSIVENESS` | `2` | Voice activity detection sensitivity (0-3) |
| `VOCA_VOICE_VAD_TRAILING_SILENCE_MS` | `500` | Silence duration before speech endpoint (ms) |
| `VOCA_VOICE_SAMPLE_RATE` | `16000` | Audio sample rate in Hz |
| `VOCA_VOICE_CHUNK_DURATION_MS` | `30` | Audio chunk duration for VAD (ms) |

---

## Memory Settings (`VOCA_MEMORY_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VOCA_MEMORY_FAISS_INDEX_PATH` | `data/faiss_index` | FAISS vector index file path |
| `VOCA_MEMORY_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model for embeddings |
| `VOCA_MEMORY_SEMANTIC_STORE_PATH` | `data/semantic.json` | Semantic memory JSON file |
| `VOCA_MEMORY_SECURE_VAULT_PATH` | `data/vault.enc` | Encrypted vault file |
| `VOCA_MEMORY_WORKING_MEMORY_MAX_TURNS` | `20` | Max conversation turns in working memory |

---

## Safety Settings (`VOCA_SAFETY_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VOCA_SAFETY_ALLOWED_ACTIONS` | `["chat","check_mood",...]` | Actions that execute without confirmation |
| `VOCA_SAFETY_CONFIRM_ACTIONS` | `["execute_script",...]` | Actions requiring user approval |
| `VOCA_SAFETY_DENIED_ACTIONS` | `["transfer_money",...]` | Actions always blocked |

---

## Server Settings (`VOCA_SERVER_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VOCA_SERVER_HOST` | `127.0.0.1` | Server bind address (use `0.0.0.0` for network) |
| `VOCA_SERVER_PORT` | `8000` | Server TCP port |
| `VOCA_SERVER_CORS_ORIGINS` | `["http://localhost:8000"]` | Allowed CORS origins |
| `VOCA_SERVER_API_KEY` | (empty) | API key for authentication (empty = no auth) |
| `VOCA_SERVER_WEBHOOK_SECRET` | (empty) | TradingView webhook verification secret |

---

## General Settings (`VOCA_` prefix)

| Variable | Default | Description |
|----------|---------|-------------|
| `VOCA_DEBUG` | `false` | Enable verbose debug logging |
| `VOCA_DATA_DIR` | `data` | Root directory for persistent data |

---

## Example `.env` File

```env
# LLM Providers
VOCA_LLM_OLLAMA_URL=http://localhost:11434
VOCA_LLM_OLLAMA_MODEL=llama3.2
VOCA_LLM_OPENAI_API_KEY=sk-your-key-here
VOCA_LLM_OPENAI_MODEL=gpt-4o-mini
VOCA_LLM_GEMINI_API_KEY=your-gemini-key
VOCA_LLM_FALLBACK_ORDER=["ollama","openai","gemini"]

# Voice
VOCA_VOICE_STT_MODEL=small
VOCA_VOICE_STT_DEVICE=cpu

# Server
VOCA_SERVER_HOST=127.0.0.1
VOCA_SERVER_PORT=8000
VOCA_SERVER_API_KEY=my-secret-key
VOCA_SERVER_WEBHOOK_SECRET=webhook-secret-123

# General
VOCA_DEBUG=false
VOCA_DATA_DIR=data
```
