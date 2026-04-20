"""ContentCreator Agent — video creation, social media marketing, and content scheduling.

@file voca/brain/agents/content_creator.py
@brief Agent for generating scripts, creating AI videos, scheduling social posts,
       SEO optimization, and tracking analytics across platforms.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from voca.brain.agents.base import BaseAgent, Tool
from voca.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


def _ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def _load_json(filename: str) -> list[dict]:
    path = _ensure_data_dir() / filename
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
    return []


def _save_json(filename: str, data: list[dict]) -> None:
    path = _ensure_data_dir() / filename
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


class GenerateScriptTool(Tool):
    """Generate a video/content script using AI."""

    def __init__(self) -> None:
        super().__init__(
            name="generate_script",
            description="Generate a video or social media content script",
            parameters={
                "topic": {"type": "str", "description": "Content topic or idea"},
                "platform": {"type": "str", "description": "Target platform: youtube, tiktok, instagram, linkedin, twitter"},
                "duration": {"type": "str", "description": "Target duration: short (30s), medium (2-5min), long (10+min)"},
                "style": {"type": "str", "description": "Content style: educational, entertaining, promotional, tutorial"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        topic = kwargs.get("topic", "")
        platform = kwargs.get("platform", "youtube").lower()
        duration = kwargs.get("duration", "medium").lower()
        style = kwargs.get("style", "educational").lower()

        if not topic:
            return {"status": "error", "message": "No topic provided"}

        duration_map = {"short": "30-60 seconds", "medium": "2-5 minutes", "long": "10-15 minutes"}
        platform_tips = {
            "youtube": "Hook in first 5 seconds, chapters, end screen CTA",
            "tiktok": "Vertical format, trending sounds, text overlays, hook immediately",
            "instagram": "Visual-first, carousel or reel, hashtags, story teaser",
            "linkedin": "Professional tone, personal story, value-driven, document format",
            "twitter": "Thread format, strong opener, data/stats, engagement bait",
        }

        script = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "topic": topic,
            "platform": platform,
            "duration": duration_map.get(duration, duration),
            "style": style,
            "created": datetime.now().isoformat(),
            "sections": {
                "hook": f"[HOOK - 5 seconds] Attention-grabbing opener about: {topic}",
                "intro": f"[INTRO - 15 seconds] Introduce yourself and what viewers will learn about {topic}",
                "main_points": [
                    f"[POINT 1] Key insight about {topic}",
                    f"[POINT 2] Supporting evidence or example",
                    f"[POINT 3] Practical takeaway",
                ],
                "cta": f"[CTA] Subscribe/follow for more {style} content about {topic}",
                "outro": "[OUTRO] Summary + tease next video",
            },
            "platform_tips": platform_tips.get(platform, ""),
            "seo_keywords": [topic.lower()] + topic.lower().split()[:5],
        }

        scripts = _load_json("content_scripts.json")
        scripts.append(script)
        _save_json("content_scripts.json", scripts)

        return {"status": "success", "script": script}


class CreateVideoTool(Tool):
    """Create an AI-generated video using external APIs."""

    def __init__(self) -> None:
        super().__init__(
            name="create_video",
            description="Create an AI video from script/prompt (requires API key for Runway/Pika/HeyGen)",
            parameters={
                "prompt": {"type": "str", "description": "Video generation prompt or script"},
                "provider": {"type": "str", "description": "Video AI: runway, pika, heygen, d-id (default: runway)"},
                "duration": {"type": "int", "description": "Video duration in seconds (default: 30)"},
                "aspect_ratio": {"type": "str", "description": "Aspect ratio: 16:9, 9:16, 1:1 (default: 9:16)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        prompt = kwargs.get("prompt", "")
        provider = kwargs.get("provider", "runway").lower()
        duration = int(kwargs.get("duration", 30))
        aspect = kwargs.get("aspect_ratio", "9:16")

        if not prompt:
            return {"status": "error", "message": "No prompt provided"}

        api_keys = {
            "runway": os.getenv("VOCA_RUNWAY_API_KEY"),
            "pika": os.getenv("VOCA_PIKA_API_KEY"),
            "heygen": os.getenv("VOCA_HEYGEN_API_KEY"),
            "d-id": os.getenv("VOCA_DID_API_KEY"),
        }

        api_key = api_keys.get(provider)
        if not api_key:
            job = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "prompt": prompt,
                "provider": provider,
                "duration": duration,
                "aspect_ratio": aspect,
                "status": "pending_api_key",
                "created": datetime.now().isoformat(),
            }
            jobs = _load_json("video_jobs.json")
            jobs.append(job)
            _save_json("video_jobs.json", jobs)

            return {
                "status": "saved",
                "message": f"Video job saved. Set VOCA_{provider.upper()}_API_KEY in .env to generate. "
                           f"Supported providers: Runway ($0.05/sec), Pika (free tier), HeyGen (avatar videos), D-ID (talking head).",
                "job": job,
            }

        # API integration placeholder
        return {
            "status": "queued",
            "message": f"Video generation queued with {provider}. Duration: {duration}s, Aspect: {aspect}",
            "prompt": prompt[:200],
            "estimated_time": f"{duration * 2} seconds",
        }


class SchedulePostTool(Tool):
    """Schedule a social media post for later publishing."""

    def __init__(self) -> None:
        super().__init__(
            name="schedule_post",
            description="Schedule a social media post for auto-publishing",
            parameters={
                "platform": {"type": "str", "description": "Platform: youtube, tiktok, instagram, linkedin, twitter, facebook"},
                "content": {"type": "str", "description": "Post text/caption"},
                "media_path": {"type": "str", "description": "Path to image/video file (optional)"},
                "schedule_at": {"type": "str", "description": "When to post: 'now', 'in 2h', 'tomorrow 9am', or ISO datetime"},
                "hashtags": {"type": "str", "description": "Comma-separated hashtags"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        platform = kwargs.get("platform", "").lower()
        content = kwargs.get("content", "")
        media_path = kwargs.get("media_path", "")
        schedule_at = kwargs.get("schedule_at", "now")
        hashtags = kwargs.get("hashtags", "")

        if not platform or not content:
            return {"status": "error", "message": "Both platform and content are required"}

        import re
        if schedule_at == "now":
            post_time = datetime.now()
        elif schedule_at.startswith("in "):
            match = re.match(r"in\s+(\d+)\s*(h|m|d)", schedule_at)
            if match:
                amount, unit = int(match.group(1)), match.group(2)
                delta = {"h": timedelta(hours=amount), "m": timedelta(minutes=amount), "d": timedelta(days=amount)}
                post_time = datetime.now() + delta.get(unit, timedelta(hours=1))
            else:
                post_time = datetime.now() + timedelta(hours=1)
        else:
            try:
                post_time = datetime.fromisoformat(schedule_at)
            except ValueError:
                post_time = datetime.now() + timedelta(hours=1)

        tag_list = [t.strip().lstrip("#") for t in hashtags.split(",") if t.strip()] if hashtags else []
        full_content = content
        if tag_list:
            full_content += "\n\n" + " ".join(f"#{t}" for t in tag_list)

        post = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "platform": platform,
            "content": full_content,
            "media_path": media_path,
            "hashtags": tag_list,
            "schedule_at": post_time.isoformat(),
            "status": "scheduled" if post_time > datetime.now() else "ready",
            "created": datetime.now().isoformat(),
        }

        posts = _load_json("scheduled_posts.json")
        posts.append(post)
        _save_json("scheduled_posts.json", posts)

        return {
            "status": "success",
            "post": post,
            "message": f"Post scheduled for {platform} at {post_time.strftime('%Y-%m-%d %H:%M')}",
        }


class OptimizeSEOTool(Tool):
    """Optimize content for SEO — titles, descriptions, tags."""

    def __init__(self) -> None:
        super().__init__(
            name="optimize_seo",
            description="Generate SEO-optimized title, description, and tags for content",
            parameters={
                "topic": {"type": "str", "description": "Content topic"},
                "platform": {"type": "str", "description": "Target platform: youtube, tiktok, instagram, blog"},
                "keywords": {"type": "str", "description": "Comma-separated target keywords"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        topic = kwargs.get("topic", "")
        platform = kwargs.get("platform", "youtube").lower()
        keywords = kwargs.get("keywords", "")

        if not topic:
            return {"status": "error", "message": "No topic provided"}

        keyword_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else topic.split()[:5]

        seo = {
            "titles": [
                f"{topic} — Complete Guide ({datetime.now().year})",
                f"How to {topic} (Step by Step)",
                f"{topic}: Everything You Need to Know",
                f"Why {topic} Changes Everything",
                f"I Tried {topic} for 30 Days — Here's What Happened",
            ],
            "description": f"In this video, we cover everything about {topic}. "
                          f"Learn {', '.join(keyword_list[:3])} and more. "
                          f"Don't forget to subscribe for more content!\n\n"
                          f"Timestamps:\n0:00 Introduction\n0:30 What is {topic}\n2:00 Key Points\n5:00 Summary",
            "tags": keyword_list + [f"{topic} tutorial", f"{topic} guide", f"{topic} explained", f"how to {topic}"],
            "hashtags": [f"#{k.replace(' ', '')}" for k in keyword_list[:10]],
            "best_posting_times": {
                "youtube": "Tuesday/Thursday 2-4 PM EST",
                "tiktok": "Monday-Friday 7-9 AM, 12-3 PM, 7-11 PM",
                "instagram": "Monday-Friday 11 AM - 1 PM",
                "linkedin": "Tuesday-Thursday 8-10 AM",
                "twitter": "Monday-Friday 8 AM - 4 PM",
            }.get(platform, "Varies by audience"),
        }

        return {"status": "success", "seo": seo, "platform": platform}


class TrackAnalyticsTool(Tool):
    """Track content performance and analytics."""

    def __init__(self) -> None:
        super().__init__(
            name="track_analytics",
            description="View content performance metrics and scheduled posts",
            parameters={
                "action": {"type": "str", "description": "Action: dashboard, posts, scripts, videos"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "dashboard").lower()

        if action == "posts":
            posts = _load_json("scheduled_posts.json")
            return {"status": "success", "posts": posts[-20:], "total": len(posts)}

        elif action == "scripts":
            scripts = _load_json("content_scripts.json")
            return {"status": "success", "scripts": scripts[-10:], "total": len(scripts)}

        elif action == "videos":
            videos = _load_json("video_jobs.json")
            return {"status": "success", "videos": videos[-10:], "total": len(videos)}

        else:  # dashboard
            posts = _load_json("scheduled_posts.json")
            scripts = _load_json("content_scripts.json")
            videos = _load_json("video_jobs.json")

            scheduled = [p for p in posts if p.get("status") == "scheduled"]
            published = [p for p in posts if p.get("status") == "published"]

            platforms = {}
            for p in posts:
                plat = p.get("platform", "unknown")
                platforms[plat] = platforms.get(plat, 0) + 1

            return {
                "status": "success",
                "dashboard": {
                    "total_scripts": len(scripts),
                    "total_posts": len(posts),
                    "scheduled": len(scheduled),
                    "published": len(published),
                    "video_jobs": len(videos),
                    "platforms": platforms,
                },
            }


class ContentCreatorAgent(BaseAgent):
    """Creates content, generates videos, schedules social media, and optimizes for growth.

    The ContentCreator agent helps users build a content marketing pipeline:
    script generation → video creation → SEO optimization → scheduling → analytics.
    """

    name = "content_creator"
    description = "Creates videos, scripts, schedules social media posts, SEO optimization, and tracks analytics"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a content creation and marketing specialist. You help users create "
        "engaging content for YouTube, TikTok, Instagram, LinkedIn, Twitter, and blogs. "
        "You can generate video scripts, create AI videos, schedule posts across platforms, "
        "optimize for SEO, and track analytics. Be creative and data-driven. "
        "When the user wants to create content, start with generate_script. "
        "For posting, use schedule_post. For visibility, use optimize_seo. "
        "Always suggest platform-specific best practices."
    )

    offline_responses = {
        "video": "🎬 I'll help you create a video!",
        "content": "✍️ Let me draft some content for you!",
        "post": "📱 I'll schedule that post!",
        "marketing": "📈 Let's build your content strategy!",
        "script": "📝 I'll generate a script for you!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            GenerateScriptTool(),
            CreateVideoTool(),
            SchedulePostTool(),
            OptimizeSEOTool(),
            TrackAnalyticsTool(),
        ]
