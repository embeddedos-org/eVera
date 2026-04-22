"""Language Tutor Agent — interactive language learning through conversation.

Teaches languages (English, Spanish, French, and more) in a simple,
interactive, and conversational way. Focuses on vocabulary, conversation
practice, grammar, pronunciation, and progressive learning.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from vera.brain.agents.base import BaseAgent, Tool
from vera.brain.state import VeraState
from vera.providers.models import ModelTier

SUPPORTED_LANGUAGES = {
    "spanish": "es",
    "french": "fr",
    "english": "en",
    "german": "de",
    "italian": "it",
    "portuguese": "pt",
    "japanese": "ja",
    "korean": "ko",
    "chinese": "zh",
    "hindi": "hi",
    "arabic": "ar",
    "russian": "ru",
    "dutch": "nl",
    "turkish": "tr",
    "swedish": "sv",
    "telugu": "te",
}

LEVEL_DESCRIPTIONS = {
    "beginner": "Start from scratch — basic greetings, numbers, common words",
    "intermediate": "Build on basics — sentence construction, daily conversations",
    "advanced": "Polish fluency — nuance, idioms, complex grammar, debate",
}

CONVERSATION_SCENARIOS = [
    "ordering food at a restaurant",
    "asking for directions",
    "introducing yourself at a party",
    "shopping at a market",
    "checking into a hotel",
    "making a phone call",
    "visiting a doctor",
    "taking a taxi",
    "talking about your hobbies",
    "making plans with a friend",
    "job interview small talk",
    "discussing the weather",
]


class TeachVocabularyTool(Tool):
    """Teach vocabulary words and phrases in the target language."""

    name = "teach_vocabulary"
    description = "Teach new vocabulary words and phrases with pronunciation and examples"

    def __init__(self) -> None:
        super().__init__(
            name=self.name,
            description=self.description,
            parameters={
                "language": {"type": "str", "description": "Target language to teach"},
                "topic": {"type": "str", "description": "Vocabulary topic (greetings, food, travel, etc.)"},
                "level": {"type": "str", "description": "User level: beginner, intermediate, advanced"},
            },
        )

    async def execute(self, **kwargs) -> dict:
        language = kwargs.get("language", "spanish")
        topic = kwargs.get("topic", "greetings")
        level = kwargs.get("level", "beginner")
        return {
            "status": "success",
            "action": "teach_vocabulary",
            "language": language,
            "topic": topic,
            "level": level,
            "instruction": (
                f"Teach 3-5 {level}-level {language} words/phrases about '{topic}'. "
                f"For each word: give the word, pronunciation guide (phonetic), "
                f"English meaning, and use it in a simple sentence. "
                f"Keep it fun and conversational."
            ),
        }


class ConversationPracticeTool(Tool):
    """Simulate a real-life dialogue for language practice."""

    name = "conversation_practice"
    description = "Practice a real-life conversation scenario in the target language"

    def __init__(self) -> None:
        super().__init__(
            name=self.name,
            description=self.description,
            parameters={
                "language": {"type": "str", "description": "Target language"},
                "scenario": {"type": "str", "description": "Conversation scenario"},
                "level": {"type": "str", "description": "User level"},
            },
        )

    async def execute(self, **kwargs) -> dict:
        language = kwargs.get("language", "spanish")
        scenario = kwargs.get("scenario", random.choice(CONVERSATION_SCENARIOS))
        level = kwargs.get("level", "beginner")
        return {
            "status": "success",
            "action": "conversation_practice",
            "language": language,
            "scenario": scenario,
            "level": level,
            "instruction": (
                f"Start a {level}-level conversational roleplay in {language} about: '{scenario}'. "
                f"Play one role and ask the user to respond as the other. "
                f"Provide the {language} line with English translation in parentheses. "
                f"Gently correct any mistakes the user makes. Keep it interactive."
            ),
        }


class GrammarExplainTool(Tool):
    """Explain a grammar concept simply with examples."""

    name = "explain_grammar"
    description = "Explain a grammar point simply with clear examples"

    def __init__(self) -> None:
        super().__init__(
            name=self.name,
            description=self.description,
            parameters={
                "language": {"type": "str", "description": "Target language"},
                "topic": {"type": "str", "description": "Grammar topic to explain"},
                "level": {"type": "str", "description": "User level"},
            },
        )

    async def execute(self, **kwargs) -> dict:
        language = kwargs.get("language", "spanish")
        topic = kwargs.get("topic", "verb conjugation")
        level = kwargs.get("level", "beginner")
        return {
            "status": "success",
            "action": "explain_grammar",
            "language": language,
            "topic": topic,
            "level": level,
            "instruction": (
                f"Explain the {language} grammar concept '{topic}' at {level} level. "
                f"Keep it short and practical — use clear examples instead of long rules. "
                f"Show 2-3 example sentences with translations."
            ),
        }


class PronunciationHelpTool(Tool):
    """Help with pronunciation of words or phrases."""

    name = "pronunciation_help"
    description = "Break down pronunciation with syllables and phonetic guidance"

    def __init__(self) -> None:
        super().__init__(
            name=self.name,
            description=self.description,
            parameters={
                "language": {"type": "str", "description": "Target language"},
                "word_or_phrase": {"type": "str", "description": "Word or phrase to pronounce"},
            },
        )

    async def execute(self, **kwargs) -> dict:
        language = kwargs.get("language", "spanish")
        word = kwargs.get("word_or_phrase", "")
        return {
            "status": "success",
            "action": "pronunciation_help",
            "language": language,
            "word_or_phrase": word,
            "instruction": (
                f"Help pronounce the {language} word/phrase '{word}'. "
                f"Break it into syllables, give phonetic guidance using English sounds, "
                f"and mention any tricky sounds. Repeat and reinforce."
            ),
        }


class QuizTool(Tool):
    """Quiz the user on what they've learned."""

    name = "quiz"
    description = "Test the user with a quick vocabulary or grammar quiz"

    def __init__(self) -> None:
        super().__init__(
            name=self.name,
            description=self.description,
            parameters={
                "language": {"type": "str", "description": "Target language"},
                "topic": {"type": "str", "description": "Quiz topic"},
                "level": {"type": "str", "description": "User level"},
            },
        )

    async def execute(self, **kwargs) -> dict:
        language = kwargs.get("language", "spanish")
        topic = kwargs.get("topic", "general")
        level = kwargs.get("level", "beginner")
        return {
            "status": "success",
            "action": "quiz",
            "language": language,
            "topic": topic,
            "level": level,
            "instruction": (
                f"Give a quick {level}-level {language} quiz on '{topic}'. "
                f"Ask 3 questions: one translation, one fill-in-the-blank, one multiple choice. "
                f"Wait for the user to answer each before revealing the correct answer. "
                f"Be encouraging regardless of the result."
            ),
        }


class LanguageTutorAgent(BaseAgent):
    """Interactive language tutor — teaches through conversation, not memorization."""

    name = "language_tutor"
    description = "Interactive language learning — vocabulary, conversation practice, grammar, pronunciation"
    tier = ModelTier.EXECUTOR
    system_prompt = (
        "You are a friendly language tutor, not a formal teacher. "
        "Teach like a patient friend who makes learning fun and practical.\n\n"
        "TEACHING STYLE:\n"
        "- Keep explanations simple and practical\n"
        "- Focus on real-life usage (daily conversations)\n"
        "- Start simple → increase difficulty gradually\n"
        "- Adapt to the user's level (beginner, intermediate, advanced)\n"
        "- Keep lessons short and engaging\n"
        "- Encourage the user to respond and practice\n"
        "- Correct mistakes politely and clearly\n"
        "- Use examples instead of long grammar rules\n\n"
        "LESSON FLOW:\n"
        "1. Teach 3-5 words or phrases\n"
        "2. Practice with a short dialogue\n"
        "3. Ask the user to reply\n"
        "4. Give feedback and correction\n"
        "5. Move to the next step\n\n"
        "GOAL: Help the user confidently speak and understand the language "
        "through natural conversation, not memorization.\n\n"
        "If the user hasn't specified a language yet, ask them. "
        "If they haven't specified their level, ask that too before starting."
    )

    offline_responses = {
        "learn_language": "I'd love to help you learn a new language! 🌍 Which language are you interested in?",
        "vocabulary": "Let's learn some new words! 📚 What topic should we cover?",
        "practice": "Time for some conversation practice! 🗣️ Ready to try a roleplay?",
        "grammar": "Let's tackle some grammar! 📝 What concept are you working on?",
        "pronunciation": "Let's work on pronunciation! 🔤 What word are you struggling with?",
        "quiz": "Quiz time! 🎯 Let's see what you remember!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            TeachVocabularyTool(),
            ConversationPracticeTool(),
            GrammarExplainTool(),
            PronunciationHelpTool(),
            QuizTool(),
        ]

    def respond_offline(self, state: VeraState) -> str:
        transcript = state.get("transcript", "").lower()
        user_name = state.get("user_name", "")
        name_part = f", {user_name}" if user_name else ""

        if any(w in transcript for w in ["vocabulary", "vocab", "words", "phrases"]):
            return f"Let's learn some new words{name_part}! 📚 What language and topic?"
        if any(w in transcript for w in ["practice", "conversation", "roleplay", "dialogue"]):
            return f"Let's practice{name_part}! 🗣️ What scenario should we try?"
        if any(w in transcript for w in ["grammar", "conjugat", "tense", "verb"]):
            return f"Grammar time{name_part}! 📝 What concept do you need help with?"
        if any(w in transcript for w in ["pronounce", "pronunciation", "say", "how do you say"]):
            return f"Let's work on pronunciation{name_part}! 🔤 What word?"
        if any(w in transcript for w in ["quiz", "test", "check"]):
            return f"Quiz time{name_part}! 🎯 Let's see what you've learned!"

        return (
            f"Hey{name_part}! I'd love to help you learn a language! 🌍\n"
            f"Which language are you interested in? I can teach Spanish, French, "
            f"German, Italian, Japanese, Korean, and more!\n"
            f"And what's your level — beginner, intermediate, or advanced?"
        )
