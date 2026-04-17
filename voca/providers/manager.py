"""Multi-provider LLM manager using litellm."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import litellm

from config import settings
from voca.providers.models import DEFAULT_MODELS, ModelConfig, ModelTier

logger = logging.getLogger(__name__)

litellm.set_verbose = False


@dataclass
class TokenUsage:
    """Tracks token usage per tier."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0
    call_count: int = 0


@dataclass
class ToolCall:
    """A tool call from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class CompletionResult:
    """Result from an LLM completion call."""

    content: str
    model: str
    tier: ModelTier
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    tool_calls: list[ToolCall] | None = None


class ProviderManager:
    """Manages LLM providers with tiered routing and fallback."""

    def __init__(self) -> None:
        self._models = dict(DEFAULT_MODELS)
        self._usage: dict[ModelTier, TokenUsage] = {tier: TokenUsage() for tier in ModelTier}
        self._configure_providers()

    def _configure_providers(self) -> None:
        """Set API keys from config."""
        if settings.llm.openai_api_key:
            litellm.openai_key = settings.llm.openai_api_key
        if settings.llm.gemini_api_key:
            litellm.gemini_key = settings.llm.gemini_api_key

    def get_models_for_tier(self, tier: ModelTier) -> list[ModelConfig]:
        return self._models.get(tier, [])

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tier: ModelTier,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResult:
        """Route completion request to appropriate model with fallback."""
        if tier == ModelTier.REFLEX:
            raise ValueError("Tier 0 (REFLEX) does not use LLM — handle with regex/rules")

        models = self.get_models_for_tier(tier)
        if not models:
            for fallback_tier in ModelTier:
                if fallback_tier > tier:
                    models = self.get_models_for_tier(fallback_tier)
                    if models:
                        logger.warning("No models for tier %s, escalating to %s", tier, fallback_tier)
                        break

        if not models:
            raise RuntimeError(f"No models available for tier {tier} or higher")

        last_error: Exception | None = None
        for model_config in models:
            try:
                return await self._call_model(messages, model_config, max_tokens, temperature, tools)
            except Exception as e:
                logger.warning("Model %s failed: %s", model_config.model_name, e)
                last_error = e
                continue

        raise RuntimeError(f"All models failed for tier {tier}: {last_error}")

    async def _call_model(
        self,
        messages: list[dict[str, Any]],
        model_config: ModelConfig,
        max_tokens: int | None,
        temperature: float | None,
        tools: list[dict[str, Any]] | None = None,
    ) -> CompletionResult:
        """Call a specific model via litellm with optional tool/function calling."""
        start = time.monotonic()

        kwargs: dict = {
            "model": model_config.model_name,
            "messages": messages,
            "max_tokens": max_tokens or model_config.max_tokens,
            "temperature": temperature if temperature is not None else model_config.temperature,
        }

        if model_config.provider == "ollama":
            kwargs["api_base"] = settings.llm.ollama_url

        # Add tools for native function calling
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await litellm.acompletion(**kwargs)
        elapsed_ms = (time.monotonic() - start) * 1000

        message = response.choices[0].message
        content = message.content or ""
        usage = response.usage

        # Parse native tool calls
        parsed_tool_calls = None
        if hasattr(message, "tool_calls") and message.tool_calls:
            import json
            parsed_tool_calls = []
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                except (json.JSONDecodeError, AttributeError):
                    args = {}
                parsed_tool_calls.append(ToolCall(
                    id=tc.id or "",
                    name=tc.function.name,
                    arguments=args or {},
                ))

        # Track usage
        tier_usage = self._usage[model_config.tier]
        tier_usage.prompt_tokens += usage.prompt_tokens
        tier_usage.completion_tokens += usage.completion_tokens
        tier_usage.call_count += 1

        logger.info(
            "LLM call: model=%s tier=%s tokens=%d latency=%.0fms tools=%s",
            model_config.model_name,
            model_config.tier.name,
            usage.total_tokens,
            elapsed_ms,
            len(parsed_tool_calls) if parsed_tool_calls else 0,
        )

        return CompletionResult(
            content=content,
            model=model_config.model_name,
            tier=model_config.tier,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            latency_ms=elapsed_ms,
            tool_calls=parsed_tool_calls,
        )

    def get_usage(self) -> dict[str, TokenUsage]:
        return {tier.name: usage for tier, usage in self._usage.items()}
