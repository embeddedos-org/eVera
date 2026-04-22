"""Model tier definitions and configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ModelTier(IntEnum):
    """LLM usage tiers — higher tier = more capable & expensive."""

    REFLEX = 0  # No LLM — regex/rule-based
    EXECUTOR = 1  # Local Ollama — fast, cheap
    SPECIALIST = 2  # Cloud LLM — capable
    STRATEGIST = 3  # Cloud LLM chain — most powerful


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a specific model."""

    tier: ModelTier
    model_name: str
    provider: str  # "ollama", "openai", "gemini"
    max_tokens: int = 1024
    temperature: float = 0.7
    description: str = ""


# Default model configurations per tier
DEFAULT_MODELS: dict[ModelTier, list[ModelConfig]] = {
    ModelTier.REFLEX: [],  # No LLM needed
    ModelTier.EXECUTOR: [
        ModelConfig(
            tier=ModelTier.EXECUTOR,
            model_name="ollama/llama3.2",
            provider="ollama",
            max_tokens=512,
            temperature=0.3,
            description="Fast local model for simple tasks",
        ),
    ],
    ModelTier.SPECIALIST: [
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="gpt-4o-mini",
            provider="openai",
            max_tokens=2048,
            temperature=0.7,
            description="Cloud model for complex tasks",
        ),
        ModelConfig(
            tier=ModelTier.SPECIALIST,
            model_name="gemini/gemini-2.0-flash",
            provider="gemini",
            max_tokens=2048,
            temperature=0.7,
            description="Gemini fallback for complex tasks",
        ),
    ],
    ModelTier.STRATEGIST: [
        ModelConfig(
            tier=ModelTier.STRATEGIST,
            model_name="gpt-4o",
            provider="openai",
            max_tokens=4096,
            temperature=0.8,
            description="Most capable model for multi-step reasoning",
        ),
    ],
}
