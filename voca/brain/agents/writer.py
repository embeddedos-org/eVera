"""Writer Agent — drafts, edits, and formats text content."""

from __future__ import annotations

from voca.brain.agents.base import BaseAgent, Tool
from voca.providers.models import ModelTier


class WriterAgent(BaseAgent):
    """Drafts, edits, and formats text content."""

    name = "writer"
    description = "Drafts, edits, and formats text content"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a professional writing assistant. You draft emails, posts, notes, "
        "edit existing text, format documents, and translate content. Match the user's "
        "tone and style."
    )

    offline_responses = {
        "write": "✍️ I'd love to write that for you! Connect an LLM and I'll craft it perfectly 📝",
        "draft": "✍️ I'll draft that up! Connect an LLM and let's go! 📝",
        "edit": "✏️ I can help edit that! Connect an LLM for polishing ✨",
        "translate": "🌐 I'll translate that for you! Just need an LLM connection 🌍",
        "format": "📝 I'll format that nicely! Connect an LLM and we're good 👍",
        "compose": "✍️ I'll compose that! Connect an LLM to get started 🎵",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            Tool(
                name="draft_text",
                description="Draft text content",
                parameters={
                    "topic": {"type": "str", "description": "Topic or subject to write about"},
                    "style": {"type": "str", "description": "Writing style (formal, casual, etc.)"},
                    "length": {"type": "str", "description": "Desired length (short, medium, long)"},
                },
            ),
            Tool(
                name="edit_text",
                description="Edit/revise text",
                parameters={
                    "text": {"type": "str", "description": "Text to edit"},
                    "instruction": {"type": "str", "description": "Editing instruction"},
                },
            ),
            Tool(
                name="format_document",
                description="Format text (markdown, HTML, etc.)",
                parameters={
                    "text": {"type": "str", "description": "Text to format"},
                    "format": {"type": "str", "description": "Target format (markdown, html, plain)"},
                },
            ),
            Tool(
                name="translate",
                description="Translate text",
                parameters={
                    "text": {"type": "str", "description": "Text to translate"},
                    "target_language": {"type": "str", "description": "Target language"},
                },
            ),
        ]
