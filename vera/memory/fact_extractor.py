"""LLM-powered fact extraction from conversation turns.

Extracts personal facts (location, occupation, preferences, family, etc.)
from user input using an LLM call and stores them in semantic memory.
"""

from __future__ import annotations

import json
import logging
import re

from vera.providers.manager import ProviderManager
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """\
You are a fact extractor. Given a conversation turn, extract any personal facts \
about the user as a JSON object with short keys and values.

Rules:
- Only extract concrete personal facts (name, location, occupation, preferences, \
family, hobbies, etc.)
- Use lowercase snake_case keys (e.g. "location", "occupation", "favorite_color")
- Values should be concise strings
- Do NOT extract opinions about third parties, conversational filler, or questions
- Do NOT re-extract facts already listed in "Known facts"
- If a known fact has changed, include the updated value
- If no new facts are found, return an empty JSON object: {}
- Return ONLY valid JSON, no explanation

Known facts:
{existing_facts}

User said: {transcript}
Assistant replied: {response}

Extract new or updated personal facts as JSON:"""


async def extract_facts(
    transcript: str,
    response: str,
    existing_facts: dict[str, str],
    provider_manager: ProviderManager,
    settings,
) -> dict[str, str]:
    """Extract personal facts from a conversation turn using an LLM.

    @param transcript: The user's input text.
    @param response: The assistant's response.
    @param existing_facts: Currently known facts to avoid re-extraction.
    @param provider_manager: LLM provider manager for inference.
    @param settings: Application settings with fact_extraction_* config.
    @return Dict of {fact_key: fact_value} for new/updated facts.
    """
    word_count = len(transcript.strip().split())
    if word_count < settings.memory.fact_extraction_min_words:
        return {}

    facts_str = "\n".join(f"- {k}: {v}" for k, v in existing_facts.items()) if existing_facts else "(none)"

    prompt = EXTRACTION_SYSTEM_PROMPT.format(
        existing_facts=facts_str,
        transcript=transcript,
        response=response,
    )

    tier = ModelTier[settings.memory.fact_extraction_tier]

    result = await provider_manager.complete(
        messages=[
            {"role": "system", "content": prompt},
        ],
        tier=tier,
        max_tokens=200,
        temperature=0.1,
    )

    return _parse_facts_json(result.content)


def _parse_facts_json(text: str) -> dict[str, str]:
    """Parse JSON from LLM output, handling markdown code fences."""
    text = text.strip()

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                logger.warning("Failed to parse fact extraction JSON: %s", text[:200])
                return {}
        else:
            logger.warning("No JSON found in fact extraction response: %s", text[:200])
            return {}

    if not isinstance(parsed, dict):
        logger.warning("Fact extraction returned non-dict: %s", type(parsed))
        return {}

    return {str(k): str(v) for k, v in parsed.items() if isinstance(k, str) and v}
