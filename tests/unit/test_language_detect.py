"""Unit tests for vera.brain.language.detect_language.

detect_language() runs on every transcript in the enrich_memory node and
its result is reported in the pipeline event. The Latin-script indicators
must match whole words ("which" is not the German "ich", "income" is not
the Italian "come"), and everyday English words ("come", "comment") must
not count as Italian or French.
"""

from __future__ import annotations

import pytest

from vera.brain.language import detect_language


@pytest.mark.parametrize(
    "text",
    [
        "Which song is playing?",
        "How rich is the richest person?",
        "Show my income for this month",
        "Welcome back, what is on my calendar?",
        "Come here and play some music",
        "Add a comment to the pull request",
        "Louis wants a sandwich",
    ],
)
def test_english_text_is_english(text: str) -> None:
    assert detect_language(text) == "en"


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Hola, ¿cómo estás?", "es"),
        ("Bonjour, merci beaucoup", "fr"),
        ("Wie geht es dir? Ich bin müde", "de"),
        ("Muito obrigado, você é ótimo", "pt"),
        ("Grazie mille, buongiorno", "it"),
        ("Привет, как дела?", "ru"),
    ],
)
def test_other_languages_still_detected(text: str, lang: str) -> None:
    assert detect_language(text) == lang
