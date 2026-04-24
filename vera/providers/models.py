"""Model tier definitions and configuration.

Supports 30+ models across 8+ providers with per-model metadata
for intelligent routing (context window, vision, tools, cost, speed).
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
    task_types: tuple[str, ...] = ()  # e.g. ("code", "creative", "fast", "vision", "web_search")


# Default model configurations per tier — 30+ models across 8+ providers
DEFAULT_MODELS: dict[ModelTier, list[ModelConfig]] = {
    ModelTier.REFLEX: [],
    ModelTier.EXECUTOR: [
        ModelConfig(
            tier=ModelTier.EXECUTOR,
            model_name="ollama/llama3.2",
            provider="ollama",
            max_tokens=512,
            temperature=0.3,
            description="Fast local model for simple tasks",
            context_window=8192,
            speed_tier="fast",
        ),
        ModelConfig(
            tier=ModelTier.EXECUTOR,
            model_name="ollama/llama3.1:8b",
            provider="ollama",
            max_tokens=512,
            temperature=0.3,
            description="Llama 3.1 8B local",
            context_window=131072,
            speed_tier="fast",
        ),
        ModelConfig(
            tier=ModelTier.EXECUTOR,
            model_name="ollama/mistral:7b",
            provider="ollama",
            max_tokens=512,
            temperature=0.3,
            description="Mistral 7B local",
            context_window=32768,
            speed_tier="fast",
        ),
        ModelConfig(
            tier=ModelTier.EXECUTOR,
            model_name="ollama/phi-3",
            provider="ollama",
            max_tokens=512,
            temperature=0.3,
            description="Microsoft Phi-3 local",
            context_window=4096,
            speed_tier="fast",
        ),
    ],
    ModelTier.SPECIALIST: [
        # OpenAI
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="gpt-4o-mini",
            provider="openai",
            max_tokens=2048,
            temperature=0.7,
            description="Fast, affordable GPT-4o mini",
            context_window=128000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            speed_tier="fast",
            task_types=("general",),
        ),
        # Gemini
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="gemini/gemini-2.0-flash",
            provider="gemini",
            max_tokens=2048,
            temperature=0.7,
            description="Google Gemini 2.0 Flash",
            context_window=1048576,
            supports_vision=True,
            supports_tools=True,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            speed_tier="fast",
            task_types=("general",),
        ),
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="gemini/gemini-1.5-pro",
            provider="gemini",
            max_tokens=4096,
            temperature=0.7,
            description="Google Gemini 1.5 Pro",
            context_window=2097152,
            supports_vision=True,
            supports_tools=True,
            cost_per_1k_input=0.00125,
            cost_per_1k_output=0.005,
            speed_tier="normal",
            task_types=("general", "long_context"),
        ),
        # Anthropic
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="claude-sonnet-4-20250514",
            provider="anthropic",
            max_tokens=4096,
            temperature=0.7,
            description="Claude Sonnet 4 — balanced",
            context_window=200000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            speed_tier="normal",
            task_types=("creative", "code", "analysis"),
        ),
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="claude-3-5-haiku-20241022",
            provider="anthropic",
            max_tokens=2048,
            temperature=0.7,
            description="Claude 3.5 Haiku — fast & affordable",
            context_window=200000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.005,
            speed_tier="fast",
            task_types=("general",),
        ),
        # Groq (fast inference)
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="groq/llama-3.1-70b-versatile",
            provider="groq",
            max_tokens=2048,
            temperature=0.7,
            description="Groq Llama 3.1 70B — ultra fast",
            context_window=131072,
            supports_tools=True,
            cost_per_1k_input=0.00059,
            cost_per_1k_output=0.00079,
            speed_tier="fast",
            task_types=("fast", "general"),
        ),
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="groq/mixtral-8x7b-32768",
            provider="groq",
            max_tokens=2048,
            temperature=0.7,
            description="Groq Mixtral 8x7B — fast inference",
            context_window=32768,
            cost_per_1k_input=0.00027,
            cost_per_1k_output=0.00027,
            speed_tier="fast",
            task_types=("fast",),
        ),
        # Mistral
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="mistral/mistral-medium-latest",
            provider="mistral",
            max_tokens=2048,
            temperature=0.7,
            description="Mistral Medium",
            context_window=32768,
            supports_tools=True,
            cost_per_1k_input=0.0027,
            cost_per_1k_output=0.0081,
            speed_tier="normal",
            task_types=("general",),
        ),
        # Together AI
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="together_ai/meta-llama/Llama-3.1-70B-Instruct-Turbo",
            provider="together",
            max_tokens=2048,
            temperature=0.7,
            description="Together Llama 3.1 70B",
            context_window=131072,
            cost_per_1k_input=0.00088,
            cost_per_1k_output=0.00088,
            speed_tier="normal",
            task_types=("general",),
        ),
        # DeepSeek
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="deepseek/deepseek-chat",
            provider="deepseek",
            max_tokens=4096,
            temperature=0.7,
            description="DeepSeek Chat V3",
            context_window=65536,
            supports_tools=True,
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            speed_tier="normal",
            task_types=("general", "code"),
        ),
    ],
    ModelTier.STRATEGIST: [
        # OpenAI flagship
        ModelConfig(
            tier=ModelTier.STRATEGIST,
            model_name="gpt-4o",
            provider="openai",
            max_tokens=4096,
            temperature=0.8,
            description="GPT-4o — most capable OpenAI model",
            context_window=128000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
            speed_tier="normal",
            task_types=("general", "vision", "code"),
        ),
        # Anthropic flagship
        ModelConfig(
            tier=ModelTier.STRATEGIST,
            model_name="claude-3-opus-20240229",
            provider="anthropic",
            max_tokens=4096,
            temperature=0.8,
            description="Claude 3 Opus — most capable Anthropic model",
            context_window=200000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1k_input=0.015,
            cost_per_1k_output=0.075,
            speed_tier="slow",
            task_types=("creative", "analysis", "code"),
        ),
        # Gemini flagship
        ModelConfig(
            tier=ModelTier.STRATEGIST,
            model_name="gemini/gemini-2.5-pro",
            provider="gemini",
            max_tokens=8192,
            temperature=0.8,
            description="Gemini 2.5 Pro — Google flagship",
            context_window=1048576,
            supports_vision=True,
            supports_tools=True,
            cost_per_1k_input=0.00125,
            cost_per_1k_output=0.01,
            speed_tier="normal",
            task_types=("general", "long_context", "vision"),
        ),
        # Mistral flagship
        ModelConfig(
            tier=ModelTier.STRATEGIST,
            model_name="mistral/mistral-large-latest",
            provider="mistral",
            max_tokens=4096,
            temperature=0.8,
            description="Mistral Large — most capable Mistral model",
            context_window=128000,
            supports_tools=True,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.009,
            speed_tier="normal",
            task_types=("general", "code"),
        ),
    ],
    ModelTier.SPECIALIZED: [
        # Code specialist
        ModelConfig(
            tier=ModelTier.SPECIALIZED,
            model_name="deepseek/deepseek-coder",
            provider="deepseek",
            max_tokens=8192,
            temperature=0.3,
            description="DeepSeek Coder — code specialist",
            context_window=65536,
            cost_per_1k_input=0.00014,
            cost_per_1k_output=0.00028,
            speed_tier="normal",
            task_types=("code",),
        ),
        ModelConfig(
            tier=ModelTier.SPECIALIZED,
            model_name="ollama/deepseek-coder:6.7b",
            provider="ollama",
            max_tokens=4096,
            temperature=0.3,
            description="DeepSeek Coder 6.7B local",
            context_window=16384,
            speed_tier="fast",
            task_types=("code",),
        ),
        # Vision specialist
        ModelConfig(
            tier=ModelTier.SPECIALIZED,
            model_name="gpt-4o",
            provider="openai",
            max_tokens=4096,
            temperature=0.5,
            description="GPT-4o vision specialist",
            context_window=128000,
            supports_vision=True,
            supports_tools=True,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
            speed_tier="normal",
            task_types=("vision",),
        ),
        # Web search specialist
        ModelConfig(
            tier=ModelTier.SPECIALIZED,
            model_name="perplexity/pplx-70b-online",
            provider="perplexity",
            max_tokens=4096,
            temperature=0.5,
            description="Perplexity 70B Online — web search specialist",
            context_window=4096,
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.001,
            speed_tier="normal",
            task_types=("web_search",),
        ),
        # Large context Ollama
        ModelConfig(
            tier=ModelTier.SPECIALIZED,
            model_name="ollama/llama3.1:70b",
            provider="ollama",
            max_tokens=4096,
            temperature=0.7,
            description="Llama 3.1 70B local — needs strong GPU",
            context_window=131072,
            speed_tier="slow",
            task_types=("general",),
        ),
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
    "ollama": None,  # No API key needed
}

# Task type → preferred provider routing
TASK_MODEL_ROUTING: dict[str, str] = {
    "code": "deepseek",
    "creative": "anthropic",
    "fast": "groq",
    "web_search": "perplexity",
    "vision": "openai",
    "long_context": "gemini",
    "general": "openai",
}
