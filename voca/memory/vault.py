"""Memory Vault — facade orchestrating all memory layers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import settings
from voca.memory.episodic import EpisodicEvent, EpisodicMemory
from voca.memory.secure import SecureVault
from voca.memory.semantic import SemanticMemory
from voca.memory.working import WorkingMemory

logger = logging.getLogger(__name__)


@dataclass
class MemoryContext:
    """Aggregated context from all memory layers."""

    conversation: list[dict[str, str]] = field(default_factory=list)
    relevant_episodes: list[EpisodicEvent] = field(default_factory=list)
    user_facts: dict[str, str] = field(default_factory=dict)
    last_agent: str | None = None


class MemoryVault:
    """Unified interface to all memory subsystems."""

    def __init__(self) -> None:
        self.working = WorkingMemory(
            max_turns=settings.memory.working_memory_max_turns,
        )
        self.episodic = EpisodicMemory(
            model_name=settings.memory.embedding_model,
            index_path=settings.memory.faiss_index_path,
        )
        self.semantic = SemanticMemory(
            store_path=settings.memory.semantic_store_path,
        )
        self.secure = SecureVault(
            vault_path=settings.memory.secure_vault_path,
        )
        logger.info("MemoryVault initialized with all layers")

    def enrich(self, transcript: str) -> MemoryContext:
        """Query all memory layers to build context for the current transcript."""
        ctx = MemoryContext(
            conversation=self.working.get_context(),
            relevant_episodes=self.episodic.recall(transcript, k=3),
            user_facts=self.semantic.search(transcript),
            last_agent=self.working.get_last_agent(),
        )
        logger.debug(
            "Enriched context: %d turns, %d episodes, %d facts",
            len(ctx.conversation),
            len(ctx.relevant_episodes),
            len(ctx.user_facts),
        )
        return ctx

    def store_interaction(
        self,
        transcript: str,
        response: str,
        agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a complete interaction across memory layers."""
        # Working memory
        self.working.add("user", transcript)
        self.working.add("assistant", response, agent=agent)

        # Episodic memory
        event_text = f"User: {transcript}\nAssistant ({agent or 'unknown'}): {response}"
        self.episodic.store(event_text, agent=agent, metadata=metadata or {})

    def remember_fact(self, key: str, value: str) -> None:
        self.semantic.remember(key, value)

    def recall_fact(self, key: str) -> str | None:
        return self.semantic.recall(key)

    def query(self, text: str, k: int = 5) -> list[EpisodicEvent]:
        return self.episodic.recall(text, k=k)

    def save_all(self) -> None:
        """Persist all memory layers to disk."""
        self.episodic.save_to_disk()
        self.semantic.save()
        logger.info("All memory layers saved to disk")

    def get_stats(self) -> dict[str, int]:
        return {
            "working_turns": self.working.turn_count,
            "episodic_events": self.episodic.count,
            "semantic_facts": self.semantic.count,
        }
