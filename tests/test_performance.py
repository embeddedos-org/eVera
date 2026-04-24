"""Performance Tests — verify response times and resource usage.

Marked as 'slow' so they don't run on every commit.
Run with: pytest tests/test_performance.py -v
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _allow_tmp_path_in_coder(tmp_path):
    """Ensure tmp_path is in ALLOWED_ROOTS for coder tools in CI."""
    from vera.brain.agents import coder

    original = list(coder.ALLOWED_ROOTS)
    coder.ALLOWED_ROOTS.append(tmp_path.resolve())
    yield
    coder.ALLOWED_ROOTS[:] = original


class TestResponseTime:
    """Verify key operations complete within acceptable time."""

    def test_agent_registry_loads_fast(self):
        """Agent registry should load in under 2 seconds."""
        start = time.monotonic()
        from vera.brain.agents import AGENT_REGISTRY

        _ = len(AGENT_REGISTRY)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"Registry load took {elapsed:.2f}s"

    def test_router_tier0_is_instant(self):
        """Tier 0 regex matching should be under 1ms."""
        from vera.brain.router import TIER0_PATTERNS

        text = "what time is it"

        start = time.monotonic()
        for _ in range(1000):
            for pattern, agent, intent, template in TIER0_PATTERNS:
                pattern.search(text)
        elapsed = time.monotonic() - start

        per_match = elapsed / 1000
        assert per_match < 0.001, f"Tier0 match took {per_match * 1000:.2f}ms"

    def test_spell_correction_is_fast(self):
        """Spell correction should be under 5ms per call."""
        from vera.brain.language import correct_spelling

        start = time.monotonic()
        for _ in range(100):
            correct_spelling("opne crome and serach for AI news")
        elapsed = time.monotonic() - start

        per_call = elapsed / 100
        assert per_call < 0.005, f"Spell correction took {per_call * 1000:.2f}ms"

    def test_language_detection_is_fast(self):
        """Language detection should be under 1ms."""
        from vera.brain.language import detect_language

        texts = ["Hello world", "こんにちは", "Hola amigos", "नमस्ते"]
        start = time.monotonic()
        for _ in range(1000):
            for text in texts:
                detect_language(text)
        elapsed = time.monotonic() - start

        per_call = elapsed / 4000
        assert per_call < 0.001, f"Language detection took {per_call * 1000:.2f}ms"

    def test_pii_detection_is_fast(self):
        """PII detection should be under 2ms."""
        from vera.safety.privacy import PrivacyGuard

        pg = PrivacyGuard()

        text = "My SSN is 123-45-6789 and card is 4111-1111-1111-1111 email test@test.com"
        start = time.monotonic()
        for _ in range(1000):
            pg.detect_pii(text)
        elapsed = time.monotonic() - start

        per_call = elapsed / 1000
        assert per_call < 0.002, f"PII detection took {per_call * 1000:.2f}ms"

    def test_policy_check_is_fast(self):
        """Policy check should be under 0.5ms."""
        from vera.safety.policy import PolicyService

        ps = PolicyService()

        start = time.monotonic()
        for _ in range(10000):
            ps.check("operator", "execute_script")
        elapsed = time.monotonic() - start

        per_call = elapsed / 10000
        assert per_call < 0.0005, f"Policy check took {per_call * 1000:.3f}ms"

    def test_tool_schema_generation_is_fast(self):
        """Tool schema generation should be under 1ms per tool."""
        from vera.brain.agents import AGENT_REGISTRY

        start = time.monotonic()
        for _ in range(100):
            for agent in AGENT_REGISTRY.values():
                for tool in agent.tools:
                    tool.to_openai_schema()
        elapsed = time.monotonic() - start

        total_tools = sum(len(a.tools) for a in AGENT_REGISTRY.values())
        per_schema = elapsed / (100 * total_tools)
        assert per_schema < 0.001, f"Schema gen took {per_schema * 1000:.2f}ms per tool"


class TestResourceUsage:
    """Verify memory and file handle usage."""

    def test_memory_vault_doesnt_leak(self):
        """Working memory should respect max_turns."""
        from vera.memory.working import WorkingMemory

        wm = WorkingMemory(max_turns=10)
        for i in range(1000):
            wm.add("user", f"message {i}")
        ctx = wm.get_context()
        assert len(ctx) <= 20  # 10 turns * 2 messages

    def test_agent_tool_count_reasonable(self):
        """No single agent should have more than 30 tools."""
        from vera.brain.agents import AGENT_REGISTRY

        for name, agent in AGENT_REGISTRY.items():
            assert len(agent.tools) <= 30, f"{name} has too many tools: {len(agent.tools)}"

    def test_file_operations_use_tmp(self, tmp_path):
        """File tools should work in temp directories."""
        import asyncio

        from vera.brain.agents.coder import ReadFileTool

        test_file = tmp_path / "perf_test.txt"
        test_file.write_text("x" * 10000)

        async def run():
            read = ReadFileTool()
            result = await read.execute(path=str(test_file))
            assert result["status"] == "success"

        asyncio.run(run())
