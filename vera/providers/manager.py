"""Multi-provider LLM manager using litellm.

Supports 30+ models across 8+ providers with auto-routing,
health checks, and intelligent model selection.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import litellm

from config import settings
from vera.providers.models import (
    DEFAULT_MODELS,
    PROVIDER_KEY_MAP,
    TASK_MODEL_ROUTING,
    ModelConfig,
    ModelTier,
)

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
        self._provider_health: dict[str, bool] = {}
        self._configure_providers()

    def _configure_providers(self) -> None:
        """Set API keys from config into litellm and environment."""
        if settings.llm.openai_api_key:
            litellm.openai_key = settings.llm.openai_api_key
            os.environ["OPENAI_API_KEY"] = settings.llm.openai_api_key
        if settings.llm.gemini_api_key:
            litellm.gemini_key = settings.llm.gemini_api_key
            os.environ["GEMINI_API_KEY"] = settings.llm.gemini_api_key
        if settings.llm.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = settings.llm.anthropic_api_key
        if settings.llm.groq_api_key:
            os.environ["GROQ_API_KEY"] = settings.llm.groq_api_key
        if settings.llm.mistral_api_key:
            os.environ["MISTRAL_API_KEY"] = settings.llm.mistral_api_key
        if settings.llm.deepseek_api_key:
            os.environ["DEEPSEEK_API_KEY"] = settings.llm.deepseek_api_key
        if settings.llm.together_api_key:
            os.environ["TOGETHER_API_KEY"] = settings.llm.together_api_key
            os.environ["TOGETHERAI_API_KEY"] = settings.llm.together_api_key
        if settings.llm.perplexity_api_key:
            os.environ["PERPLEXITYAI_API_KEY"] = settings.llm.perplexity_api_key

    def _is_provider_configured(self, provider: str) -> bool:
        """Check if a provider has its API key configured."""
        if provider == "ollama":
            return True  # Always available (local)
        key_field = PROVIDER_KEY_MAP.get(provider)
        if not key_field:
            return False
        return bool(getattr(settings.llm, key_field, None))

    def get_models_for_tier(self, tier: ModelTier) -> list[ModelConfig]:
        return self._models.get(tier, [])

    def get_available_models(self) -> dict[str, list[dict[str, Any]]]:
        """Return all models grouped by provider with availability status."""
        by_provider: dict[str, list[dict[str, Any]]] = {}

        for tier in ModelTier:
            for model in self._models.get(tier, []):
                provider = model.provider
                if provider not in by_provider:
                    by_provider[provider] = []

                configured = self._is_provider_configured(provider)
                healthy = self._provider_health.get(provider, None)

                by_provider[provider].append(
                    {
                        "model_name": model.model_name,
                        "provider": provider,
                        "tier": tier.name,
                        "tier_value": int(tier),
                        "description": model.description,
                        "context_window": model.context_window,
                        "supports_vision": model.supports_vision,
                        "supports_tools": model.supports_tools,
                        "cost_per_1k_input": model.cost_per_1k_input,
                        "cost_per_1k_output": model.cost_per_1k_output,
                        "speed_tier": model.speed_tier,
                        "task_types": list(model.task_types),
                        "configured": configured,
                        "healthy": healthy,
                    }
                )

        return by_provider

    def select_model(self, task_type: str) -> ModelConfig | None:
        """Auto-select the best model for a given task type.

        Routes: code→DeepSeek, creative→Claude, fast→Groq,
        web_search→Perplexity, vision→GPT-4o.
        """
        preferred_provider = TASK_MODEL_ROUTING.get(task_type, "openai")

        # First try specialized tier
        for model in self._models.get(ModelTier.SPECIALIZED, []):
            if (
                task_type in model.task_types
                and model.provider == preferred_provider
                and self._is_provider_configured(model.provider)
            ):
                return model

        # Fall back to specialist/strategist tiers
        for tier in [ModelTier.SPECIALIST, ModelTier.STRATEGIST]:
            for model in self._models.get(tier, []):
                if task_type in model.task_types and self._is_provider_configured(model.provider):
                    return model

        # Fall back to any configured model
        for tier in [ModelTier.SPECIALIST, ModelTier.STRATEGIST, ModelTier.EXECUTOR]:
            for model in self._models.get(tier, []):
                if self._is_provider_configured(model.provider):
                    return model

        return None

    async def provider_health_check(self) -> dict[str, dict[str, Any]]:
        """Check health of all configured providers."""
        results: dict[str, dict[str, Any]] = {}

        for provider in PROVIDER_KEY_MAP:
            if not self._is_provider_configured(provider):
                results[provider] = {"status": "not_configured", "latency_ms": None}
                self._provider_health[provider] = False
                continue

            # Find a model for this provider
            test_model = None
            for tier in ModelTier:
                for model in self._models.get(tier, []):
                    if model.provider == provider:
                        test_model = model
                        break
                if test_model:
                    break

            if not test_model:
                results[provider] = {"status": "no_models", "latency_ms": None}
                continue

            start = time.monotonic()
            try:
                kwargs: dict[str, Any] = {
                    "model": test_model.model_name,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                    "temperature": 0,
                }
                if provider == "ollama":
                    kwargs["api_base"] = settings.llm.ollama_url

                await litellm.acompletion(**kwargs)
                latency = (time.monotonic() - start) * 1000
                results[provider] = {"status": "healthy", "latency_ms": round(latency)}
                self._provider_health[provider] = True
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                results[provider] = {
                    "status": "unhealthy",
                    "latency_ms": round(latency),
                    "error": str(e)[:200],
                }
                self._provider_health[provider] = False

        return results

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tier: ModelTier,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[dict[str, Any]] | None = None,
        model_override: str | None = None,
    ) -> CompletionResult:
        """Route completion request to appropriate model with fallback.

        @param model_override: If set, use this specific model name instead of tier routing.
        """
        if tier == ModelTier.REFLEX:
            raise ValueError("Tier 0 (REFLEX) does not use LLM — handle with regex/rules")

        # If model_override is specified, find it in our registry or use it directly
        if model_override:
            override_config = self._find_model(model_override)
            if override_config:
                return await self._call_model(messages, override_config, max_tokens, temperature, tools)
            # Use it as a raw model name via litellm
            raw_config = ModelConfig(
                tier=tier,
                model_name=model_override,
                provider="unknown",
                max_tokens=max_tokens or 2048,
                temperature=temperature or 0.7,
            )
            return await self._call_model(messages, raw_config, max_tokens, temperature, tools)

        models = self._get_available_models_for_tier(tier)
        if not models:
            for fallback_tier in ModelTier:
                if fallback_tier > tier:
                    models = self._get_available_models_for_tier(fallback_tier)
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
                # Record LLM error for monitoring
                from vera.monitoring import metrics as mon_metrics

                mon_metrics.record_llm_call(
                    provider=model_config.provider,
                    model=model_config.model_name,
                    tier=model_config.tier.name,
                    tokens=0,
                    latency_ms=0,
                    error=True,
                )
                last_error = e
                continue

        raise RuntimeError(f"All models failed for tier {tier}: {last_error}")

    def _find_model(self, model_name: str) -> ModelConfig | None:
        """Find a model by name across all tiers."""
        for tier in ModelTier:
            for model in self._models.get(tier, []):
                if model.model_name == model_name:
                    return model
        return None

    def _get_available_models_for_tier(self, tier: ModelTier) -> list[ModelConfig]:
        """Get models for a tier, filtered to only configured providers."""
        models = self._models.get(tier, [])
        available = [m for m in models if self._is_provider_configured(m.provider)]
        if available:
            return available
        return models  # Return all if none configured (litellm will handle errors)

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

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await litellm.acompletion(**kwargs)
        elapsed_ms = (time.monotonic() - start) * 1000

        message = response.choices[0].message
        content = message.content or ""
        usage = response.usage

        parsed_tool_calls = None
        if hasattr(message, "tool_calls") and message.tool_calls:
            import json

            parsed_tool_calls = []
            for tc in message.tool_calls:
                try:
                    args = (
                        json.loads(tc.function.arguments)
                        if isinstance(tc.function.arguments, str)
                        else tc.function.arguments
                    )
                except (json.JSONDecodeError, AttributeError):
                    args = {}
                parsed_tool_calls.append(
                    ToolCall(
                        id=tc.id or "",
                        name=tc.function.name,
                        arguments=args or {},
                    )
                )

        tier_usage = self._usage[model_config.tier]
        tier_usage.prompt_tokens += usage.prompt_tokens
        tier_usage.completion_tokens += usage.completion_tokens
        tier_usage.call_count += 1

        # Record metrics for monitoring
        from vera.monitoring import metrics as mon_metrics

        mon_metrics.record_llm_call(
            provider=model_config.provider,
            model=model_config.model_name,
            tier=model_config.tier.name,
            tokens=usage.total_tokens,
            latency_ms=elapsed_ms,
            error=False,
        )

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

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tier: ModelTier,
        max_tokens: int | None = None,
        temperature: float | None = None,
        model_override: str | None = None,
    ):
        """Stream completion tokens from the LLM."""
        if tier == ModelTier.REFLEX:
            raise ValueError("Tier 0 (REFLEX) does not use LLM")

        if model_override:
            override_config = self._find_model(model_override)
            if override_config:
                async for chunk in self._stream_model(messages, override_config, max_tokens, temperature):
                    yield chunk
                return

        models = self._get_available_models_for_tier(tier)
        if not models:
            for fallback_tier in ModelTier:
                if fallback_tier > tier:
                    models = self._get_available_models_for_tier(fallback_tier)
                    if models:
                        break

        if not models:
            raise RuntimeError(f"No models available for tier {tier} or higher")

        last_error: Exception | None = None
        for model_config in models:
            try:
                async for chunk in self._stream_model(messages, model_config, max_tokens, temperature):
                    yield chunk
                return
            except Exception as e:
                logger.warning("Streaming model %s failed: %s", model_config.model_name, e)
                last_error = e
                continue

        raise RuntimeError(f"All streaming models failed for tier {tier}: {last_error}")

    async def _stream_model(
        self,
        messages: list[dict[str, Any]],
        model_config: ModelConfig,
        max_tokens: int | None,
        temperature: float | None,
    ):
        """Stream from a specific model."""
        kwargs: dict = {
            "model": model_config.model_name,
            "messages": messages,
            "max_tokens": max_tokens or model_config.max_tokens,
            "temperature": temperature if temperature is not None else model_config.temperature,
            "stream": True,
        }
        if model_config.provider == "ollama":
            kwargs["api_base"] = settings.llm.ollama_url

        response = await litellm.acompletion(**kwargs)

        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
