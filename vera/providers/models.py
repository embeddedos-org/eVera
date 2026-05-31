"""eVera Model Registry — 100+ models across all providers and tiers.

Offline-first: Ollama models are listed first and tried before any cloud provider.
Every model family from the LLM config is represented.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ModelTier(str, Enum):
    """Model capability tiers for intelligent routing."""
    FAST = "fast"           # Ultra-fast, small models for simple tasks
    EXECUTOR = "executor"   # General-purpose, balanced models
    SPECIALIST = "specialist"  # Domain-specific or large models
    STRATEGIST = "strategist"  # Alias for SPECIALIST (backward compat)
    ARCHITECT = "architect"    # Alias for SPECIALIST (backward compat)
    REASONING = "reasoning"    # Chain-of-thought, complex reasoning
    VISION = "vision"          # Image/video understanding
    EMBEDDING = "embedding"    # Vector embeddings for RAG/search
    CODE = "code"              # Code generation and analysis


@dataclass
class ModelConfig:
    id: str
    provider: str
    tier: ModelTier
    context_window: int = 8192
    supports_vision: bool = False
    supports_tools: bool = True
    offline: bool = False          # True = works without internet
    description: str = ""
    ram_gb: float = 0.0            # Approximate RAM needed for offline models
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# OLLAMA OFFLINE MODELS — All work without internet
# ---------------------------------------------------------------------------

# --- Llama family ---
LLAMA_MODELS = [
    ModelConfig("ollama/llama3.3:70b",      "ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=40, description="Llama 3.3 70B — best Llama overall", tags=["general", "large"]),
    ModelConfig("ollama/llama3.3:8b",       "ollama", ModelTier.EXECUTOR,   128000, offline=True, ram_gb=5,  description="Llama 3.3 8B — fast and capable"),
    ModelConfig("ollama/llama3.2:3b",       "ollama", ModelTier.FAST,       128000, offline=True, ram_gb=2,  description="Llama 3.2 3B — ultra-fast, low RAM", tags=["fast", "low-ram"]),
    ModelConfig("ollama/llama3.2:1b",       "ollama", ModelTier.FAST,       128000, offline=True, ram_gb=1,  description="Llama 3.2 1B — minimal RAM", tags=["fast", "low-ram"]),
    ModelConfig("ollama/llama3.2-vision:11b","ollama", ModelTier.VISION,    128000, supports_vision=True, offline=True, ram_gb=8, description="Llama 3.2 Vision 11B", tags=["vision"]),
    ModelConfig("ollama/llama3.2-vision:90b","ollama", ModelTier.VISION,    128000, supports_vision=True, offline=True, ram_gb=55, description="Llama 3.2 Vision 90B", tags=["vision", "large"]),
    ModelConfig("ollama/llama3.1:70b",      "ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=40, description="Llama 3.1 70B"),
    ModelConfig("ollama/llama3.1:8b",       "ollama", ModelTier.EXECUTOR,   128000, offline=True, ram_gb=5,  description="Llama 3.1 8B"),
    ModelConfig("ollama/llama3.1:405b",     "ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=230, description="Llama 3.1 405B — largest Llama", tags=["large"]),
    ModelConfig("ollama/llama3:8b",         "ollama", ModelTier.EXECUTOR,   8192,  offline=True, ram_gb=5,  description="Llama 3 8B"),
    ModelConfig("ollama/llama3:70b",        "ollama", ModelTier.SPECIALIST, 8192,  offline=True, ram_gb=40, description="Llama 3 70B"),
    ModelConfig("ollama/llama2:7b",         "ollama", ModelTier.EXECUTOR,   4096,  offline=True, ram_gb=4,  description="Llama 2 7B — legacy"),
    ModelConfig("ollama/llama2:13b",        "ollama", ModelTier.EXECUTOR,   4096,  offline=True, ram_gb=8,  description="Llama 2 13B — legacy"),
]

# --- Qwen family (best overall offline) ---
QWEN_MODELS = [
    ModelConfig("ollama/qwen3:0.6b",        "ollama", ModelTier.FAST,       32768, offline=True, ram_gb=0.5, description="Qwen3 0.6B — minimal", tags=["fast", "low-ram"]),
    ModelConfig("ollama/qwen3:1.7b",        "ollama", ModelTier.FAST,       32768, offline=True, ram_gb=1,   description="Qwen3 1.7B — fast", tags=["fast"]),
    ModelConfig("ollama/qwen3:4b",          "ollama", ModelTier.EXECUTOR,   32768, offline=True, ram_gb=3,   description="Qwen3 4B — balanced"),
    ModelConfig("ollama/qwen3:8b",          "ollama", ModelTier.EXECUTOR,   32768, offline=True, ram_gb=5,   description="Qwen3 8B — recommended general", tags=["recommended"]),
    ModelConfig("ollama/qwen3:14b",         "ollama", ModelTier.SPECIALIST, 32768, offline=True, ram_gb=9,   description="Qwen3 14B — high quality"),
    ModelConfig("ollama/qwen3:32b",         "ollama", ModelTier.SPECIALIST, 32768, offline=True, ram_gb=20,  description="Qwen3 32B — best Qwen", tags=["recommended"]),
    ModelConfig("ollama/qwen3:72b",         "ollama", ModelTier.SPECIALIST, 32768, offline=True, ram_gb=45,  description="Qwen3 72B — largest Qwen"),
    ModelConfig("ollama/qwen2.5:0.5b",      "ollama", ModelTier.FAST,       32768, offline=True, ram_gb=0.4, description="Qwen2.5 0.5B", tags=["low-ram"]),
    ModelConfig("ollama/qwen2.5:1.5b",      "ollama", ModelTier.FAST,       32768, offline=True, ram_gb=1,   description="Qwen2.5 1.5B"),
    ModelConfig("ollama/qwen2.5:3b",        "ollama", ModelTier.FAST,       32768, offline=True, ram_gb=2,   description="Qwen2.5 3B"),
    ModelConfig("ollama/qwen2.5:7b",        "ollama", ModelTier.EXECUTOR,   32768, offline=True, ram_gb=5,   description="Qwen2.5 7B"),
    ModelConfig("ollama/qwen2.5:14b",       "ollama", ModelTier.SPECIALIST, 32768, offline=True, ram_gb=9,   description="Qwen2.5 14B"),
    ModelConfig("ollama/qwen2.5:32b",       "ollama", ModelTier.SPECIALIST, 32768, offline=True, ram_gb=20,  description="Qwen2.5 32B"),
    ModelConfig("ollama/qwen2.5:72b",       "ollama", ModelTier.SPECIALIST, 32768, offline=True, ram_gb=45,  description="Qwen2.5 72B"),
    ModelConfig("ollama/qwen2.5-coder:1.5b","ollama", ModelTier.CODE,       32768, offline=True, ram_gb=1,   description="Qwen2.5 Coder 1.5B", tags=["code"]),
    ModelConfig("ollama/qwen2.5-coder:7b",  "ollama", ModelTier.CODE,       32768, offline=True, ram_gb=5,   description="Qwen2.5 Coder 7B — best small coder", tags=["code", "recommended"]),
    ModelConfig("ollama/qwen2.5-coder:14b", "ollama", ModelTier.CODE,       32768, offline=True, ram_gb=9,   description="Qwen2.5 Coder 14B", tags=["code"]),
    ModelConfig("ollama/qwen2.5-coder:32b", "ollama", ModelTier.CODE,       32768, offline=True, ram_gb=20,  description="Qwen2.5 Coder 32B", tags=["code"]),
    ModelConfig("ollama/qwen2.5vl:7b",      "ollama", ModelTier.VISION,     32768, supports_vision=True, offline=True, ram_gb=5, description="Qwen2.5 VL 7B — vision", tags=["vision"]),
    ModelConfig("ollama/qwen2.5vl:72b",     "ollama", ModelTier.VISION,     32768, supports_vision=True, offline=True, ram_gb=45, description="Qwen2.5 VL 72B — best vision", tags=["vision"]),
    ModelConfig("ollama/qwen3-coder:8b",    "ollama", ModelTier.CODE,       32768, offline=True, ram_gb=5,   description="Qwen3 Coder 8B", tags=["code"]),
    ModelConfig("ollama/qwen3-coder:32b",   "ollama", ModelTier.CODE,       32768, offline=True, ram_gb=20,  description="Qwen3 Coder 32B — best coder", tags=["code", "recommended"]),
]

# --- DeepSeek family (best reasoning) ---
DEEPSEEK_MODELS = [
    ModelConfig("ollama/deepseek-r1:1.5b",  "ollama", ModelTier.REASONING, 64000, offline=True, ram_gb=1,   description="DeepSeek-R1 1.5B — tiny reasoning", tags=["reasoning"]),
    ModelConfig("ollama/deepseek-r1:7b",    "ollama", ModelTier.REASONING, 64000, offline=True, ram_gb=5,   description="DeepSeek-R1 7B — reasoning", tags=["reasoning", "recommended"]),
    ModelConfig("ollama/deepseek-r1:8b",    "ollama", ModelTier.REASONING, 64000, offline=True, ram_gb=5,   description="DeepSeek-R1 8B", tags=["reasoning"]),
    ModelConfig("ollama/deepseek-r1:14b",   "ollama", ModelTier.REASONING, 64000, offline=True, ram_gb=9,   description="DeepSeek-R1 14B", tags=["reasoning"]),
    ModelConfig("ollama/deepseek-r1:32b",   "ollama", ModelTier.REASONING, 64000, offline=True, ram_gb=20,  description="DeepSeek-R1 32B — best reasoning", tags=["reasoning", "recommended"]),
    ModelConfig("ollama/deepseek-r1:70b",   "ollama", ModelTier.REASONING, 64000, offline=True, ram_gb=45,  description="DeepSeek-R1 70B", tags=["reasoning", "large"]),
    ModelConfig("ollama/deepseek-r1:671b",  "ollama", ModelTier.REASONING, 64000, offline=True, ram_gb=400, description="DeepSeek-R1 671B — full model", tags=["reasoning", "large"]),
    ModelConfig("ollama/deepseek-v3",       "ollama", ModelTier.SPECIALIST, 64000, offline=True, ram_gb=400, description="DeepSeek V3 — frontier model", tags=["large"]),
    ModelConfig("ollama/deepseek-coder-v2", "ollama", ModelTier.CODE,       64000, offline=True, ram_gb=9,   description="DeepSeek Coder V2", tags=["code"]),
]

# --- Gemma family (Google, offline) ---
GEMMA_MODELS = [
    ModelConfig("ollama/gemma3:1b",         "ollama", ModelTier.FAST,       128000, offline=True, ram_gb=1,   description="Gemma 3 1B — tiny", tags=["fast", "low-ram"]),
    ModelConfig("ollama/gemma3:4b",         "ollama", ModelTier.EXECUTOR,   128000, offline=True, ram_gb=3,   description="Gemma 3 4B — fast"),
    ModelConfig("ollama/gemma3:12b",        "ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=8,   description="Gemma 3 12B — MacBook recommended", tags=["recommended"]),
    ModelConfig("ollama/gemma3:27b",        "ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=17,  description="Gemma 3 27B — high quality"),
    ModelConfig("ollama/gemma3:4b-vision",  "ollama", ModelTier.VISION,     128000, supports_vision=True, offline=True, ram_gb=3, description="Gemma 3 4B Vision", tags=["vision"]),
    ModelConfig("ollama/gemma3:12b-vision", "ollama", ModelTier.VISION,     128000, supports_vision=True, offline=True, ram_gb=8, description="Gemma 3 12B Vision", tags=["vision"]),
    ModelConfig("ollama/gemma4:9b",         "ollama", ModelTier.EXECUTOR,   128000, supports_vision=True, offline=True, ram_gb=6, description="Gemma 4 9B — latest Google", tags=["vision", "recommended"]),
    ModelConfig("ollama/gemma4:27b",        "ollama", ModelTier.SPECIALIST, 128000, supports_vision=True, offline=True, ram_gb=17, description="Gemma 4 27B — best Gemma", tags=["vision"]),
    ModelConfig("ollama/gemma2:2b",         "ollama", ModelTier.FAST,       8192,  offline=True, ram_gb=1.5, description="Gemma 2 2B"),
    ModelConfig("ollama/gemma2:9b",         "ollama", ModelTier.EXECUTOR,   8192,  offline=True, ram_gb=6,   description="Gemma 2 9B"),
    ModelConfig("ollama/gemma2:27b",        "ollama", ModelTier.SPECIALIST, 8192,  offline=True, ram_gb=17,  description="Gemma 2 27B"),
]

# --- Mistral family ---
MISTRAL_MODELS = [
    ModelConfig("ollama/mistral:7b",            "ollama", ModelTier.EXECUTOR,   32768, offline=True, ram_gb=5,  description="Mistral 7B — classic"),
    ModelConfig("ollama/mistral-nemo:12b",       "ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=8, description="Mistral Nemo 12B — long context"),
    ModelConfig("ollama/mistral-small3.2:24b",   "ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=15, description="Mistral Small 3.2 24B", tags=["recommended"]),
    ModelConfig("ollama/mixtral:8x7b",           "ollama", ModelTier.SPECIALIST, 32768, offline=True, ram_gb=26, description="Mixtral 8x7B MoE"),
    ModelConfig("ollama/mixtral:8x22b",          "ollama", ModelTier.SPECIALIST, 64000, offline=True, ram_gb=80, description="Mixtral 8x22B MoE — large"),
    ModelConfig("ollama/magistral:24b",          "ollama", ModelTier.REASONING,  128000, offline=True, ram_gb=15, description="Magistral 24B — Mistral reasoning", tags=["reasoning"]),
]

# --- Phi family (Microsoft) ---
PHI_MODELS = [
    ModelConfig("ollama/phi4:14b",          "ollama", ModelTier.SPECIALIST, 16384, offline=True, ram_gb=9,  description="Phi-4 14B — best Phi", tags=["recommended"]),
    ModelConfig("ollama/phi4-mini:3.8b",    "ollama", ModelTier.EXECUTOR,   16384, offline=True, ram_gb=2.5, description="Phi-4 Mini 3.8B — fast"),
    ModelConfig("ollama/phi3:3.8b",         "ollama", ModelTier.FAST,       128000, offline=True, ram_gb=2.5, description="Phi-3 Mini 3.8B", tags=["low-ram"]),
    ModelConfig("ollama/phi3:14b",          "ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=9,  description="Phi-3 Medium 14B"),
    ModelConfig("ollama/phi3.5:3.8b",       "ollama", ModelTier.FAST,       128000, offline=True, ram_gb=2.5, description="Phi-3.5 Mini 3.8B"),
    ModelConfig("ollama/phi2:2.7b",         "ollama", ModelTier.FAST,       2048,  offline=True, ram_gb=2,  description="Phi-2 2.7B — legacy"),
]

# --- Code-specific models ---
CODE_MODELS = [
    ModelConfig("ollama/codellama:7b",      "ollama", ModelTier.CODE,  16384, offline=True, ram_gb=4,  description="Code Llama 7B", tags=["code"]),
    ModelConfig("ollama/codellama:13b",     "ollama", ModelTier.CODE,  16384, offline=True, ram_gb=8,  description="Code Llama 13B", tags=["code"]),
    ModelConfig("ollama/codellama:34b",     "ollama", ModelTier.CODE,  16384, offline=True, ram_gb=20, description="Code Llama 34B", tags=["code"]),
    ModelConfig("ollama/granite-code:3b",   "ollama", ModelTier.CODE,  8192,  offline=True, ram_gb=2,  description="Granite Code 3B (IBM)", tags=["code"]),
    ModelConfig("ollama/granite-code:8b",   "ollama", ModelTier.CODE,  8192,  offline=True, ram_gb=5,  description="Granite Code 8B (IBM)", tags=["code"]),
    ModelConfig("ollama/granite-code:20b",  "ollama", ModelTier.CODE,  8192,  offline=True, ram_gb=12, description="Granite Code 20B (IBM)", tags=["code"]),
    ModelConfig("ollama/granite-code:34b",  "ollama", ModelTier.CODE,  8192,  offline=True, ram_gb=20, description="Granite Code 34B (IBM)", tags=["code"]),
    ModelConfig("ollama/starcoder2:3b",     "ollama", ModelTier.CODE,  16384, offline=True, ram_gb=2,  description="StarCoder2 3B", tags=["code"]),
    ModelConfig("ollama/starcoder2:7b",     "ollama", ModelTier.CODE,  16384, offline=True, ram_gb=5,  description="StarCoder2 7B", tags=["code"]),
    ModelConfig("ollama/starcoder2:15b",    "ollama", ModelTier.CODE,  16384, offline=True, ram_gb=9,  description="StarCoder2 15B", tags=["code"]),
]

# --- Vision models ---
VISION_MODELS = [
    ModelConfig("ollama/llava:7b",          "ollama", ModelTier.VISION, 4096,  supports_vision=True, offline=True, ram_gb=5,  description="LLaVA 7B — classic vision", tags=["vision"]),
    ModelConfig("ollama/llava:13b",         "ollama", ModelTier.VISION, 4096,  supports_vision=True, offline=True, ram_gb=8,  description="LLaVA 13B", tags=["vision"]),
    ModelConfig("ollama/llava:34b",         "ollama", ModelTier.VISION, 4096,  supports_vision=True, offline=True, ram_gb=20, description="LLaVA 34B", tags=["vision"]),
    ModelConfig("ollama/minicpm-v:8b",      "ollama", ModelTier.VISION, 8192,  supports_vision=True, offline=True, ram_gb=5,  description="MiniCPM-V 8B — efficient vision", tags=["vision"]),
    ModelConfig("ollama/moondream:1.8b",    "ollama", ModelTier.VISION, 2048,  supports_vision=True, offline=True, ram_gb=1.5, description="Moondream 1.8B — tiny vision", tags=["vision", "low-ram"]),
]

# --- Reasoning / QwQ ---
REASONING_MODELS = [
    ModelConfig("ollama/qwq:32b",           "ollama", ModelTier.REASONING, 32768, offline=True, ram_gb=20, description="QwQ 32B — Qwen reasoning", tags=["reasoning", "recommended"]),
    ModelConfig("ollama/qwq:7b",            "ollama", ModelTier.REASONING, 32768, offline=True, ram_gb=5,  description="QwQ 7B — fast reasoning", tags=["reasoning"]),
    ModelConfig("ollama/cogito:8b",         "ollama", ModelTier.REASONING, 32768, offline=True, ram_gb=5,  description="Cogito 8B — reasoning", tags=["reasoning"]),
    ModelConfig("ollama/cogito:32b",        "ollama", ModelTier.REASONING, 32768, offline=True, ram_gb=20, description="Cogito 32B", tags=["reasoning"]),
]

# --- Embedding models (for RAG, offline) ---
EMBEDDING_MODELS = [
    ModelConfig("ollama/nomic-embed-text",  "ollama", ModelTier.EMBEDDING, 8192, offline=True, ram_gb=0.3, description="Nomic Embed Text — best offline embedding", tags=["embedding", "recommended"]),
    ModelConfig("ollama/mxbai-embed-large", "ollama", ModelTier.EMBEDDING, 512,  offline=True, ram_gb=0.7, description="MXBAI Embed Large", tags=["embedding"]),
    ModelConfig("ollama/qwen3-embedding:0.6b","ollama", ModelTier.EMBEDDING, 32768, offline=True, ram_gb=0.5, description="Qwen3 Embedding 0.6B", tags=["embedding"]),
    ModelConfig("ollama/qwen3-embedding:4b","ollama", ModelTier.EMBEDDING, 32768, offline=True, ram_gb=3,   description="Qwen3 Embedding 4B", tags=["embedding"]),
    ModelConfig("ollama/all-minilm",        "ollama", ModelTier.EMBEDDING, 512,  offline=True, ram_gb=0.1, description="All-MiniLM — tiny embedding", tags=["embedding", "low-ram"]),
    ModelConfig("ollama/snowflake-arctic-embed","ollama", ModelTier.EMBEDDING, 512, offline=True, ram_gb=0.5, description="Snowflake Arctic Embed", tags=["embedding"]),
]

# --- Misc / Specialty ---
MISC_MODELS = [
    ModelConfig("ollama/hermes3:8b",        "ollama", ModelTier.EXECUTOR,   8192,  offline=True, ram_gb=5,  description="Hermes 3 8B — instruction following"),
    ModelConfig("ollama/hermes3:70b",       "ollama", ModelTier.SPECIALIST, 8192,  offline=True, ram_gb=40, description="Hermes 3 70B"),
    ModelConfig("ollama/command-r:35b",     "ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=22, description="Command-R 35B (Cohere)"),
    ModelConfig("ollama/command-r-plus:104b","ollama", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=65, description="Command-R+ 104B (Cohere)"),
    ModelConfig("ollama/tinyllama:1.1b",    "ollama", ModelTier.FAST,       2048,  offline=True, ram_gb=0.7, description="TinyLlama 1.1B — minimal", tags=["fast", "low-ram"]),
    ModelConfig("ollama/smollm2:135m",      "ollama", ModelTier.FAST,       8192,  offline=True, ram_gb=0.1, description="SmolLM2 135M — ultra-tiny", tags=["fast", "low-ram"]),
    ModelConfig("ollama/smollm2:360m",      "ollama", ModelTier.FAST,       8192,  offline=True, ram_gb=0.3, description="SmolLM2 360M", tags=["fast", "low-ram"]),
    ModelConfig("ollama/smollm2:1.7b",      "ollama", ModelTier.FAST,       8192,  offline=True, ram_gb=1,   description="SmolLM2 1.7B", tags=["fast"]),
    ModelConfig("ollama/gpt-oss:7b",        "ollama", ModelTier.EXECUTOR,   8192,  offline=True, ram_gb=5,   description="GPT-OSS 7B (Meta open)"),
    ModelConfig("ollama/gpt-oss:20b",       "ollama", ModelTier.SPECIALIST, 8192,  offline=True, ram_gb=13,  description="GPT-OSS 20B"),
]

# ---------------------------------------------------------------------------
# LOCAL OPENAI-COMPATIBLE SERVERS — LM Studio, Jan, llama.cpp
# These expose an OpenAI-compatible REST API at a local URL.
# Configure VERA_LM_STUDIO_URL / VERA_JAN_URL / VERA_LLAMACPP_URL in .env
# Default ports: LM Studio=1234, Jan=1337, llama.cpp=8080
# ---------------------------------------------------------------------------
LM_STUDIO_MODELS = [
    ModelConfig("lmstudio/auto",              "lmstudio", ModelTier.EXECUTOR,   128000, offline=True, ram_gb=0,
                description="LM Studio — auto-detect loaded model", tags=["local", "openai-compat"]),
    ModelConfig("lmstudio/llama3.2:3b",       "lmstudio", ModelTier.FAST,       128000, offline=True, ram_gb=2,
                description="LM Studio: Llama 3.2 3B", tags=["local", "fast"]),
    ModelConfig("lmstudio/llama3.3:70b",      "lmstudio", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=40,
                description="LM Studio: Llama 3.3 70B", tags=["local", "large"]),
    ModelConfig("lmstudio/qwen3:8b",          "lmstudio", ModelTier.EXECUTOR,   32768,  offline=True, ram_gb=5,
                description="LM Studio: Qwen3 8B", tags=["local"]),
    ModelConfig("lmstudio/deepseek-r1:7b",    "lmstudio", ModelTier.REASONING,  64000,  offline=True, ram_gb=5,
                description="LM Studio: DeepSeek-R1 7B", tags=["local", "reasoning"]),
    ModelConfig("lmstudio/phi-4:14b",         "lmstudio", ModelTier.SPECIALIST, 16384,  offline=True, ram_gb=9,
                description="LM Studio: Phi-4 14B", tags=["local"]),
    ModelConfig("lmstudio/gemma3:12b",        "lmstudio", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=8,
                description="LM Studio: Gemma 3 12B", tags=["local"]),
    ModelConfig("lmstudio/mistral-small3.2:24b","lmstudio", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=15,
                description="LM Studio: Mistral Small 3.2 24B", tags=["local"]),
]

JAN_MODELS = [
    ModelConfig("jan/auto",                   "jan",      ModelTier.EXECUTOR,   128000, offline=True, ram_gb=0,
                description="Jan AI — auto-detect loaded model", tags=["local", "openai-compat"]),
    ModelConfig("jan/llama3.2:3b",            "jan",      ModelTier.FAST,       128000, offline=True, ram_gb=2,
                description="Jan: Llama 3.2 3B", tags=["local", "fast"]),
    ModelConfig("jan/llama3.3:70b",           "jan",      ModelTier.SPECIALIST, 128000, offline=True, ram_gb=40,
                description="Jan: Llama 3.3 70B", tags=["local", "large"]),
    ModelConfig("jan/qwen3:8b",               "jan",      ModelTier.EXECUTOR,   32768,  offline=True, ram_gb=5,
                description="Jan: Qwen3 8B", tags=["local"]),
    ModelConfig("jan/deepseek-r1:7b",         "jan",      ModelTier.REASONING,  64000,  offline=True, ram_gb=5,
                description="Jan: DeepSeek-R1 7B", tags=["local", "reasoning"]),
    ModelConfig("jan/phi-4:14b",              "jan",      ModelTier.SPECIALIST, 16384,  offline=True, ram_gb=9,
                description="Jan: Phi-4 14B", tags=["local"]),
]

LLAMA_CPP_MODELS = [
    ModelConfig("llamacpp/auto",              "llamacpp", ModelTier.EXECUTOR,   128000, offline=True, ram_gb=0,
                description="llama.cpp server — auto-detect loaded model", tags=["local", "openai-compat"]),
    ModelConfig("llamacpp/llama3.2:3b",       "llamacpp", ModelTier.FAST,       128000, offline=True, ram_gb=2,
                description="llama.cpp: Llama 3.2 3B", tags=["local", "fast"]),
    ModelConfig("llamacpp/llama3.3:70b",      "llamacpp", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=40,
                description="llama.cpp: Llama 3.3 70B", tags=["local", "large"]),
    ModelConfig("llamacpp/qwen3:8b",          "llamacpp", ModelTier.EXECUTOR,   32768,  offline=True, ram_gb=5,
                description="llama.cpp: Qwen3 8B", tags=["local"]),
    ModelConfig("llamacpp/deepseek-r1:7b",    "llamacpp", ModelTier.REASONING,  64000,  offline=True, ram_gb=5,
                description="llama.cpp: DeepSeek-R1 7B", tags=["local", "reasoning"]),
    ModelConfig("llamacpp/deepseek-r1:32b",   "llamacpp", ModelTier.REASONING,  64000,  offline=True, ram_gb=20,
                description="llama.cpp: DeepSeek-R1 32B", tags=["local", "reasoning"]),
    ModelConfig("llamacpp/mistral-small3.2:24b","llamacpp", ModelTier.SPECIALIST, 128000, offline=True, ram_gb=15,
                description="llama.cpp: Mistral Small 3.2 24B", tags=["local"]),
]

# ---------------------------------------------------------------------------
# CLOUD MODELS — Require internet + API keys (WWW mode only)
# ---------------------------------------------------------------------------
OPENAI_MODELS = [
    ModelConfig("gpt-4o",           "openai", ModelTier.SPECIALIST, 128000, supports_vision=True,  description="GPT-4o — OpenAI flagship"),
    ModelConfig("gpt-4o-mini",      "openai", ModelTier.EXECUTOR,   128000, supports_vision=True,  description="GPT-4o Mini — fast and cheap"),
    ModelConfig("gpt-4-turbo",      "openai", ModelTier.SPECIALIST, 128000, supports_vision=True,  description="GPT-4 Turbo"),
    ModelConfig("o1",               "openai", ModelTier.REASONING,  200000, description="o1 — OpenAI reasoning", tags=["reasoning"]),
    ModelConfig("o1-mini",          "openai", ModelTier.REASONING,  128000, description="o1-mini — fast reasoning", tags=["reasoning"]),
    ModelConfig("o3",               "openai", ModelTier.REASONING,  200000, description="o3 — latest OpenAI reasoning", tags=["reasoning"]),
    ModelConfig("o3-mini",          "openai", ModelTier.REASONING,  200000, description="o3-mini", tags=["reasoning"]),
    ModelConfig("o4-mini",          "openai", ModelTier.REASONING,  200000, description="o4-mini — latest", tags=["reasoning"]),
]

ANTHROPIC_MODELS = [
    ModelConfig("claude-opus-4",        "anthropic", ModelTier.SPECIALIST, 200000, supports_vision=True, description="Claude Opus 4 — most capable"),
    ModelConfig("claude-sonnet-4",      "anthropic", ModelTier.SPECIALIST, 200000, supports_vision=True, description="Claude Sonnet 4 — balanced"),
    ModelConfig("claude-3-5-sonnet",    "anthropic", ModelTier.SPECIALIST, 200000, supports_vision=True, description="Claude 3.5 Sonnet"),
    ModelConfig("claude-3-5-haiku",     "anthropic", ModelTier.EXECUTOR,   200000, supports_vision=True, description="Claude 3.5 Haiku — fast"),
    ModelConfig("claude-3-opus",        "anthropic", ModelTier.SPECIALIST, 200000, supports_vision=True, description="Claude 3 Opus"),
]

GOOGLE_MODELS = [
    ModelConfig("gemini-2.5-pro",       "gemini", ModelTier.SPECIALIST, 1000000, supports_vision=True, description="Gemini 2.5 Pro — 1M context"),
    ModelConfig("gemini-2.5-flash",     "gemini", ModelTier.EXECUTOR,   1000000, supports_vision=True, description="Gemini 2.5 Flash — fast"),
    ModelConfig("gemini-2.0-flash",     "gemini", ModelTier.EXECUTOR,   1000000, supports_vision=True, description="Gemini 2.0 Flash"),
    ModelConfig("gemini-1.5-pro",       "gemini", ModelTier.SPECIALIST, 2000000, supports_vision=True, description="Gemini 1.5 Pro — 2M context"),
]

GROQ_MODELS = [
    ModelConfig("groq/llama-3.3-70b",   "groq", ModelTier.SPECIALIST, 128000, description="Llama 3.3 70B via Groq — ultra-fast inference"),
    ModelConfig("groq/llama-3.1-8b",    "groq", ModelTier.EXECUTOR,   128000, description="Llama 3.1 8B via Groq"),
    ModelConfig("groq/mixtral-8x7b",    "groq", ModelTier.SPECIALIST, 32768,  description="Mixtral 8x7B via Groq"),
    ModelConfig("groq/gemma2-9b",       "groq", ModelTier.EXECUTOR,   8192,   description="Gemma 2 9B via Groq"),
    ModelConfig("groq/deepseek-r1-70b", "groq", ModelTier.REASONING,  128000, description="DeepSeek-R1 70B via Groq", tags=["reasoning"]),
    ModelConfig("groq/qwen-qwq-32b",    "groq", ModelTier.REASONING,  128000, description="QwQ 32B via Groq", tags=["reasoning"]),
]

DEEPSEEK_CLOUD_MODELS = [
    ModelConfig("deepseek-chat",        "deepseek", ModelTier.SPECIALIST, 64000, description="DeepSeek Chat V3"),
    ModelConfig("deepseek-reasoner",    "deepseek", ModelTier.REASONING,  64000, description="DeepSeek Reasoner R1", tags=["reasoning"]),
    ModelConfig("deepseek-coder",       "deepseek", ModelTier.CODE,       64000, description="DeepSeek Coder V2", tags=["code"]),
]

MISTRAL_CLOUD_MODELS = [
    ModelConfig("mistral-large-latest", "mistral", ModelTier.SPECIALIST, 128000, description="Mistral Large — flagship"),
    ModelConfig("mistral-medium",       "mistral", ModelTier.EXECUTOR,   32768,  description="Mistral Medium"),
    ModelConfig("codestral-latest",     "mistral", ModelTier.CODE,       32768,  description="Codestral — Mistral code model", tags=["code"]),
    ModelConfig("magistral-medium",     "mistral", ModelTier.REASONING,  128000, description="Magistral Medium — reasoning", tags=["reasoning"]),
]

TOGETHER_MODELS = [
    ModelConfig("together/llama-3.1-70b", "together", ModelTier.SPECIALIST, 128000, description="Llama 3.1 70B via Together AI"),
    ModelConfig("together/qwen2.5-72b",   "together", ModelTier.SPECIALIST, 32768,  description="Qwen2.5 72B via Together AI"),
    ModelConfig("together/deepseek-r1",   "together", ModelTier.REASONING,  64000,  description="DeepSeek-R1 via Together AI", tags=["reasoning"]),
]

PERPLEXITY_MODELS = [
    ModelConfig("pplx/sonar-pro",         "perplexity", ModelTier.SPECIALIST, 200000, description="Sonar Pro — web-grounded search"),
    ModelConfig("pplx/sonar",             "perplexity", ModelTier.EXECUTOR,   127072, description="Sonar — fast web search"),
    ModelConfig("pplx/sonar-reasoning",   "perplexity", ModelTier.REASONING,  127072, description="Sonar Reasoning", tags=["reasoning"]),
]

# ---------------------------------------------------------------------------
# Master registry — offline models first for priority
# ---------------------------------------------------------------------------

ALL_MODELS: list[ModelConfig] = (
    LLAMA_MODELS
    + QWEN_MODELS
    + DEEPSEEK_MODELS
    + GEMMA_MODELS
    + MISTRAL_MODELS
    + PHI_MODELS
    + CODE_MODELS
    + VISION_MODELS
    + REASONING_MODELS
    + EMBEDDING_MODELS
    + MISC_MODELS
    + LM_STUDIO_MODELS
    + JAN_MODELS
    + LLAMA_CPP_MODELS
    + OPENAI_MODELS
    + ANTHROPIC_MODELS
    + GOOGLE_MODELS
    + GROQ_MODELS
    + DEEPSEEK_CLOUD_MODELS
    + MISTRAL_CLOUD_MODELS
    + TOGETHER_MODELS
    + PERPLEXITY_MODELS
)

# Quick lookup by model id
MODEL_BY_ID: dict[str, ModelConfig] = {m.id: m for m in ALL_MODELS}

# Offline-only models (for LOCAL and LAN modes)
OFFLINE_MODELS: list[ModelConfig] = [m for m in ALL_MODELS if m.offline]

# Default model preferences per tier (offline-first)
DEFAULT_MODELS: dict[ModelTier, str] = {
    ModelTier.FAST:      "ollama/qwen3:4b",
    ModelTier.EXECUTOR:  "ollama/qwen3:8b",
    ModelTier.SPECIALIST:"ollama/qwen3:32b",
    ModelTier.REASONING: "ollama/deepseek-r1:7b",
    ModelTier.VISION:    "ollama/gemma4:9b",
    ModelTier.CODE:      "ollama/qwen2.5-coder:7b",
    ModelTier.EMBEDDING: "ollama/nomic-embed-text",
}

# Low-RAM defaults (for machines with < 8GB RAM)
LOW_RAM_DEFAULTS: dict[ModelTier, str] = {
    ModelTier.FAST:      "ollama/smollm2:1.7b",
    ModelTier.EXECUTOR:  "ollama/qwen3:4b",
    ModelTier.SPECIALIST:"ollama/phi4-mini:3.8b",
    ModelTier.REASONING: "ollama/deepseek-r1:1.5b",
    ModelTier.VISION:    "ollama/moondream:1.8b",
    ModelTier.CODE:      "ollama/qwen2.5-coder:1.5b",
    ModelTier.EMBEDDING: "ollama/all-minilm",
}

# ---------------------------------------------------------------------------
# Provider → API key config field mapping
# ---------------------------------------------------------------------------
PROVIDER_KEY_MAP: dict[str, Optional[str]] = {
    "openai":      "openai_api_key",
    "anthropic":   "anthropic_api_key",
    "gemini":      "gemini_api_key",
    "groq":        "groq_api_key",
    "mistral":     "mistral_api_key",
    "deepseek":    "deepseek_api_key",
    "together":    "together_api_key",
    "perplexity":  "perplexity_api_key",
    "ollama":      None,   # No API key needed — fully offline
    "lmstudio":    None,   # No API key — local LM Studio server
    "jan":         None,   # No API key — local Jan AI server
    "llamacpp":    None,   # No API key — local llama.cpp server
    "lan_hosted":  None,   # LAN-hosted OpenAI-compatible server
}

# Task type → preferred provider routing
TASK_MODEL_ROUTING: dict[str, str] = {
    "code":         "deepseek",
    "creative":     "anthropic",
    "fast":         "groq",
    "web_search":   "perplexity",
    "vision":       "openai",
    "long_context": "gemini",
    "reasoning":    "deepseek",
    "general":      "openai",
    "offline":      "ollama",
}

# Zone / operating-mode → allowed providers
# LOCAL mode: only offline providers
# LAN mode: offline + any LAN-hosted providers
# WWW mode: all providers
ZONE_PROVIDER_POLICY: dict[str, list[str]] = {
    "local": ["ollama", "lmstudio", "jan", "llamacpp"],
    "lan":   ["ollama", "lmstudio", "jan", "llamacpp", "lan_hosted"],
    "www":   list(PROVIDER_KEY_MAP.keys()),
}
