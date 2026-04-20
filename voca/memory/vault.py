"""Memory Vault — facade orchestrating all memory layers.

@file voca/memory/vault.py
@brief Unified interface to eVoca's 4-layer memory system.

The MemoryVault facade provides a single API for querying and storing
data across Working (conversation buffer), Episodic (FAISS vectors),
Semantic (key-value facts), and Secure (Fernet-encrypted) memory layers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from config import settings
from voca.memory.episodic import EpisodicEvent, EpisodicMemory
from voca.memory.persistence import ConversationStore
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
    """Unified interface to all memory subsystems.

    Provides methods to enrich context for the current conversation,
    store interactions, remember/recall facts, and persist to disk.
    """

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
        self.conversation_store = ConversationStore(
            db_path=settings.data_dir / "conversations.db",
        )
        logger.info("MemoryVault initialized with all layers + persistence")

    def enrich(self, transcript: str, session_id: str | None = None) -> MemoryContext:
        """Query all memory layers to build context for the current transcript.

        @param transcript: The user's current input text.
        @param session_id: Optional session ID for per-session conversation history.
        @return MemoryContext aggregating conversation history, relevant episodes,
                user facts, and the last active agent.
        """
        ctx = MemoryContext(
            conversation=self.working.get_context(session_id=session_id),
            relevant_episodes=self.episodic.recall(transcript, k=3),
            user_facts=self.semantic.search(transcript),
            last_agent=self.working.get_last_agent(session_id=session_id),
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
        session_id: str | None = None,
    ) -> None:
        """Store a complete interaction across memory layers.

        Records the user-assistant exchange in both working memory
        (conversation buffer) and episodic memory (FAISS vector index).

        @param transcript: The user's input text.
        @param response: The assistant's response text.
        @param agent: Name of the agent that generated the response.
        @param metadata: Additional metadata to store with the episode.
        @param session_id: Optional session ID for per-session history.
        """
        # Working memory
        self.working.add("user", transcript, session_id=session_id)
        self.working.add("assistant", response, agent=agent, session_id=session_id)

        # Persist to SQLite
        sid = session_id or "default"
        self.conversation_store.save_turn("user", transcript, session_id=sid)
        self.conversation_store.save_turn("assistant", response, session_id=sid, agent=agent, metadata=metadata)

        # Episodic memory
        event_text = f"User: {transcript}\nAssistant ({agent or 'unknown'}): {response}"
        self.episodic.store(event_text, agent=agent, metadata=metadata or {})

    def remember_fact(self, key: str, value: str) -> None:
        self.semantic.remember(key, value)

    def recall_fact(self, key: str) -> str | None:
        return self.semantic.recall(key)

    def query(self, text: str, k: int = 5) -> list[EpisodicEvent]:
        return self.episodic.recall(text, k=k)

    def load_session(self, session_id: str) -> None:
        """Restore a session's conversation history from SQLite into working memory.

        @param session_id: Session ID to restore.
        """
        turns = self.conversation_store.load_turns(
            session_id=session_id,
            limit=self.working._max_turns,
        )
        for turn in turns:
            self.working.add(
                turn["role"],
                turn["content"],
                agent=turn.get("agent"),
                session_id=session_id,
            )
        if turns:
            logger.info("Restored %d turns for session %s", len(turns), session_id)

    def save_all(self) -> None:
        """Persist all memory layers to disk.

        Saves the FAISS index and semantic memory JSON to their
        configured file paths.
        """
        self.episodic.save_to_disk()
        self.semantic.save()
        logger.info("All memory layers saved to disk")

    def get_stats(self) -> dict[str, int]:
        """Return counts of items in each memory layer.

        @return Dictionary with working_turns, episodic_events, semantic_facts, and active_sessions.
        """
        return {
            "working_turns": self.working.turn_count,
            "episodic_events": self.episodic.count,
            "semantic_facts": self.semantic.count,
            "active_sessions": self.working.session_count,
        }
