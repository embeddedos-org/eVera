"""Working memory — current conversation context."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Turn:
    """A single conversation turn."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    agent: str | None = None
    metadata: dict | None = None


class WorkingMemory:
    """Short-term memory for the active conversation session."""

    def __init__(self, max_turns: int = 20) -> None:
        self._turns: list[Turn] = []
        self._max_turns = max_turns

    def add(self, role: str, content: str, agent: str | None = None, metadata: dict | None = None) -> None:
        turn = Turn(role=role, content=content, agent=agent, metadata=metadata)
        self._turns.append(turn)
        # Trim oldest turns if over limit
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns :]

    def get_context(self) -> list[dict[str, str]]:
        """Return conversation history in LLM message format."""
        return [{"role": t.role, "content": t.content} for t in self._turns]

    def get_recent(self, n: int = 5) -> list[Turn]:
        return self._turns[-n:]

    def get_last_agent(self) -> str | None:
        """Return the agent used in the most recent assistant turn."""
        for turn in reversed(self._turns):
            if turn.role == "assistant" and turn.agent:
                return turn.agent
        return None

    def clear(self) -> None:
        self._turns.clear()

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    def __len__(self) -> int:
        return len(self._turns)
