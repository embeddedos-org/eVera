"""
eVera Virtual LLM Router
========================
Automatically selects the best available model for each task type.
Priority: offline (Ollama/LM Studio/Jan) → LAN → cloud.
Falls back down the chain if a model is unavailable.

Task types and their preferred model capabilities:
  - coding       → deepseek-coder, qwen2.5-coder, codestral, granite-code
  - reasoning    → qwq, deepseek-r1, magistral, cogito
  - vision       → llava, minicpm-v, gemma3 (vision), gpt-4o, claude-3-5-sonnet
  - embedding    → mxbai-embed, nomic-embed, all-minilm
  - fast/reflex  → qwen3:0.6b, phi3.5-mini, smollm2
  - general      → qwen3:8b, llama3.3, mistral, gemma3
  - long_context → qwen3:14b, llama3.1:70b, claude-3-5-sonnet
  - creative     → mistral, llama3.3, claude-3-5-haiku
  - math         → qwq, deepseek-r1, magistral
  - search       → any www-mode model with tool_use capability
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger("evera.virtual_router")


class TaskType(str, Enum):
    GENERAL = "general"
    CODING = "coding"
    REASONING = "reasoning"
    VISION = "vision"
    EMBEDDING = "embedding"
    FAST = "fast"
    LONG_CONTEXT = "long_context"
    CREATIVE = "creative"
    MATH = "math"
    SEARCH = "search"


class Zone(str, Enum):
    LOCAL = "local"
    LAN = "lan"
    WWW = "www"


@dataclass
class ModelCandidate:
    """A model candidate with its priority and health status."""
    model_id: str
    provider: str          # "ollama" | "lmstudio" | "jan" | "llamacpp" | "openai" | "anthropic" | "google" | ...
    offline: bool          # True = no internet needed
    task_types: list[TaskType]
    priority: int          # lower = preferred
    context_length: int = 8192
    vision: bool = False
    embedding: bool = False
    last_checked: float = 0.0
    available: Optional[bool] = None  # None = unknown


# ── Candidate registry ────────────────────────────────────────────────────────
# Each entry: (model_id, provider, offline, task_types, priority, ctx_len, vision, embedding)
_CANDIDATES: list[ModelCandidate] = [
    # ── Ultra-fast offline (REFLEX tier) ──────────────────────────────────────
    ModelCandidate("qwen3:0.6b",         "ollama", True,  [TaskType.FAST, TaskType.GENERAL], 1, 8192),
    ModelCandidate("smollm2:135m",       "ollama", True,  [TaskType.FAST], 2, 4096),
    ModelCandidate("phi3.5:mini",        "ollama", True,  [TaskType.FAST, TaskType.GENERAL], 3, 8192),

    # ── Offline coding ────────────────────────────────────────────────────────
    ModelCandidate("qwen2.5-coder:7b",   "ollama", True,  [TaskType.CODING, TaskType.GENERAL], 10, 32768),
    ModelCandidate("deepseek-coder-v2",  "ollama", True,  [TaskType.CODING], 11, 32768),
    ModelCandidate("codestral:22b",      "ollama", True,  [TaskType.CODING], 12, 32768),
    ModelCandidate("granite-code:8b",    "ollama", True,  [TaskType.CODING], 13, 8192),
    ModelCandidate("qwen3-coder:8b",     "ollama", True,  [TaskType.CODING, TaskType.REASONING], 14, 32768),

    # ── Offline reasoning / math ──────────────────────────────────────────────
    ModelCandidate("qwq:32b",            "ollama", True,  [TaskType.REASONING, TaskType.MATH], 20, 32768),
    ModelCandidate("deepseek-r1:14b",    "ollama", True,  [TaskType.REASONING, TaskType.MATH], 21, 32768),
    ModelCandidate("magistral:24b",      "ollama", True,  [TaskType.REASONING, TaskType.MATH], 22, 32768),
    ModelCandidate("cogito:8b",          "ollama", True,  [TaskType.REASONING], 23, 8192),

    # ── Offline general ───────────────────────────────────────────────────────
    ModelCandidate("qwen3:8b",           "ollama", True,  [TaskType.GENERAL, TaskType.CREATIVE], 30, 32768),
    ModelCandidate("llama3.3:70b",       "ollama", True,  [TaskType.GENERAL, TaskType.LONG_CONTEXT], 31, 32768),
    ModelCandidate("mistral:7b",         "ollama", True,  [TaskType.GENERAL, TaskType.CREATIVE], 32, 8192),
    ModelCandidate("gemma3:9b",          "ollama", True,  [TaskType.GENERAL], 33, 8192),
    ModelCandidate("phi4:14b",           "ollama", True,  [TaskType.GENERAL, TaskType.REASONING], 34, 16384),

    # ── Offline vision ────────────────────────────────────────────────────────
    ModelCandidate("llava:13b",          "ollama", True,  [TaskType.VISION], 40, 4096, vision=True),
    ModelCandidate("minicpm-v:8b",       "ollama", True,  [TaskType.VISION], 41, 8192, vision=True),
    ModelCandidate("gemma3:9b",          "ollama", True,  [TaskType.VISION], 42, 8192, vision=True),

    # ── Offline embedding ─────────────────────────────────────────────────────
    ModelCandidate("mxbai-embed-large",  "ollama", True,  [TaskType.EMBEDDING], 50, 512, embedding=True),
    ModelCandidate("nomic-embed-text",   "ollama", True,  [TaskType.EMBEDDING], 51, 512, embedding=True),
    ModelCandidate("all-minilm:l6-v2",   "ollama", True,  [TaskType.EMBEDDING], 52, 512, embedding=True),

    # ── LM Studio / Jan (also offline, OpenAI-compatible) ────────────────────
    ModelCandidate("lmstudio/auto",      "lmstudio", True, [TaskType.GENERAL, TaskType.CODING], 60, 32768),
    ModelCandidate("jan/auto",           "jan",      True, [TaskType.GENERAL, TaskType.CODING], 61, 32768),
    ModelCandidate("llamacpp/auto",      "llamacpp", True, [TaskType.GENERAL, TaskType.CODING], 62, 32768),

    # ── Cloud fallbacks (www mode only) ──────────────────────────────────────
    ModelCandidate("gpt-4o",             "openai",    False, [TaskType.GENERAL, TaskType.VISION, TaskType.CODING, TaskType.REASONING], 100, 128000, vision=True),
    ModelCandidate("gpt-4o-mini",        "openai",    False, [TaskType.FAST, TaskType.GENERAL], 101, 128000),
    ModelCandidate("claude-3-5-sonnet",  "anthropic", False, [TaskType.GENERAL, TaskType.CODING, TaskType.CREATIVE, TaskType.LONG_CONTEXT], 102, 200000),
    ModelCandidate("claude-3-5-haiku",   "anthropic", False, [TaskType.FAST, TaskType.CREATIVE], 103, 200000),
    ModelCandidate("gemini-2.0-flash",   "google",    False, [TaskType.FAST, TaskType.GENERAL, TaskType.VISION], 104, 1000000, vision=True),
    ModelCandidate("gemini-2.5-pro",     "google",    False, [TaskType.REASONING, TaskType.LONG_CONTEXT, TaskType.MATH], 105, 1000000),
    ModelCandidate("gpt-4.1",            "openai",    False, [TaskType.CODING, TaskType.REASONING], 106, 1000000),
    ModelCandidate("o3-mini",            "openai",    False, [TaskType.REASONING, TaskType.MATH], 107, 200000),
]


# ── Health cache ──────────────────────────────────────────────────────────────
_HEALTH_CACHE_TTL = 60.0  # seconds before re-checking a model's availability


class VirtualRouter:
    """
    Selects the best available model for a given task type and zone.

    Usage:
        router = VirtualRouter(ollama_url="http://localhost:11434")
        model_id = await router.select(TaskType.CODING, zone=Zone.LOCAL)
    """

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        lmstudio_url: str = "http://localhost:1234",
        jan_url: str = "http://localhost:1337",
        llamacpp_url: str = "http://localhost:8080",
    ):
        self.ollama_url = ollama_url
        self.lmstudio_url = lmstudio_url
        self.jan_url = jan_url
        self.llamacpp_url = llamacpp_url
        self._candidates = list(_CANDIDATES)
        self._ollama_models: set[str] = set()
        self._ollama_checked_at: float = 0.0

    async def select(
        self,
        task_type: TaskType = TaskType.GENERAL,
        zone: Zone = Zone.LOCAL,
        require_vision: bool = False,
        require_embedding: bool = False,
        min_context: int = 0,
    ) -> str:
        """
        Returns the best model_id for the given task and zone.
        Falls back through the priority chain until one is available.
        """
        candidates = self._filter(
            task_type, zone, require_vision, require_embedding, min_context
        )
        for candidate in candidates:
            if await self._is_available(candidate):
                logger.info(
                    "[VirtualRouter] Selected %s (%s) for task=%s zone=%s",
                    candidate.model_id, candidate.provider, task_type, zone,
                )
                return candidate.model_id

        # Last resort: return the first offline candidate regardless of health
        offline = [c for c in self._candidates if c.offline]
        if offline:
            logger.warning("[VirtualRouter] All preferred models unavailable, using %s", offline[0].model_id)
            return offline[0].model_id

        return "qwen3:0.6b"  # absolute fallback

    def _filter(
        self,
        task_type: TaskType,
        zone: Zone,
        require_vision: bool,
        require_embedding: bool,
        min_context: int,
    ) -> list[ModelCandidate]:
        """Return candidates sorted by priority, filtered by zone and capabilities."""
        results = []
        for c in self._candidates:
            # Zone filter: LOCAL → offline only; LAN → offline + LAN; WWW → all
            if zone == Zone.LOCAL and not c.offline:
                continue
            if zone == Zone.LAN and not c.offline and c.provider not in ("lmstudio", "jan", "llamacpp"):
                continue
            # Capability filters
            if require_vision and not c.vision:
                continue
            if require_embedding and not c.embedding:
                continue
            if c.context_length < min_context:
                continue
            # Task type match
            if task_type in c.task_types or task_type == TaskType.GENERAL:
                results.append(c)

        results.sort(key=lambda c: c.priority)
        return results

    async def _is_available(self, candidate: ModelCandidate) -> bool:
        """Check if a model is reachable. Uses a TTL cache."""
        now = time.monotonic()
        if (
            candidate.available is not None
            and now - candidate.last_checked < _HEALTH_CACHE_TTL
        ):
            return candidate.available

        available = False
        try:
            if candidate.provider == "ollama":
                available = await self._check_ollama(candidate.model_id)
            elif candidate.provider == "lmstudio":
                available = await self._check_openai_compat(self.lmstudio_url)
            elif candidate.provider == "jan":
                available = await self._check_openai_compat(self.jan_url)
            elif candidate.provider == "llamacpp":
                available = await self._check_openai_compat(self.llamacpp_url)
            else:
                # Cloud providers — assume available if in WWW zone
                available = True
        except Exception:
            available = False

        candidate.available = available
        candidate.last_checked = now
        return available

    async def _check_ollama(self, model_id: str) -> bool:
        """Check if a specific Ollama model is pulled and available."""
        now = time.monotonic()
        if now - self._ollama_checked_at > _HEALTH_CACHE_TTL:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{self.ollama_url}/api/tags")
                    if resp.status_code == 200:
                        data = resp.json()
                        self._ollama_models = {
                            m["name"].split(":")[0] for m in data.get("models", [])
                        }
                        self._ollama_checked_at = now
            except Exception:
                return False

        base = model_id.split(":")[0]
        return base in self._ollama_models

    async def _check_openai_compat(self, base_url: str) -> bool:
        """Check if an OpenAI-compatible server is responding."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{base_url}/v1/models")
                return resp.status_code == 200
        except Exception:
            return False

    def classify_task(self, message: str) -> TaskType:
        """
        Heuristic task classifier — determines task type from the message text.
        Used when no explicit task_type is provided.
        """
        msg = message.lower()

        # Coding signals
        if any(w in msg for w in [
            "code", "function", "class", "debug", "fix bug", "implement",
            "python", "javascript", "typescript", "rust", "golang", "java",
            "sql", "html", "css", "api", "algorithm", "script", "program",
        ]):
            return TaskType.CODING

        # Reasoning / math signals
        if any(w in msg for w in [
            "reason", "think step", "analyze", "logic", "proof", "theorem",
            "calculate", "compute", "solve", "equation", "math", "formula",
            "step by step", "chain of thought",
        ]):
            return TaskType.REASONING

        # Vision signals
        if any(w in msg for w in [
            "image", "picture", "photo", "screenshot", "diagram", "chart",
            "what do you see", "describe this", "ocr", "read this image",
        ]):
            return TaskType.VISION

        # Embedding signals
        if any(w in msg for w in ["embed", "vector", "similarity", "semantic search"]):
            return TaskType.EMBEDDING

        # Fast / simple signals
        if len(msg.split()) < 8 and any(w in msg for w in [
            "hi", "hello", "thanks", "yes", "no", "ok", "sure", "what time",
            "what date", "who are you",
        ]):
            return TaskType.FAST

        # Long context signals
        if any(w in msg for w in [
            "summarize this document", "read this file", "entire codebase",
            "long text", "full document",
        ]):
            return TaskType.LONG_CONTEXT

        # Creative signals
        if any(w in msg for w in [
            "write a story", "poem", "creative", "fiction", "blog post",
            "marketing copy", "email draft", "persuasive",
        ]):
            return TaskType.CREATIVE

        return TaskType.GENERAL


# ── Singleton ─────────────────────────────────────────────────────────────────
_router: Optional[VirtualRouter] = None


def get_router(
    ollama_url: str = "http://localhost:11434",
    lmstudio_url: str = "http://localhost:1234",
    jan_url: str = "http://localhost:1337",
    llamacpp_url: str = "http://localhost:8080",
) -> VirtualRouter:
    global _router
    if _router is None:
        _router = VirtualRouter(ollama_url, lmstudio_url, jan_url, llamacpp_url)
    return _router
