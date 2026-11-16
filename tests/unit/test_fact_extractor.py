"""Fact extraction: the prompt template formats, and the LLM reply is parsed.

EXTRACTION_SYSTEM_PROMPT goes through str.format(), so a literal brace in
it has to be doubled; a bare "{}" made every extract_facts() call raise
IndexError before the LLM was asked.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from vera.memory.fact_extractor import EXTRACTION_SYSTEM_PROMPT, _parse_facts_json, extract_facts


def _settings(min_words: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        memory=SimpleNamespace(fact_extraction_min_words=min_words, fact_extraction_tier="EXECUTOR"),
    )


def _provider(reply: str) -> MagicMock:
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=SimpleNamespace(content=reply))
    return provider


def test_prompt_template_formats():
    prompt = EXTRACTION_SYSTEM_PROMPT.format(
        existing_facts="- location: Pune",
        transcript="I work as a nurse",
        response="Nice!",
    )
    assert "return an empty JSON object: {}" in prompt
    assert "- location: Pune" in prompt
    assert "User said: I work as a nurse" in prompt
    assert "Assistant replied: Nice!" in prompt


async def test_extract_facts_asks_the_llm_and_returns_facts():
    provider = _provider('{"occupation": "nurse"}')
    facts = await extract_facts(
        transcript="I have worked as a nurse for ten years",
        response="That is great.",
        existing_facts={"location": "Pune"},
        provider_manager=provider,
        settings=_settings(),
    )
    assert facts == {"occupation": "nurse"}
    provider.complete.assert_awaited_once()
    prompt = provider.complete.await_args.kwargs["messages"][0]["content"]
    assert "- location: Pune" in prompt
    assert "User said: I have worked as a nurse for ten years" in prompt


async def test_braces_in_the_conversation_are_kept():
    provider = _provider("{}")
    facts = await extract_facts(
        transcript="my config is {debug: true} and {0}",
        response="noted {x}",
        existing_facts={},
        provider_manager=provider,
        settings=_settings(min_words=1),
    )
    assert facts == {}
    prompt = provider.complete.await_args.kwargs["messages"][0]["content"]
    assert "User said: my config is {debug: true} and {0}" in prompt
    assert "Known facts:\n(none)" in prompt


async def test_short_transcript_skips_the_llm():
    provider = _provider('{"name": "x"}')
    facts = await extract_facts("hi there", "hello", {}, provider, _settings(min_words=5))
    assert facts == {}
    provider.complete.assert_not_awaited()


def test_parse_facts_json_handles_fences_and_noise():
    assert _parse_facts_json('```json\n{"city": "Pune"}\n```') == {"city": "Pune"}
    assert _parse_facts_json('Sure: {"pet": "cat"} done') == {"pet": "cat"}
    assert _parse_facts_json("no json here") == {}
    assert _parse_facts_json('["a"]') == {}
