"""Sentiment analysis — keyword-based and LLM-powered mood detection.

Provides three analysis modes:
- keyword: Fast lexicon-based sentiment scoring (no LLM)
- llm: Full LLM-powered mood classification with trigger extraction
- hybrid (default): Keywords first, LLM only when uncertain or non-neutral
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from vera.providers.manager import ProviderManager
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

MOOD_LEXICON: dict[str, list[str]] = {
    "stressed": [
        "stressed", "stress", "overwhelmed", "overloaded", "swamped",
        "pressure", "pressured", "burned out", "burnout", "drowning",
    ],
    "anxious": [
        "anxious", "anxiety", "worried", "nervous", "uneasy", "panic",
        "panicking", "scared", "afraid", "dread", "dreading", "terrified",
    ],
    "sad": [
        "sad", "depressed", "down", "unhappy", "miserable", "heartbroken",
        "lonely", "lost", "hopeless", "grief", "grieving", "crying", "tears",
    ],
    "frustrated": [
        "frustrated", "annoyed", "angry", "furious", "irritated", "mad",
        "pissed", "fed up", "sick of", "hate", "ugh", "argh",
    ],
    "tired": [
        "tired", "exhausted", "drained", "fatigue", "fatigued", "sleepy",
        "wiped out", "worn out", "no energy", "burnt out",
    ],
    "happy": [
        "happy", "glad", "joyful", "delighted", "pleased", "wonderful",
        "fantastic", "awesome", "amazing", "great", "love", "loving",
        "thankful", "grateful", "blessed", "good", "nice",
    ],
    "excited": [
        "excited", "thrilled", "pumped", "stoked", "ecstatic", "hyped",
        "can't wait", "looking forward", "promoted", "celebration",
        "celebrate", "best day", "incredible",
    ],
}

NEGATIVE_MOODS = {"stressed", "anxious", "sad", "frustrated", "tired"}

SENTIMENT_SYSTEM_PROMPT = """\
Classify the user's emotional state from their message. Return JSON only:
{
  "mood": "<one of: stressed, anxious, sad, frustrated, tired, happy, excited, neutral>",
  "confidence": <0.0 to 1.0>,
  "trigger": "<short phrase that triggered this mood, or null>"
}
Return ONLY valid JSON, no explanation."""


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    mood: str
    confidence: float
    trigger: str | None
    method: str


def keyword_sentiment(text: str) -> tuple[str, float]:
    """Score text against the mood lexicon, return (mood, confidence).

    Counts keyword hits per mood category. Returns the highest-scoring
    mood and a confidence based on hit ratio.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for mood, keywords in MOOD_LEXICON.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            scores[mood] = count

    if not scores:
        return "neutral", 0.3

    best_mood = max(scores, key=scores.get)  # type: ignore[arg-type]
    total_hits = sum(scores.values())
    confidence = min(0.9, 0.3 + (scores[best_mood] / max(total_hits, 1)) * 0.6)

    return best_mood, confidence


async def llm_sentiment(
    text: str,
    provider_manager: ProviderManager,
    tier: ModelTier,
) -> tuple[str, float, str | None]:
    """Classify mood using an LLM call. Returns (mood, confidence, trigger)."""
    result = await provider_manager.complete(
        messages=[
            {"role": "system", "content": SENTIMENT_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        tier=tier,
        max_tokens=100,
        temperature=0.1,
    )

    return _parse_sentiment_json(result.content)


def _parse_sentiment_json(text: str) -> tuple[str, float, str | None]:
    """Parse sentiment JSON from LLM output."""
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
                logger.warning("Failed to parse sentiment JSON: %s", text[:200])
                return "neutral", 0.3, None
        else:
            return "neutral", 0.3, None

    mood = parsed.get("mood", "neutral")
    confidence = float(parsed.get("confidence", 0.5))
    trigger = parsed.get("trigger")

    valid_moods = set(MOOD_LEXICON.keys()) | {"neutral"}
    if mood not in valid_moods:
        mood = "neutral"

    return mood, min(max(confidence, 0.0), 1.0), trigger


async def analyze_sentiment(
    text: str,
    method: str = "hybrid",
    provider_manager: ProviderManager | None = None,
    tier: ModelTier = ModelTier.EXECUTOR,
) -> SentimentResult:
    """Orchestrate sentiment analysis using the specified method.

    @param text: User input text to analyze.
    @param method: "keyword", "llm", or "hybrid" (default).
    @param provider_manager: Required for "llm" and "hybrid" methods.
    @param tier: ModelTier for LLM calls.
    @return SentimentResult with mood, confidence, trigger, and method used.
    """
    if method == "keyword":
        mood, confidence = keyword_sentiment(text)
        return SentimentResult(mood=mood, confidence=confidence, trigger=None, method="keyword")

    if method == "llm":
        if provider_manager is None:
            raise ValueError("provider_manager required for LLM sentiment analysis")
        mood, confidence, trigger = await llm_sentiment(text, provider_manager, tier)
        return SentimentResult(mood=mood, confidence=confidence, trigger=trigger, method="llm")

    # hybrid: keyword first, LLM when uncertain or non-neutral
    mood, confidence = keyword_sentiment(text)

    if confidence < 0.5 or mood != "neutral":
        if provider_manager is not None:
            try:
                llm_mood, llm_conf, trigger = await llm_sentiment(text, provider_manager, tier)
                return SentimentResult(
                    mood=llm_mood, confidence=llm_conf, trigger=trigger, method="hybrid_llm",
                )
            except Exception as e:
                logger.warning("LLM sentiment failed, using keyword fallback: %s", e)

    return SentimentResult(mood=mood, confidence=confidence, trigger=None, method="hybrid_keyword")
