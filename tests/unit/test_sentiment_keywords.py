"""Unit tests for the keyword mood lexicon in vera/emotional/sentiment.py.

Keywords must match whole words (or phrases), not substrings of other
words: "ugh" is not in "through", "mad" is not in "made", "down" is not
in "download", "hate" is not in "whatever" and "love" is not in "gloves".
"""

from __future__ import annotations

import asyncio

import pytest

from vera.emotional.sentiment import analyze_sentiment, keyword_sentiment


@pytest.mark.parametrize(
    "text",
    [
        "I made it through the queue, that's enough for today.",
        "Can you download the report and send it over?",
        "Whatever works for you is fine.",
        "I left my gloves in the car.",
        "The shutdown is scheduled for Friday.",
    ],
)
def test_keywords_inside_other_words_do_not_count(text):
    assert keyword_sentiment(text) == ("neutral", 0.3)


@pytest.mark.parametrize(
    ("text", "mood"),
    [
        ("I'm so stressed about this deadline", "stressed"),
        ("Ugh, the build broke again", "frustrated"),
        ("I hated that meeting", "frustrated"),
        ("Feeling down today", "sad"),
        ("I'm completely burned out", "stressed"),
        ("Can't wait for the weekend!", "excited"),
        ("I love this, thank you", "happy"),
        ("This week has been really stressful", "stressed"),
    ],
)
def test_whole_words_and_inflections_still_match(text, mood):
    assert keyword_sentiment(text)[0] == mood


def test_keyword_method_reports_neutral_for_plain_request():
    result = asyncio.run(analyze_sentiment("I made a note to download it later", method="keyword"))
    assert result.mood == "neutral"
    assert result.method == "keyword"
