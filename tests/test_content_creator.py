"""Tests for ContentCreator agent tools."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def cc_env(tmp_path):
    """Patch content_creator module DATA_DIR to tmp_path."""
    import vera.brain.agents.content_creator as cc_mod

    cc_mod.DATA_DIR = tmp_path
    return tmp_path


# ── GenerateScriptTool ──────────────────────────────────────────


class TestGenerateScript:
    @pytest.mark.asyncio
    async def test_generates_script_with_sections(self, cc_env):
        from vera.brain.agents.content_creator import GenerateScriptTool

        tool = GenerateScriptTool()
        result = await tool.execute(topic="AI", platform="youtube")
        assert result["status"] == "success"
        script = result["script"]
        assert script["topic"] == "AI"
        assert script["platform"] == "youtube"
        assert "hook" in script["sections"]
        assert "intro" in script["sections"]
        assert "main_points" in script["sections"]
        assert "cta" in script["sections"]
        assert len(script["sections"]["main_points"]) == 3
        assert script["platform_tips"] != ""
        assert "ai" in script["seo_keywords"]

    @pytest.mark.asyncio
    async def test_empty_topic_returns_error(self, cc_env):
        from vera.brain.agents.content_creator import GenerateScriptTool

        tool = GenerateScriptTool()
        result = await tool.execute(topic="")
        assert result["status"] == "error"
        assert "No topic" in result["message"]

    @pytest.mark.asyncio
    async def test_script_persisted_to_disk(self, cc_env):
        from vera.brain.agents.content_creator import GenerateScriptTool

        tool = GenerateScriptTool()
        await tool.execute(topic="Python Tips", platform="tiktok")
        data = json.loads((cc_env / "content_scripts.json").read_text())
        assert len(data) == 1
        assert data[0]["topic"] == "Python Tips"
        assert data[0]["platform"] == "tiktok"

    @pytest.mark.asyncio
    async def test_script_with_different_platforms(self, cc_env):
        from vera.brain.agents.content_creator import GenerateScriptTool

        tool = GenerateScriptTool()
        for platform in ["youtube", "tiktok", "instagram", "linkedin", "twitter"]:
            result = await tool.execute(topic="Test", platform=platform)
            assert result["status"] == "success"
            assert result["script"]["platform_tips"] != ""


# ── CreateVideoTool ─────────────────────────────────────────────


class TestCreateVideo:
    @pytest.mark.asyncio
    async def test_no_api_key_saves_job(self, cc_env):
        from vera.brain.agents.content_creator import CreateVideoTool

        tool = CreateVideoTool()
        result = await tool.execute(prompt="test video about cats")
        assert result["status"] == "saved"
        assert "API_KEY" in result["message"]
        assert result["job"]["prompt"] == "test video about cats"
        assert result["job"]["status"] == "pending_api_key"
        # Verify job saved to disk
        jobs = json.loads((cc_env / "video_jobs.json").read_text())
        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_empty_prompt_returns_error(self, cc_env):
        from vera.brain.agents.content_creator import CreateVideoTool

        tool = CreateVideoTool()
        result = await tool.execute(prompt="")
        assert result["status"] == "error"
        assert "No prompt" in result["message"]

    @pytest.mark.asyncio
    async def test_video_job_has_correct_fields(self, cc_env):
        from vera.brain.agents.content_creator import CreateVideoTool

        tool = CreateVideoTool()
        result = await tool.execute(prompt="demo", provider="pika", duration=60, aspect_ratio="16:9")
        job = result["job"]
        assert job["provider"] == "pika"
        assert job["duration"] == 60
        assert job["aspect_ratio"] == "16:9"


# ── SchedulePostTool ────────────────────────────────────────────


class TestSchedulePost:
    @pytest.mark.asyncio
    async def test_schedule_now(self, cc_env):
        from vera.brain.agents.content_creator import SchedulePostTool

        tool = SchedulePostTool()
        result = await tool.execute(platform="twitter", content="Hello world!", schedule_at="now")
        assert result["status"] == "success"
        assert result["post"]["platform"] == "twitter"
        assert "Hello world!" in result["post"]["content"]

    @pytest.mark.asyncio
    async def test_schedule_relative_time(self, cc_env):
        from vera.brain.agents.content_creator import SchedulePostTool

        tool = SchedulePostTool()
        result = await tool.execute(platform="instagram", content="Check this out!", schedule_at="in 2h")
        assert result["status"] == "success"
        post_time = datetime.fromisoformat(result["post"]["schedule_at"])
        # Should be roughly 2 hours from now
        expected_time = datetime.now() + timedelta(hours=2)
        assert abs((post_time - expected_time).total_seconds()) < 10

    @pytest.mark.asyncio
    async def test_schedule_iso_datetime(self, cc_env):
        from vera.brain.agents.content_creator import SchedulePostTool

        tool = SchedulePostTool()
        future = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
        result = await tool.execute(platform="linkedin", content="Professional post", schedule_at=future)
        assert result["status"] == "success"
        assert result["post"]["status"] == "scheduled"

    @pytest.mark.asyncio
    async def test_empty_platform_or_content_error(self, cc_env):
        from vera.brain.agents.content_creator import SchedulePostTool

        tool = SchedulePostTool()
        # Missing platform
        result = await tool.execute(platform="", content="hello")
        assert result["status"] == "error"
        # Missing content
        result = await tool.execute(platform="twitter", content="")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_hashtags_processing(self, cc_env):
        from vera.brain.agents.content_creator import SchedulePostTool

        tool = SchedulePostTool()
        result = await tool.execute(
            platform="twitter",
            content="My post",
            schedule_at="now",
            hashtags="python, AI, coding",
        )
        assert result["status"] == "success"
        assert result["post"]["hashtags"] == ["python", "AI", "coding"]
        assert "#python" in result["post"]["content"]
        assert "#AI" in result["post"]["content"]

    @pytest.mark.asyncio
    async def test_post_persisted_to_disk(self, cc_env):
        from vera.brain.agents.content_creator import SchedulePostTool

        tool = SchedulePostTool()
        await tool.execute(platform="twitter", content="Test", schedule_at="now")
        data = json.loads((cc_env / "scheduled_posts.json").read_text())
        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_schedule_invalid_date_fallback(self, cc_env):
        from vera.brain.agents.content_creator import SchedulePostTool

        tool = SchedulePostTool()
        result = await tool.execute(platform="twitter", content="Post", schedule_at="invalid-date-string")
        assert result["status"] == "success"  # Falls back to now + 1h

    @pytest.mark.asyncio
    async def test_schedule_relative_minutes(self, cc_env):
        from vera.brain.agents.content_creator import SchedulePostTool

        tool = SchedulePostTool()
        result = await tool.execute(platform="twitter", content="Soon!", schedule_at="in 30m")
        assert result["status"] == "success"


# ── OptimizeSEOTool ─────────────────────────────────────────────


class TestOptimizeSEO:
    @pytest.mark.asyncio
    async def test_seo_with_topic(self, cc_env):
        from vera.brain.agents.content_creator import OptimizeSEOTool

        tool = OptimizeSEOTool()
        result = await tool.execute(topic="Python programming")
        assert result["status"] == "success"
        seo = result["seo"]
        assert len(seo["titles"]) == 5
        assert "Python programming" in seo["description"]
        assert len(seo["tags"]) > 0
        assert len(seo["hashtags"]) > 0
        assert "best_posting_times" in seo

    @pytest.mark.asyncio
    async def test_seo_empty_topic_error(self, cc_env):
        from vera.brain.agents.content_creator import OptimizeSEOTool

        tool = OptimizeSEOTool()
        result = await tool.execute(topic="")
        assert result["status"] == "error"
        assert "No topic" in result["message"]

    @pytest.mark.asyncio
    async def test_seo_with_custom_keywords(self, cc_env):
        from vera.brain.agents.content_creator import OptimizeSEOTool

        tool = OptimizeSEOTool()
        result = await tool.execute(topic="ML", keywords="machine learning, deep learning, neural nets")
        seo = result["seo"]
        assert "machine learning" in seo["tags"]

    @pytest.mark.asyncio
    async def test_seo_platform_posting_times(self, cc_env):
        from vera.brain.agents.content_creator import OptimizeSEOTool

        tool = OptimizeSEOTool()
        for platform in ["youtube", "tiktok", "instagram"]:
            result = await tool.execute(topic="Test", platform=platform)
            assert result["seo"]["best_posting_times"] != ""


# ── TrackAnalyticsTool ──────────────────────────────────────────


class TestTrackAnalytics:
    @pytest.mark.asyncio
    async def test_dashboard_empty(self, cc_env):
        from vera.brain.agents.content_creator import TrackAnalyticsTool

        tool = TrackAnalyticsTool()
        result = await tool.execute(action="dashboard")
        assert result["status"] == "success"
        dashboard = result["dashboard"]
        assert dashboard["total_scripts"] == 0
        assert dashboard["total_posts"] == 0
        assert dashboard["video_jobs"] == 0

    @pytest.mark.asyncio
    async def test_dashboard_with_data(self, cc_env):
        from vera.brain.agents.content_creator import TrackAnalyticsTool

        # Create some data files
        posts = [
            {"platform": "twitter", "status": "scheduled", "content": "A"},
            {"platform": "twitter", "status": "published", "content": "B"},
            {"platform": "instagram", "status": "scheduled", "content": "C"},
        ]
        scripts = [{"topic": "AI"}]
        videos = [{"prompt": "test"}]
        (cc_env / "scheduled_posts.json").write_text(json.dumps(posts))
        (cc_env / "content_scripts.json").write_text(json.dumps(scripts))
        (cc_env / "video_jobs.json").write_text(json.dumps(videos))

        tool = TrackAnalyticsTool()
        result = await tool.execute(action="dashboard")
        dashboard = result["dashboard"]
        assert dashboard["total_posts"] == 3
        assert dashboard["scheduled"] == 2
        assert dashboard["published"] == 1
        assert dashboard["total_scripts"] == 1
        assert dashboard["video_jobs"] == 1
        assert dashboard["platforms"]["twitter"] == 2
        assert dashboard["platforms"]["instagram"] == 1

    @pytest.mark.asyncio
    async def test_action_posts(self, cc_env):
        from vera.brain.agents.content_creator import TrackAnalyticsTool

        posts = [{"id": "1", "platform": "twitter"}]
        (cc_env / "scheduled_posts.json").write_text(json.dumps(posts))
        tool = TrackAnalyticsTool()
        result = await tool.execute(action="posts")
        assert result["status"] == "success"
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_action_scripts(self, cc_env):
        from vera.brain.agents.content_creator import TrackAnalyticsTool

        scripts = [{"topic": "AI"}, {"topic": "ML"}]
        (cc_env / "content_scripts.json").write_text(json.dumps(scripts))
        tool = TrackAnalyticsTool()
        result = await tool.execute(action="scripts")
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_action_videos(self, cc_env):
        from vera.brain.agents.content_creator import TrackAnalyticsTool

        videos = [{"prompt": "demo"}]
        (cc_env / "video_jobs.json").write_text(json.dumps(videos))
        tool = TrackAnalyticsTool()
        result = await tool.execute(action="videos")
        assert result["total"] == 1


# ── ContentCreatorAgent ─────────────────────────────────────────


class TestContentCreatorAgent:
    def test_agent_has_five_tools(self):
        from vera.brain.agents.content_creator import ContentCreatorAgent

        agent = ContentCreatorAgent()
        assert len(agent.tools) == 5

    def test_agent_name(self):
        from vera.brain.agents.content_creator import ContentCreatorAgent

        agent = ContentCreatorAgent()
        assert agent.name == "content_creator"

    def test_agent_has_offline_responses(self):
        from vera.brain.agents.content_creator import ContentCreatorAgent

        agent = ContentCreatorAgent()
        assert len(agent.offline_responses) > 0

    def test_agent_tool_names(self):
        from vera.brain.agents.content_creator import ContentCreatorAgent

        agent = ContentCreatorAgent()
        tool_names = [t.name for t in agent.tools]
        assert "generate_script" in tool_names
        assert "create_video" in tool_names
        assert "schedule_post" in tool_names
        assert "optimize_seo" in tool_names
        assert "track_analytics" in tool_names


# ── Helper functions ────────────────────────────────────────────


class TestCCHelpers:
    def test_load_json_nonexistent_returns_empty_list(self, cc_env):
        from vera.brain.agents.content_creator import _load_json

        result = _load_json("nonexistent.json")
        assert result == []

    def test_load_json_corrupt_returns_empty_list(self, cc_env):
        from vera.brain.agents.content_creator import _load_json

        (cc_env / "bad.json").write_text("{corrupt")
        result = _load_json("bad.json")
        assert result == []

    def test_save_and_load_roundtrip(self, cc_env):
        from vera.brain.agents.content_creator import _load_json, _save_json

        data = [{"key": "value"}]
        _save_json("test.json", data)
        loaded = _load_json("test.json")
        assert loaded == data
