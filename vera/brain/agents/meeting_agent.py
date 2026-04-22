"""Meeting Agent — meeting notes parsing, action item extraction, task creation.

@file vera/brain/agents/meeting_agent.py
@brief Processes meeting transcripts/notes to extract structured action items,
decisions, and summaries. Optionally creates todos and Jira tickets.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

EXTRACTION_PROMPT = """\
You are an expert meeting analyst. Extract structured information from the following meeting notes/transcript.

Return ONLY a valid JSON object with this structure (no markdown):
{
  "summary": "Brief 2-3 sentence summary of the meeting",
  "participants": ["person1", "person2"],
  "decisions": ["decision 1", "decision 2"],
  "action_items": [
    {
      "assignee": "person name or 'unassigned'",
      "task": "clear description of what needs to be done",
      "deadline": "YYYY-MM-DD or 'none'",
      "priority": "high/medium/low"
    }
  ],
  "key_topics": ["topic1", "topic2"],
  "follow_ups": ["any follow-up meetings or check-ins needed"]
}

Meeting Notes:
"""


class ExtractActionItemsTool(Tool):
    def __init__(self):
        super().__init__(
            name="extract_action_items",
            description="Extract action items from meeting notes or transcript text",
            parameters={"text": {"type": "str", "description": "Meeting notes or transcript text"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        text = kwargs.get("text", "")
        if not text:
            return {"status": "error", "message": "text is required — paste meeting notes or transcript"}

        try:
            from vera.providers.manager import ProviderManager

            provider = ProviderManager()
            result = await provider.complete(
                messages=[
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": text},
                ],
                tier=ModelTier.SPECIALIST,
                temperature=0.2,
            )

            parsed = json.loads(result.content.strip())
            return {
                "status": "success",
                "summary": parsed.get("summary", ""),
                "action_items": parsed.get("action_items", []),
                "decisions": parsed.get("decisions", []),
                "participants": parsed.get("participants", []),
            }
        except json.JSONDecodeError:
            return {"status": "error", "message": "Failed to parse LLM response as JSON"}
        except Exception as e:
            return {"status": "error", "message": f"Extraction failed: {e}"}


class ParseMeetingNotesTool(Tool):
    def __init__(self):
        super().__init__(
            name="parse_meeting_notes",
            description="Parse and structure meeting notes into a comprehensive format",
            parameters={
                "text": {"type": "str", "description": "Meeting notes or transcript"},
                "format": {"type": "str", "description": "Output format: structured (default), markdown, or brief"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        text = kwargs.get("text", "")
        output_format = kwargs.get("format", "structured")
        if not text:
            return {"status": "error", "message": "text is required"}

        try:
            from vera.providers.manager import ProviderManager

            provider = ProviderManager()

            format_instructions = {
                "structured": "Return a detailed JSON object with all extracted fields.",
                "markdown": "Return well-formatted markdown with headers for Summary, Decisions, Action Items, and Follow-ups.",
                "brief": "Return a concise JSON with just summary and action_items.",
            }

            result = await provider.complete(
                messages=[
                    {
                        "role": "system",
                        "content": EXTRACTION_PROMPT
                        + f"\n\nFormat: {format_instructions.get(output_format, format_instructions['structured'])}",
                    },
                    {"role": "user", "content": text},
                ],
                tier=ModelTier.SPECIALIST,
                temperature=0.2,
            )

            if output_format == "markdown":
                return {"status": "success", "format": "markdown", "content": result.content}

            parsed = json.loads(result.content.strip())
            return {"status": "success", "format": output_format, "meeting": parsed}
        except json.JSONDecodeError:
            return {"status": "partial", "raw_output": result.content}
        except Exception as e:
            return {"status": "error", "message": f"Parsing failed: {e}"}


class CreateTasksFromMeetingTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_tasks_from_meeting",
            description="Extract action items from meeting notes and create todos (+ Jira tickets if configured)",
            parameters={"text": {"type": "str", "description": "Meeting notes or transcript"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        text = kwargs.get("text", "")
        if not text:
            return {"status": "error", "message": "text is required"}

        extractor = ExtractActionItemsTool()
        extraction = await extractor.execute(text=text)

        if extraction.get("status") != "success":
            return extraction

        action_items = extraction.get("action_items", [])
        if not action_items:
            return {"status": "success", "message": "No action items found in the meeting notes.", "todos_created": 0}

        from config import settings

        todos_created = 0
        jira_tickets_created = 0

        # Create local todos
        if settings.meeting.auto_create_todos:
            todos_path = DATA_DIR / "todos.json"
            todos_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                todos = json.loads(todos_path.read_text()) if todos_path.exists() else []
            except (OSError, json.JSONDecodeError):
                todos = []

            for item in action_items:
                todo = {
                    "text": f"[Meeting] {item.get('task', '')}",
                    "done": False,
                    "priority": item.get("priority", "medium"),
                    "assignee": item.get("assignee", "unassigned"),
                    "deadline": item.get("deadline", "none"),
                    "source": "meeting_notes",
                    "created_at": datetime.now().isoformat(),
                }
                todos.append(todo)
                todos_created += 1

            todos_path.write_text(json.dumps(todos, indent=2, default=str))

        # Create Jira tickets if enabled
        if settings.meeting.auto_create_tickets and settings.jira.enabled:
            try:
                from vera.brain.agents.jira_agent import CreateTicketTool

                ticket_tool = CreateTicketTool()

                for item in action_items:
                    result = await ticket_tool.execute(
                        summary=item.get("task", "Meeting action item"),
                        description=f"From meeting notes. Assignee: {item.get('assignee', 'unassigned')}. Deadline: {item.get('deadline', 'none')}.",
                        priority={"high": "High", "medium": "Medium", "low": "Low"}.get(
                            item.get("priority", "medium"), "Medium"
                        ),
                    )
                    if result.get("status") == "success":
                        jira_tickets_created += 1
            except Exception as e:
                logger.warning("Failed to create Jira tickets from meeting: %s", e)

        return {
            "status": "success",
            "action_items_found": len(action_items),
            "todos_created": todos_created,
            "jira_tickets_created": jira_tickets_created,
            "summary": extraction.get("summary", ""),
            "action_items": action_items,
        }


class MeetingAgent(BaseAgent):
    """Meeting notes processing, action item extraction, and task creation."""

    name = "meeting"
    description = "Parse meeting notes, extract action items, create todos and tickets from transcripts"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a meeting assistant. You can parse meeting notes and transcripts to extract "
        "action items, decisions, and summaries. You can also create todo items and Jira tickets "
        "from the extracted action items. When the user shares meeting notes, extract the key "
        "information and offer to create tasks."
    )

    offline_responses = {
        "meeting": "📝 I can help process meeting notes! Paste them and I'll extract action items.",
        "action_items": "📋 Paste your meeting notes and I'll find all the action items!",
        "transcript": "🎙️ Share the transcript and I'll parse it for you!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            ExtractActionItemsTool(),
            ParseMeetingNotesTool(),
            CreateTasksFromMeetingTool(),
        ]
