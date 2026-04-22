"""Tests for ProviderManager.stream() method."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vera.providers.models import ModelTier


class TestProviderStream:
    @pytest.mark.asyncio
    async def test_stream_raises_value_error_for_reflex_tier(self):
        with patch("vera.providers.manager.litellm"):
            from vera.providers.manager import ProviderManager

            pm = ProviderManager()
            with pytest.raises(ValueError, match="REFLEX"):
                async for _ in pm.stream(
                    messages=[{"role": "user", "content": "hi"}],
                    tier=ModelTier.REFLEX,
                ):
                    pass

    @pytest.mark.asyncio
    async def test_stream_raises_runtime_error_no_models(self):
        with patch("vera.providers.manager.litellm"):
            from vera.providers.manager import ProviderManager

            pm = ProviderManager()
            pm._models = {tier: [] for tier in ModelTier}
            with pytest.raises(RuntimeError, match="No models available"):
                async for _ in pm.stream(
                    messages=[{"role": "user", "content": "hi"}],
                    tier=ModelTier.SPECIALIST,
                ):
                    pass

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        mock_chunks = []
        for text in ["Hello", " world", "!"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = text
            mock_chunks.append(chunk)

        async def mock_async_iter():
            for chunk in mock_chunks:
                yield chunk

        with patch("vera.providers.manager.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_async_iter())
            from vera.providers.manager import ProviderManager

            pm = ProviderManager()

            collected = []
            async for chunk in pm.stream(
                messages=[{"role": "user", "content": "hi"}],
                tier=ModelTier.SPECIALIST,
            ):
                collected.append(chunk)

            assert collected == ["Hello", " world", "!"]

    @pytest.mark.asyncio
    async def test_stream_skips_empty_delta(self):
        chunks = []
        # Chunk with content
        c1 = MagicMock()
        c1.choices = [MagicMock()]
        c1.choices[0].delta = MagicMock(content="data")
        chunks.append(c1)
        # Chunk with None content
        c2 = MagicMock()
        c2.choices = [MagicMock()]
        c2.choices[0].delta = MagicMock(content=None)
        chunks.append(c2)
        # Chunk with empty string content
        c3 = MagicMock()
        c3.choices = [MagicMock()]
        c3.choices[0].delta = MagicMock(content="")
        chunks.append(c3)

        async def mock_iter():
            for c in chunks:
                yield c

        with patch("vera.providers.manager.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=mock_iter())
            from vera.providers.manager import ProviderManager

            pm = ProviderManager()

            collected = []
            async for chunk in pm.stream(
                messages=[{"role": "user", "content": "hi"}],
                tier=ModelTier.SPECIALIST,
            ):
                collected.append(chunk)

            assert collected == ["data"]


class TestGetUsage:
    def test_get_usage_returns_tier_keyed_dict(self):
        with patch("vera.providers.manager.litellm"):
            from vera.providers.manager import ProviderManager

            pm = ProviderManager()
            usage = pm.get_usage()
            assert "REFLEX" in usage
            assert "EXECUTOR" in usage
            assert "SPECIALIST" in usage
            assert "STRATEGIST" in usage
            assert usage["REFLEX"].call_count == 0
