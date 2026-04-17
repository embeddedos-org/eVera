"""VocaState — shared state for the LangGraph supervisor-worker graph."""

from __future__ import annotations

from typing import Any, TypedDict


class VocaState(TypedDict, total=False):
    """State flowing through the LangGraph pipeline."""

    # Input
    transcript: str
    session_id: str

    # User identity
    user_name: str

    # Classification
    intent: str
    tier: int  # ModelTier value
    agent_name: str
    confidence: float

    # Memory context
    memory_context: dict[str, Any]
    conversation_history: list[dict[str, str]]

    # Agent execution
    agent_response: str
    tool_results: list[dict[str, Any]]
    mood: str  # happy, thinking, excited, neutral, empathetic, error

    # Safety
    safety_approved: bool
    needs_confirmation: bool
    pending_action: dict[str, Any]

    # Output
    final_response: str
    metadata: dict[str, Any]
