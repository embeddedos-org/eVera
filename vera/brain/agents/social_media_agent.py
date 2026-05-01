"""Social Media Agent -- posting, hashtags, content calendar, trends, captions."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class SocialPostTool(Tool):
    def __init__(self):
        super().__init__(
            name="social_post",
            description="Create/schedule social media posts",
            parameters={
                "platform": {"type": "str", "description": "twitter|linkedin|facebook|instagram"},
                "content": {"type": "str", "description": "Post content"},
                "schedule": {"type": "str", "description": "Schedule time ISO (optional)"},
                "hashtags": {"type": "str", "description": "Comma-separated hashtags"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        pp = Path("data/social_posts.json")
        pp.parent.mkdir(parents=True, exist_ok=True)
        posts = json.loads(pp.read_text()) if pp.exists() else []
        post = {
            "platform": kw.get("platform", "twitter"),
            "content": kw.get("content", ""),
            "hashtags": kw.get("hashtags", "").split(",") if kw.get("hashtags") else [],
            "schedule": kw.get("schedule", ""),
            "created": datetime.now().isoformat(),
            "status": "scheduled" if kw.get("schedule") else "draft",
        }
        posts.append(post)
        pp.write_text(json.dumps(posts, indent=2))
        return {"status": "success", "post": post}


class HashtagGeneratorTool(Tool):
    def __init__(self):
        super().__init__(
            name="hashtag_generator",
            description="Generate relevant hashtags",
            parameters={
                "topic": {"type": "str", "description": "Topic"},
                "count": {"type": "int", "description": "Number of hashtags"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        topic = kw.get("topic", "").lower()
        words = topic.split()
        tags = (
            [f"#{topic.replace(' ', '')}"]
            + [f"#{w}" for w in words[:3]]
            + ["#trending", "#viral", "#instagood", "#explore"]
        )
        return {"status": "success", "hashtags": tags[: kw.get("count", 10)]}


class ContentCalendarTool(Tool):
    def __init__(self):
        super().__init__(
            name="content_calendar",
            description="Manage content calendar",
            parameters={
                "action": {"type": "str", "description": "view|add|remove"},
                "date": {"type": "str", "description": "Date YYYY-MM-DD"},
                "content": {"type": "str", "description": "Content"},
                "platform": {"type": "str", "description": "Platform"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        cp = Path("data/content_calendar.json")
        cp.parent.mkdir(parents=True, exist_ok=True)
        cal = json.loads(cp.read_text()) if cp.exists() else []
        a = kw.get("action", "view")
        if a == "add":
            cal.append(
                {"date": kw.get("date", ""), "content": kw.get("content", ""), "platform": kw.get("platform", "all")}
            )
            cp.write_text(json.dumps(cal, indent=2))
            return {"status": "success", "added": True}
        elif a == "remove":
            cal = [c for c in cal if c["date"] != kw.get("date", "")]
            cp.write_text(json.dumps(cal, indent=2))
            return {"status": "success", "removed": True}
        return {"status": "success", "calendar": cal[:30]}


class TrendAnalysisTool(Tool):
    def __init__(self):
        super().__init__(
            name="trend_analysis",
            description="Analyze trending topics",
            parameters={
                "platform": {"type": "str", "description": "twitter|tiktok|youtube|reddit"},
                "category": {"type": "str", "description": "Category"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(
                    d.text(f"{kw.get('platform', 'twitter')} trending today {kw.get('category', '')}", max_results=5)
                )
            return {"status": "success", "trends": [{"title": r["title"], "url": r["href"]} for r in results]}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class CaptionWriterTool(Tool):
    def __init__(self):
        super().__init__(
            name="caption_writer",
            description="Generate social media captions",
            parameters={
                "topic": {"type": "str", "description": "Topic"},
                "tone": {"type": "str", "description": "professional|casual|funny|inspirational"},
                "platform": {"type": "str", "description": "Platform"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        limits = {"twitter": 280, "instagram": 2200, "linkedin": 3000, "facebook": 63206}
        return {
            "status": "success",
            "topic": kw.get("topic", ""),
            "tone": kw.get("tone", "casual"),
            "char_limit": limits.get(kw.get("platform", "twitter"), 280),
        }


class SocialMediaAgent(BaseAgent):
    name = "social_media"
    description = "Social media posting, hashtags, content calendar, trend analysis, caption writing"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Social Media Agent. Create posts, generate hashtags, manage content calendars, analyze trends, write captions."
    offline_responses = {
        "post": "\U0001f4f1 Creating post!",
        "hashtag": "# Generating!",
        "trend": "\U0001f4c8 Trends!",
        "social": "\U0001f310 Social ready!",
    }

    def _setup_tools(self):
        self._tools = [
            SocialPostTool(),
            HashtagGeneratorTool(),
            ContentCalendarTool(),
            TrendAnalysisTool(),
            CaptionWriterTool(),
        ]
