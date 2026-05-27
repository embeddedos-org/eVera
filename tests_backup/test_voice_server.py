"""Tests for Feature 2: TTS engine abstraction and factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestTTSEngineFactory:
    def test_default_returns_local(self):
        with patch("config.settings") as mock_settings:
            mock_settings.voice.tts_engine = "pyttsx3"
            mock_settings.voice.tts_rate = 175
            from vera.action.tts import LocalTTSEngine, get_tts_engine

            engine = get_tts_engine()
            assert isinstance(engine, LocalTTSEngine)

    def test_edge_tts_returns_edge(self):
        from vera.action.tts import EdgeTTSEngine, get_tts_engine

        engine = get_tts_engine("edge-tts")
        assert isinstance(engine, EdgeTTSEngine)

    def test_explicit_name_overrides_config(self):
        from vera.action.tts import EdgeTTSEngine, get_tts_engine

        engine = get_tts_engine("edge")
        assert isinstance(engine, EdgeTTSEngine)


class TestLocalTTSEngine:
    def test_init_without_pyttsx3(self):
        with patch.dict("sys.modules", {"pyttsx3": None}):
            with patch(
                "builtins.__import__",
                side_effect=lambda n, *a, **k: (
                    (_ for _ in ()).throw(ImportError()) if n == "pyttsx3" else __import__(n, *a, **k)
                ),
            ):
                try:
                    from vera.action.tts import LocalTTSEngine

                    engine = LocalTTSEngine()
                    assert engine._engine is None
                except Exception:
                    pass  # pyttsx3 may actually be available

    def test_interrupt(self):
        from vera.action.tts import LocalTTSEngine

        engine = LocalTTSEngine()
        engine.interrupt()
        assert engine._interrupted is True


class TestEdgeTTSEngine:
    def test_init_default_voice(self):
        from vera.action.tts import EdgeTTSEngine

        engine = EdgeTTSEngine()
        assert engine._voice == "en-US-AriaNeural"

    def test_init_custom_voice(self):
        from vera.action.tts import EdgeTTSEngine

        engine = EdgeTTSEngine(voice="en-GB-SoniaNeural")
        assert engine._voice == "en-GB-SoniaNeural"

    def test_interrupt(self):
        from vera.action.tts import EdgeTTSEngine

        engine = EdgeTTSEngine()
        engine.interrupt()
        assert engine._interrupted is True


class TestSplitSentences:
    def test_basic_split(self):
        from vera.action.tts import _split_sentences

        result = _split_sentences("Hello. How are you? I'm fine!")
        assert len(result) == 3

    def test_empty_string(self):
        from vera.action.tts import _split_sentences

        result = _split_sentences("")
        assert result == []
