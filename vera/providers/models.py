"""Model tier definitions and configuration.

Supports 80+ models across 10+ providers with per-model metadata
for intelligent routing (context window, vision, tools, cost, speed).

Ollama models cover every family from the official library:
  General: Llama 3.x, Qwen 3/2.5/2, Gemma 4/3/2, Mistral, Phi-4/3/2,
           Command-R, Hermes 3, Cogito, Magistral, TinyLlama, SmolLM, GPT-OSS
  Reasoning: DeepSeek-R1, QwQ, Qwen3-reasoning
  Coding: Qwen2.5-Coder, Qwen3-Coder, Code Llama, Granite Code
  Vision: LLaVA, Llama 3.2 Vision, Qwen2.5-VL, MiniCPM-V, Gemma 3/4 vision
  Embedding: nomic-embed-text, mxbai-embed-large, qwen3-embedding
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum


class ModelTier(IntEnum):
    """LLM usage tiers — higher tier = more capable & expensive."""
    REFLEX = 0
    EXECUTOR = 1
    SPECIALIST = 2
    STRATEGIST = 3
    SPECIALIZED = 4  # Vision, code, web-search specialists


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a specific model."""
    tier: ModelTier
    model_name: str
    provider: str
    max_tokens: int = 1024
    temperature: float = 0.7
    description: str = ""
    context_window: int = 4096
    supports_vision: bool = False
    supports_tools: bool = False
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    speed_tier: str = "normal"  # "fast", "normal", "slow"
    task_types: tuple[str, ...] = ()
    # Zone restriction: "local"=offline only, "lan"=LAN+local, "www"=all zones
    min_zone: str = "local"  # Ollama models always work offline


# Default model configurations per tier — 80+ models across 10+ providers
DEFAULT_MODELS: dict[ModelTier, list[ModelConfig]] = {
    ModelTier.REFLEX: [],

    # ── EXECUTOR: Fast local Ollama models — all work 100% offline ──────────
    ModelTier.EXECUTOR: [
        # Llama family
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/llama3.2", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Llama 3.2 — recommended default offline",
                    context_window=8192, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/llama3.1:8b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Llama 3.1 8B — 128K context",
                    context_window=131072, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/llama3:8b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Llama 3 8B",
                    context_window=8192, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/llama2:7b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Llama 2 7B — lightweight",
                    context_window=4096, speed_tier="fast", task_types=("general",)),
        # Qwen family
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/qwen3:8b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Qwen 3 8B — best overall offline",
                    context_window=32768, speed_tier="fast", task_types=("general", "code")),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/qwen2.5:7b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Qwen 2.5 7B — excellent multilingual",
                    context_window=32768, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/qwen2:7b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Qwen 2 7B",
                    context_window=32768, speed_tier="fast", task_types=("general",)),
        # Gemma family
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/gemma4:4b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Gemma 4 4B — Google, very fast",
                    context_window=8192, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/gemma3:4b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Gemma 3 4B — Google",
                    context_window=8192, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/gemma2:9b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Gemma 2 9B",
                    context_window=8192, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/gemma:7b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Gemma 7B — original",
                    context_window=8192, speed_tier="fast", task_types=("general",)),
        # Mistral family
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/mistral:7b", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Mistral 7B — fast, efficient",
                    context_window=32768, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/mistral-nemo", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Mistral Nemo 12B",
                    context_window=128000, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/mistral-small3.2", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Mistral Small 3.2",
                    context_window=32768, speed_tier="fast", task_types=("general",)),
        # Phi family (Microsoft)
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/phi4", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Phi-4 — Microsoft, very capable",
                    context_window=16384, speed_tier="fast", task_types=("general", "code")),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/phi3", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Phi-3 — Microsoft",
                    context_window=4096, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/phi", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Phi-2 — tiny but capable",
                    context_window=2048, speed_tier="fast", task_types=("general",)),
        # Other general models
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/command-r", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Command-R — great for RAG",
                    context_window=128000, speed_tier="normal", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/hermes3", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Hermes 3 — great instruction following",
                    context_window=8192, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/cogito", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Cogito — reasoning-focused",
                    context_window=8192, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/magistral", provider="ollama",
                    max_tokens=512, temperature=0.3, description="Magistral — Mistral reasoning",
                    context_window=32768, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/tinyllama", provider="ollama",
                    max_tokens=256, temperature=0.3, description="TinyLlama — runs on any hardware",
                    context_window=2048, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/smollm", provider="ollama",
                    max_tokens=256, temperature=0.3, description="SmolLM — edge devices",
                    context_window=2048, speed_tier="fast", task_types=("general",)),
        ModelConfig(tier=ModelTier.EXECUTOR, model_name="ollama/gpt-oss", provider="ollama",
                    max_tokens=512, temperature=0.3, description="GPT-OSS — OpenAI open-source",
                    context_window=8192, speed_tier="fast", task_types=("general",)),
    ],

    # ── SPECIALIST: Cloud + large local models ───────────────────────────────
    ModelTier.SPECIALIST: [
        # OpenAI
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="gpt-4o-mini", provider="openai",
                    max_tokens=2048, temperature=0.7, description="GPT-4o mini — fast, affordable",
                    context_window=128000, supports_vision=True, supports_tools=True,
                    cost_per_1k_input=0.00015, cost_per_1k_output=0.0006,
                    speed_tier="fast", task_types=("general",), min_zone="www"),
        # Gemini
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="gemini/gemini-2.0-flash", provider="gemini",
                    max_tokens=2048, temperature=0.7, description="Gemini 2.0 Flash — very fast",
                    context_window=1048576, supports_vision=True, supports_tools=True,
                    speed_tier="fast", task_types=("general",), min_zone="www"),
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="gemini/gemini-1.5-pro", provider="gemini",
                    max_tokens=4096, temperature=0.7, description="Gemini 1.5 Pro — 2M context",
                    context_window=2097152, supports_vision=True, supports_tools=True,
                    cost_per_1k_input=0.00125, cost_per_1k_output=0.005,
                    speed_tier="normal", task_types=("general", "long_context"), min_zone="www"),
        # Anthropic
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="claude-sonnet-4-20250514", provider="anthropic",
                    max_tokens=4096, temperature=0.7, description="Claude Sonnet 4 — balanced",
                    context_window=200000, supports_vision=True, supports_tools=True,
                    cost_per_1k_input=0.003, cost_per_1k_output=0.015,
                    speed_tier="normal", task_types=("creative", "code", "analysis"), min_zone="www"),
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="claude-3-5-haiku-20241022", provider="anthropic",
                    max_tokens=2048, temperature=0.7, description="Claude 3.5 Haiku — fast",
                    context_window=200000, supports_vision=True, supports_tools=True,
                    cost_per_1k_input=0.001, cost_per_1k_output=0.005,
                    speed_tier="fast", task_types=("general",), min_zone="www"),
        # Groq
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="groq/llama-3.1-70b-versatile", provider="groq",
                    max_tokens=2048, temperature=0.7, description="Groq Llama 3.1 70B — ultra fast cloud",
                    context_window=131072, supports_tools=True,
                    cost_per_1k_input=0.00059, cost_per_1k_output=0.00079,
                    speed_tier="fast", task_types=("fast", "general"), min_zone="www"),
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="groq/mixtral-8x7b-32768", provider="groq",
                    max_tokens=2048, temperature=0.7, description="Groq Mixtral 8x7B",
                    context_window=32768, cost_per_1k_input=0.00027, cost_per_1k_output=0.00027,
                    speed_tier="fast", task_types=("fast",), min_zone="www"),
        # Mistral cloud
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="mistral/mistral-medium-latest", provider="mistral",
                    max_tokens=2048, temperature=0.7, description="Mistral Medium",
                    context_window=32768, supports_tools=True,
                    cost_per_1k_input=0.0027, cost_per_1k_output=0.0081,
                    speed_tier="normal", task_types=("general",), min_zone="www"),
        # Together AI
        ModelConfig(tier=ModelTier.SPECIALIST,
                    model_name="together_ai/meta-llama/Llama-3.1-70B-Instruct-Turbo", provider="together",
                    max_tokens=2048, temperature=0.7, description="Together Llama 3.1 70B",
                    context_window=131072, cost_per_1k_input=0.00088, cost_per_1k_output=0.00088,
                    speed_tier="normal", task_types=("general",), min_zone="www"),
        # DeepSeek cloud
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="deepseek/deepseek-chat", provider="deepseek",
                    max_tokens=4096, temperature=0.7, description="DeepSeek Chat V3",
                    context_window=65536, supports_tools=True,
                    cost_per_1k_input=0.00014, cost_per_1k_output=0.00028,
                    speed_tier="normal", task_types=("general", "code"), min_zone="www"),
        # Large Ollama models (need good GPU, still offline)
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="ollama/llama3.1:70b", provider="ollama",
                    max_tokens=2048, temperature=0.7, description="Llama 3.1 70B local — needs 48GB+ VRAM",
                    context_window=131072, speed_tier="slow", task_types=("general",)),
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="ollama/qwen3:32b", provider="ollama",
                    max_tokens=2048, temperature=0.7, description="Qwen 3 32B — best offline quality",
                    context_window=32768, speed_tier="normal", task_types=("general", "code")),
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="ollama/qwen2.5:32b", provider="ollama",
                    max_tokens=2048, temperature=0.7, description="Qwen 2.5 32B local",
                    context_window=32768, speed_tier="normal", task_types=("general",)),
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="ollama/gemma3:27b", provider="ollama",
                    max_tokens=2048, temperature=0.7, description="Gemma 3 27B — Google flagship local",
                    context_window=8192, speed_tier="normal", task_types=("general",)),
        ModelConfig(tier=ModelTier.SPECIALIST, model_name="ollama/command-r:35b", provider="ollama",
                    max_tokens=2048, temperature=0.7, description="Command-R 35B — excellent for RAG",
                    context_window=128000, speed_tier="normal", task_types=("general",)),
    ],

    # ── STRATEGIST: Flagship cloud + large local reasoning ───────────────────
    ModelTier.STRATEGIST: [
        # OpenAI flagship
        ModelConfig(tier=ModelTier.STRATEGIST, model_name="gpt-4o", provider="openai",
                    max_tokens=4096, temperature=0.8, description="GPT-4o — OpenAI flagship",
                    context_window=128000, supports_vision=True, supports_tools=True,
                    cost_per_1k_input=0.005, cost_per_1k_output=0.015,
                    speed_tier="normal", task_types=("general", "vision", "code"), min_zone="www"),
        # Anthropic flagship
        ModelConfig(tier=ModelTier.STRATEGIST, model_name="claude-3-opus-20240229", provider="anthropic",
                    max_tokens=4096, temperature=0.8, description="Claude 3 Opus — most capable Anthropic",
                    context_window=200000, supports_vision=True, supports_tools=True,
                    cost_per_1k_input=0.015, cost_per_1k_output=0.075,
                    speed_tier="slow", task_types=("creative", "analysis", "code"), min_zone="www"),
        # Gemini flagship
        ModelConfig(tier=ModelTier.STRATEGIST, model_name="gemini/gemini-2.5-pro", provider="gemini",
                    max_tokens=8192, temperature=0.8, description="Gemini 2.5 Pro — Google flagship",
                    context_window=1048576, supports_vision=True, supports_tools=True,
                    cost_per_1k_input=0.00125, cost_per_1k_output=0.01,
                    speed_tier="normal", task_types=("general", "long_context", "vision"), min_zone="www"),
        # Mistral flagship
        ModelConfig(tier=ModelTier.STRATEGIST, model_name="mistral/mistral-large-latest", provider="mistral",
                    max_tokens=4096, temperature=0.8, description="Mistral Large — most capable Mistral",
                    context_window=128000, supports_tools=True,
                    cost_per_1k_input=0.003, cost_per_1k_output=0.009,
                    speed_tier="normal", task_types=("general", "code"), min_zone="www"),
        # Reasoning models (Ollama — offline)
        ModelConfig(tier=ModelTier.STRATEGIST, model_name="ollama/deepseek-r1:7b", provider="ollama",
                    max_tokens=4096, temperature=0.6, description="DeepSeek-R1 7B — best offline reasoning",
                    context_window=65536, speed_tier="normal", task_types=("reasoning", "code")),
        ModelConfig(tier=ModelTier.STRATEGIST, model_name="ollama/deepseek-r1:32b", provider="ollama",
                    max_tokens=4096, temperature=0.6, description="DeepSeek-R1 32B — powerful reasoning",
                    context_window=65536, speed_tier="slow", task_types=("reasoning", "code")),
        ModelConfig(tier=ModelTier.STRATEGIST, model_name="ollama/qwq", provider="ollama",
                    max_tokens=4096, temperature=0.6, description="QwQ — Qwen reasoning model",
                    context_window=32768, speed_tier="slow", task_types=("reasoning",)),
        ModelConfig(tier=ModelTier.STRATEGIST, model_name="ollama/qwen3:32b-reasoning", provider="ollama",
                    max_tokens=4096, temperature=0.6, description="Qwen 3 32B reasoning variant",
                    context_window=32768, speed_tier="slow", task_types=("reasoning",)),
    ],

    # ── SPECIALIZED: Code, vision, web-search, embedding specialists ─────────
    ModelTier.SPECIALIZED: [
        # Coding specialists (Ollama — offline)
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/qwen2.5-coder:7b", provider="ollama",
                    max_tokens=4096, temperature=0.2, description="Qwen2.5-Coder 7B — best offline coder",
                    context_window=32768, speed_tier="fast", task_types=("code",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/qwen3-coder:8b", provider="ollama",
                    max_tokens=4096, temperature=0.2, description="Qwen3-Coder 8B — latest coding model",
                    context_window=32768, speed_tier="fast", task_types=("code",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/codellama:7b", provider="ollama",
                    max_tokens=4096, temperature=0.2, description="Code Llama 7B — Meta code specialist",
                    context_window=16384, speed_tier="fast", task_types=("code",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/granite-code:8b", provider="ollama",
                    max_tokens=4096, temperature=0.2, description="Granite Code 8B — IBM code specialist",
                    context_window=8192, speed_tier="fast", task_types=("code",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/deepseek-coder:6.7b", provider="ollama",
                    max_tokens=4096, temperature=0.3, description="DeepSeek Coder 6.7B local",
                    context_window=16384, speed_tier="fast", task_types=("code",)),
        # Cloud coding
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="deepseek/deepseek-coder", provider="deepseek",
                    max_tokens=8192, temperature=0.3, description="DeepSeek Coder — cloud code specialist",
                    context_window=65536, cost_per_1k_input=0.00014, cost_per_1k_output=0.00028,
                    speed_tier="normal", task_types=("code",), min_zone="www"),
        # Vision specialists (Ollama — offline)
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/llava:7b", provider="ollama",
                    max_tokens=2048, temperature=0.5, description="LLaVA 7B — vision offline",
                    context_window=4096, supports_vision=True, speed_tier="normal", task_types=("vision",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/llama3.2-vision:11b", provider="ollama",
                    max_tokens=2048, temperature=0.5, description="Llama 3.2 Vision 11B — best offline vision",
                    context_window=128000, supports_vision=True, speed_tier="normal", task_types=("vision",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/qwen2.5-vl:7b", provider="ollama",
                    max_tokens=2048, temperature=0.5, description="Qwen2.5-VL 7B — vision + language",
                    context_window=32768, supports_vision=True, speed_tier="normal", task_types=("vision",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/minicpm-v", provider="ollama",
                    max_tokens=2048, temperature=0.5, description="MiniCPM-V — compact vision model",
                    context_window=8192, supports_vision=True, speed_tier="fast", task_types=("vision",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/gemma3:12b-vision", provider="ollama",
                    max_tokens=2048, temperature=0.5, description="Gemma 3 12B vision variant",
                    context_window=8192, supports_vision=True, speed_tier="normal", task_types=("vision",)),
        # Cloud vision
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="gpt-4o", provider="openai",
                    max_tokens=4096, temperature=0.5, description="GPT-4o — best cloud vision",
                    context_window=128000, supports_vision=True, supports_tools=True,
                    cost_per_1k_input=0.005, cost_per_1k_output=0.015,
                    speed_tier="normal", task_types=("vision",), min_zone="www"),
        # Web search specialist
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="perplexity/pplx-70b-online", provider="perplexity",
                    max_tokens=4096, temperature=0.5, description="Perplexity 70B Online — live web search",
                    context_window=4096, cost_per_1k_input=0.001, cost_per_1k_output=0.001,
                    speed_tier="normal", task_types=("web_search",), min_zone="www"),
        # Embedding models (Ollama — offline)
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/nomic-embed-text", provider="ollama",
                    max_tokens=512, temperature=0.0, description="Nomic Embed Text — best offline embeddings",
                    context_window=8192, speed_tier="fast", task_types=("embedding",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/mxbai-embed-large", provider="ollama",
                    max_tokens=512, temperature=0.0, description="MXBAI Embed Large — high quality",
                    context_window=512, speed_tier="fast", task_types=("embedding",)),
        ModelConfig(tier=ModelTier.SPECIALIZED, model_name="ollama/qwen3-embedding", provider="ollama",
                    max_tokens=512, temperature=0.0, description="Qwen3 Embedding — multilingual",
                    context_window=8192, speed_tier="fast", task_types=("embedding",)),
    ],
}

# Provider → API key config field mapping
PROVIDER_KEY_MAP: dict[str, str] = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "gemini": "gemini_api_key",
    "groq": "groq_api_key",
    "mistral": "mistral_api_key",
    "deepseek": "deepseek_api_key",
    "together": "together_api_key",
    "perplexity": "perplexity_api_key",
    "ollama": None,  # No API key needed — always available offline
}

# Task type → preferred provider routing (offline-first)
TASK_MODEL_ROUTING: dict[str, str] = {
    "code": "ollama",
    "reasoning": "ollama",
    "creative": "anthropic",
    "fast": "groq",
    "web_search": "perplexity",
    "vision": "ollama",
    "long_context": "gemini",
    "general": "ollama",
    "embedding": "ollama",
}

# Zone → allowed providers mapping
# LOCAL: only Ollama (fully offline, no internet)
# LAN: Ollama + any LAN-hosted models
# WWW: all providers including cloud APIs
ZONE_PROVIDER_POLICY: dict[str, list[str]] = {
    "local": ["ollama"],
    "lan": ["ollama"],
    "www": ["ollama", "openai", "anthropic", "gemini", "groq", "mistral",
            "deepseek", "together", "perplexity"],
}
