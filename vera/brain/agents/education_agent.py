"""Education Agent -- flashcards, quizzes, learning paths, Pomodoro, notes."""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class FlashcardTool(Tool):
    def __init__(self):
        super().__init__(
            name="flashcards",
            description="Create/study/list flashcards",
            parameters={
                "action": {"type": "str", "description": "create|study|list|delete"},
                "deck": {"type": "str", "description": "Deck name"},
                "front": {"type": "str", "description": "Card front"},
                "back": {"type": "str", "description": "Card back"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        dd = Path("data/flashcards")
        dd.mkdir(parents=True, exist_ok=True)
        dk = kw.get("deck", "default")
        fp = dd / f"{dk}.json"
        cards = json.loads(fp.read_text()) if fp.exists() else []
        a = kw.get("action", "list")
        if a == "create":
            cards.append({"front": kw.get("front", ""), "back": kw.get("back", ""), "correct": 0, "attempts": 0})
            fp.write_text(json.dumps(cards, indent=2))
            return {"status": "success", "total": len(cards)}
        elif a == "study":
            if not cards:
                return {"status": "success", "message": "No cards"}
            c = random.choice(cards)
            return {"status": "success", "front": c["front"], "back": c["back"]}
        elif a == "delete":
            cards = [c for c in cards if c["front"] != kw.get("front", "")]
            fp.write_text(json.dumps(cards, indent=2))
            return {"status": "success", "deleted": True}
        return {"status": "success", "deck": dk, "count": len(cards), "cards": cards[:20]}


class QuizGeneratorTool(Tool):
    def __init__(self):
        super().__init__(
            name="generate_quiz",
            description="Generate quiz questions on a topic",
            parameters={
                "topic": {"type": "str", "description": "Quiz topic"},
                "num_questions": {"type": "int", "description": "Number of questions"},
                "difficulty": {"type": "str", "description": "easy|medium|hard"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        return {
            "status": "success",
            "topic": kw.get("topic", ""),
            "num_questions": kw.get("num_questions", 5),
            "difficulty": kw.get("difficulty", "medium"),
            "instruction": "Use LLM to generate quiz questions with multiple choice options and answers.",
        }


class LearningPathTool(Tool):
    def __init__(self):
        super().__init__(
            name="learning_path",
            description="Create structured learning path",
            parameters={
                "subject": {"type": "str", "description": "Subject"},
                "level": {"type": "str", "description": "beginner|intermediate|advanced"},
                "duration_weeks": {"type": "int", "description": "Duration in weeks"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        return {
            "status": "success",
            "subject": kw.get("subject", ""),
            "level": kw.get("level", "beginner"),
            "weeks": kw.get("duration_weeks", 4),
            "instruction": "Generate week-by-week plan with topics, resources, milestones.",
        }


class PomodoroTool(Tool):
    def __init__(self):
        super().__init__(
            name="pomodoro_timer",
            description="Pomodoro study timer",
            parameters={
                "action": {"type": "str", "description": "start|stop|status"},
                "duration_minutes": {"type": "int", "description": "Work duration (default 25)"},
                "break_minutes": {"type": "int", "description": "Break duration (default 5)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        return {
            "status": "success",
            "action": kw.get("action", "start"),
            "work": kw.get("duration_minutes", 25),
            "break": kw.get("break_minutes", 5),
            "message": f"Focus for {kw.get('duration_minutes', 25)} minutes!",
        }


class NoteTakingTool(Tool):
    def __init__(self):
        super().__init__(
            name="study_notes",
            description="Create/search/list study notes",
            parameters={
                "action": {"type": "str", "description": "create|search|list"},
                "subject": {"type": "str", "description": "Subject"},
                "title": {"type": "str", "description": "Note title"},
                "content": {"type": "str", "description": "Note content"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        nd = Path("data/study_notes")
        nd.mkdir(parents=True, exist_ok=True)
        subj = kw.get("subject", "general")
        fp = nd / f"{subj}.json"
        notes = json.loads(fp.read_text()) if fp.exists() else []
        a = kw.get("action", "list")
        if a == "create":
            notes.append(
                {"title": kw.get("title", ""), "content": kw.get("content", ""), "created": datetime.now().isoformat()}
            )
            fp.write_text(json.dumps(notes, indent=2))
            return {"status": "success", "total": len(notes)}
        elif a == "search":
            q = kw.get("title", "").lower()
            return {
                "status": "success",
                "results": [n for n in notes if q in n.get("title", "").lower() or q in n.get("content", "").lower()][
                    :10
                ],
            }
        return {
            "status": "success",
            "subject": subj,
            "count": len(notes),
            "notes": [{"title": n["title"]} for n in notes[:20]],
        }


class EducationAgent(BaseAgent):
    name = "education"
    description = "Flashcards, quizzes, learning paths, Pomodoro timer, study notes"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Education Agent. Create flashcards, generate quizzes, build learning paths, manage Pomodoro sessions, organize study notes. Be encouraging."
    offline_responses = {
        "study": "\U0001f4da Study time!",
        "quiz": "\u2753 Quiz time!",
        "learn": "\U0001f393 Let's learn!",
        "flashcard": "\U0001f4c7 Flashcards!",
    }

    def _setup_tools(self):
        self._tools = [FlashcardTool(), QuizGeneratorTool(), LearningPathTool(), PomodoroTool(), NoteTakingTool()]
