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
        self._sessions: dict[str, list[Turn]] = {}

    def add(self, role: str, content: str, agent: str | None = None, metadata: dict | None = None, session_id: str | None = None) -> None:
        turn = Turn(role=role, content=content, agent=agent, metadata=metadata)
        if session_id:
            if session_id not in self._sessions:
                self._sessions[session_id] = []
            self._sessions[session_id].append(turn)
            if len(self._sessions[session_id]) > self._max_turns:
                self._sessions[session_id] = self._sessions[session_id][-self._max_turns:]
        self._turns.append(turn)
        if len(self._turns) > self._max_turns:
            self._turns = self._turns[-self._max_turns:]

    def get_context(self, session_id: str | None = None) -> list[dict[str, str]]:
        """Return conversation history in LLM message format."""
        turns = self._sessions.get(session_id, self._turns) if session_id else self._turns
        return [{"role": t.role, "content": t.content} for t in turns]

    def get_recent(self, n: int = 5, session_id: str | None = None) -> list[Turn]:
        turns = self._sessions.get(session_id, self._turns) if session_id else self._turns
        return turns[-n:]

    def get_last_agent(self, session_id: str | None = None) -> str | None:
        """Return the agent used in the most recent assistant turn."""
        turns = self._sessions.get(session_id, self._turns) if session_id else self._turns
        for turn in reversed(turns):
            if turn.role == "assistant" and turn.agent:
                return turn.agent
        return None

    def clear(self, session_id: str | None = None) -> None:
        if session_id and session_id in self._sessions:
            self._sessions[session_id].clear()
        else:
            self._turns.clear()
            self._sessions.clear()

    def remove_session(self, session_id: str) -> None:
        """Remove a session's conversation history."""
        self._sessions.pop(session_id, None)

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def __len__(self) -> int:
        return len(self._turns)
