"""Tests for MediaFactory agent — image gen, video assembly, upload tools.

Mocks all external APIs (httpx, moviepy, PIL, edge-tts, google API, rembg)
to ensure tests run without optional dependencies installed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_image(tmp_path: Path) -> Path:
    """Create a minimal valid PNG file for testing."""
    # Minimal 1x1 white PNG
    import struct
    import zlib

    def _create_png(width: int = 10, height: int = 10) -> bytes:
        def _chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        header = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        raw = b""
        for _ in range(height):
            raw += b"\x00" + b"\xff\xff\xff" * width
        idat = zlib.compress(raw)
        return header + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")

    img_path = tmp_path / "test_image.png"
    img_path.write_bytes(_create_png())
    return img_path


@pytest.fixture
def tmp_video(tmp_path: Path) -> Path:
    """Create a placeholder video file."""
    video_path = tmp_path / "test_video.mp4"
    video_path.write_bytes(b"\x00" * 1024)
    return video_path


@pytest.fixture
def tmp_audio(tmp_path: Path) -> Path:
    """Create a placeholder audio file."""
    audio_path = tmp_path / "test_audio.mp3"
    audio_path.write_bytes(b"\x00" * 512)
    return audio_path


# ---------------------------------------------------------------------------
# Agent registration & structure
# ---------------------------------------------------------------------------


class TestMediaFactoryAgent:
    def test_agent_import(self):
        from vera.brain.agents.media_factory import MediaFactoryAgent

        agent = MediaFactoryAgent()
        assert agent.name == "media_factory"

    def test_agent_has_12_tools(self):
        from vera.brain.agents.media_factory import MediaFactoryAgent

        agent = MediaFactoryAgent()
        assert len(agent.tools) == 12

    def test_agent_tool_names(self):
        from vera.brain.agents.media_factory import MediaFactoryAgent

        agent = MediaFactoryAgent()
        names = {t.name for t in agent.tools}
        expected = {
            "generate_image",
            "edit_image",
            "add_text_overlay",
            "remove_background",
            "generate_voiceover",
            "assemble_video",
            "add_subtitles",
            "add_background_music",
            "upload_youtube",
            "upload_instagram",
            "upload_tiktok",
            "create_reel",
        }
        assert names == expected

    def test_agent_offline_responses(self):
        from vera.brain.agents.media_factory import MediaFactoryAgent

        agent = MediaFactoryAgent()
        assert len(agent.offline_responses) > 0
        assert "image" in agent.offline_responses

    def test_agent_description(self):
        from vera.brain.agents.media_factory import MediaFactoryAgent

        agent = MediaFactoryAgent()
        assert "image" in agent.description.lower()
        assert "video" in agent.description.lower()

    def test_agent_tier(self):
        from vera.brain.agents.media_factory import MediaFactoryAgent
        from vera.providers.models import ModelTier

        agent = MediaFactoryAgent()
        assert agent.tier == ModelTier.SPECIALIST


# ---------------------------------------------------------------------------
# GenerateImageTool
# ---------------------------------------------------------------------------


class TestGenerateImageTool:
    @pytest.mark.asyncio
    async def test_no_prompt_returns_error(self):
        from vera.brain.agents.media_factory import GenerateImageTool

        tool = GenerateImageTool()
        result = await tool.execute(prompt="")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_pollinations_success(self, tmp_path: Path):
        from vera.brain.agents.media_factory import GenerateImageTool

        tool = GenerateImageTool()
        mock_response = MagicMock()
        mock_response.content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch("vera.brain.agents.media_factory.DATA_DIR", tmp_path):
                (tmp_path / "images").mkdir(parents=True, exist_ok=True)
                result = await tool.execute(prompt="sunset", provider="pollinations")
                assert result["status"] == "success"
                assert result["provider"] == "pollinations"


# ---------------------------------------------------------------------------
# EditImageTool
# ---------------------------------------------------------------------------


class TestEditImageTool:
    @pytest.mark.asyncio
    async def test_missing_file(self):
        from vera.brain.agents.media_factory import EditImageTool

        tool = EditImageTool()
        result = await tool.execute(path="/nonexistent.png", action="resize", value="100x100")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_unknown_action(self, tmp_image: Path):
        from vera.brain.agents.media_factory import EditImageTool

        tool = EditImageTool()
        result = await tool.execute(path=str(tmp_image), action="unknown_action", value="1")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_grayscale(self, tmp_image: Path):
        from vera.brain.agents.media_factory import EditImageTool

        tool = EditImageTool()
        result = await tool.execute(path=str(tmp_image), action="grayscale", value="")
        assert result["status"] == "success"
        assert "_edited_grayscale" in result["path"]


# ---------------------------------------------------------------------------
# AddTextOverlayTool
# ---------------------------------------------------------------------------


class TestAddTextOverlayTool:
    @pytest.mark.asyncio
    async def test_no_text(self, tmp_image: Path):
        from vera.brain.agents.media_factory import AddTextOverlayTool

        tool = AddTextOverlayTool()
        result = await tool.execute(image_path=str(tmp_image), text="")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_add_text_success(self, tmp_image: Path):
        from vera.brain.agents.media_factory import AddTextOverlayTool

        tool = AddTextOverlayTool()
        result = await tool.execute(image_path=str(tmp_image), text="Hello World", position="center")
        assert result["status"] == "success"
        assert "_text" in result["path"]


# ---------------------------------------------------------------------------
# RemoveBackgroundTool
# ---------------------------------------------------------------------------


class TestRemoveBackgroundTool:
    @pytest.mark.asyncio
    async def test_missing_file(self):
        from vera.brain.agents.media_factory import RemoveBackgroundTool

        tool = RemoveBackgroundTool()
        result = await tool.execute(image_path="/nonexistent.png")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_rembg_not_installed(self, tmp_image: Path):
        from vera.brain.agents.media_factory import RemoveBackgroundTool

        tool = RemoveBackgroundTool()
        with patch.dict("sys.modules", {"rembg": None}):
            # Force ImportError by patching the import
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "rembg":
                    raise ImportError("mocked")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = await tool.execute(image_path=str(tmp_image))
                assert result["status"] == "error"
                assert "rembg" in result["message"]


# ---------------------------------------------------------------------------
# GenerateVoiceoverTool
# ---------------------------------------------------------------------------


class TestGenerateVoiceoverTool:
    @pytest.mark.asyncio
    async def test_no_text(self):
        from vera.brain.agents.media_factory import GenerateVoiceoverTool

        tool = GenerateVoiceoverTool()
        result = await tool.execute(text="")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_edge_tts_not_installed(self):
        from vera.brain.agents.media_factory import GenerateVoiceoverTool

        tool = GenerateVoiceoverTool()
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "edge_tts":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = await tool.execute(text="Hello world")
            assert result["status"] == "error"
            assert "edge-tts" in result["message"]


# ---------------------------------------------------------------------------
# AssembleVideoTool
# ---------------------------------------------------------------------------


class TestAssembleVideoTool:
    @pytest.mark.asyncio
    async def test_no_images(self):
        from vera.brain.agents.media_factory import AssembleVideoTool

        tool = AssembleVideoTool()
        result = await tool.execute(images="")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_missing_image_file(self):
        from vera.brain.agents.media_factory import AssembleVideoTool

        tool = AssembleVideoTool()
        result = await tool.execute(images="/nonexistent1.png,/nonexistent2.png")
        # Should fail with moviepy import error or file not found
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# AddSubtitlesTool
# ---------------------------------------------------------------------------


class TestAddSubtitlesTool:
    @pytest.mark.asyncio
    async def test_missing_video(self):
        from vera.brain.agents.media_factory import AddSubtitlesTool

        tool = AddSubtitlesTool()
        result = await tool.execute(video_path="/nonexistent.mp4")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# AddBackgroundMusicTool
# ---------------------------------------------------------------------------


class TestAddBackgroundMusicTool:
    @pytest.mark.asyncio
    async def test_missing_video(self):
        from vera.brain.agents.media_factory import AddBackgroundMusicTool

        tool = AddBackgroundMusicTool()
        result = await tool.execute(video_path="/nonexistent.mp4", music_path="/music.mp3")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_missing_music(self, tmp_video: Path):
        from vera.brain.agents.media_factory import AddBackgroundMusicTool

        tool = AddBackgroundMusicTool()
        result = await tool.execute(video_path=str(tmp_video), music_path="/nonexistent.mp3")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Upload Tools
# ---------------------------------------------------------------------------


class TestUploadYouTubeTool:
    @pytest.mark.asyncio
    async def test_missing_video(self):
        from vera.brain.agents.media_factory import UploadYouTubeTool

        tool = UploadYouTubeTool()
        result = await tool.execute(video_path="/nonexistent.mp4", title="Test")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_missing_deps(self, tmp_video: Path):
        from vera.brain.agents.media_factory import UploadYouTubeTool

        tool = UploadYouTubeTool()
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "google" in name:
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = await tool.execute(video_path=str(tmp_video), title="Test Video")
            assert result["status"] == "error"
            assert result.get("saved") is True


class TestUploadInstagramTool:
    @pytest.mark.asyncio
    async def test_missing_media(self):
        from vera.brain.agents.media_factory import UploadInstagramTool

        tool = UploadInstagramTool()
        result = await tool.execute(media_path="/nonexistent.mp4", caption="Test")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_no_token_saves_entry(self, tmp_video: Path):
        from vera.brain.agents.media_factory import UploadInstagramTool

        tool = UploadInstagramTool()
        with patch("config.settings.media.instagram_access_token", ""):
            with patch.dict(os.environ, {"VERA_MEDIA_INSTAGRAM_ACCESS_TOKEN": ""}, clear=False):
                result = await tool.execute(media_path=str(tmp_video), caption="Test")
                assert result["status"] == "saved"


class TestUploadTikTokTool:
    @pytest.mark.asyncio
    async def test_missing_video(self):
        from vera.brain.agents.media_factory import UploadTikTokTool

        tool = UploadTikTokTool()
        result = await tool.execute(video_path="/nonexistent.mp4", caption="Test")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_saves_entry(self, tmp_video: Path):
        from vera.brain.agents.media_factory import UploadTikTokTool

        tool = UploadTikTokTool()
        result = await tool.execute(video_path=str(tmp_video), caption="Fun video")
        assert result["status"] == "saved"
        assert "browser" in result["message"].lower()


# ---------------------------------------------------------------------------
# CreateReelTool
# ---------------------------------------------------------------------------


class TestCreateReelTool:
    @pytest.mark.asyncio
    async def test_no_topic(self):
        from vera.brain.agents.media_factory import CreateReelTool

        tool = CreateReelTool()
        result = await tool.execute(topic="")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Config & Policy
# ---------------------------------------------------------------------------


class TestMediaConfig:
    def test_media_settings_in_config(self):
        from config import settings

        assert hasattr(settings, "media")
        assert hasattr(settings.media, "enabled")
        assert hasattr(settings.media, "dalle_api_key")
        assert hasattr(settings.media, "default_voice")
        assert settings.media.default_voice == "en-US-AriaNeural"
        assert settings.media.default_aspect_ratio == "9:16"
        assert settings.media.default_image_provider == "pollinations"

    def test_media_policy_rules(self):
        from vera.safety.policy import DEFAULT_RULES, PolicyAction

        assert DEFAULT_RULES.get("media_factory.generate_image") == PolicyAction.ALLOW
        assert DEFAULT_RULES.get("media_factory.edit_image") == PolicyAction.ALLOW
        assert DEFAULT_RULES.get("media_factory.upload_youtube") == PolicyAction.CONFIRM
        assert DEFAULT_RULES.get("media_factory.upload_instagram") == PolicyAction.CONFIRM
        assert DEFAULT_RULES.get("media_factory.upload_tiktok") == PolicyAction.CONFIRM
        assert DEFAULT_RULES.get("media_factory.create_reel") == PolicyAction.CONFIRM


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestMediaRouting:
    def test_intent_agent_map_has_media_factory(self):
        from vera.brain.router import INTENT_AGENT_MAP

        media_intents = [k for k, v in INTENT_AGENT_MAP.items() if v == "media_factory"]
        assert "generate_image" in media_intents
        assert "create_reel" in media_intents
        assert "edit_image" in media_intents
        assert "voiceover" in media_intents
        assert "upload_youtube" in media_intents

    def test_classification_prompt_has_media_factory(self):
        from vera.brain.router import CLASSIFICATION_PROMPT

        assert "media_factory" in CLASSIFICATION_PROMPT


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_format_srt_time(self):
        from vera.brain.agents.media_factory import _format_srt_time

        assert _format_srt_time(0) == "00:00:00,000"
        assert _format_srt_time(61.5) == "00:01:01,500"
        assert _format_srt_time(3661.123) == "01:01:01,123"

    def test_ensure_dirs(self, tmp_path: Path):
        from vera.brain.agents import media_factory

        original = media_factory.DATA_DIR
        media_factory.DATA_DIR = tmp_path / "media"
        try:
            media_factory._ensure_dirs()
            assert (tmp_path / "media" / "images").exists()
            assert (tmp_path / "media" / "audio").exists()
            assert (tmp_path / "media" / "videos").exists()
            assert (tmp_path / "media" / "uploads").exists()
        finally:
            media_factory.DATA_DIR = original

    def test_log_upload(self, tmp_path: Path):
        from vera.brain.agents import media_factory

        original = media_factory.DATA_DIR
        media_factory.DATA_DIR = tmp_path / "media"
        try:
            media_factory._log_upload({"platform": "test", "status": "ok"})
            log_path = tmp_path / "media" / "uploads.json"
            assert log_path.exists()
            data = json.loads(log_path.read_text())
            assert len(data) == 1
            assert data[0]["platform"] == "test"
        finally:
            media_factory.DATA_DIR = original
