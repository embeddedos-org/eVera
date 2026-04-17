"""Companion Agent — open conversation, emotional support, and companionship."""

from __future__ import annotations

import random
from datetime import datetime

from voca.brain.agents.base import BaseAgent, Tool
from voca.brain.state import VocaState
from voca.providers.models import ModelTier


JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
    "Why was the JavaScript developer sad? Because he didn't Node how to Express himself. 😅",
    "There are only 10 types of people in the world: those who understand binary and those who don't. 🤓",
    "Why do Java developers wear glasses? Because they can't C#. 👓",
    "A SQL query walks into a bar, walks up to two tables and asks... 'Can I join you?' 🍻",
    "Why did the developer go broke? Because he used up all his cache. 💸",
    "How many programmers does it take to change a light bulb? None, that's a hardware problem. 💡",
    "Why do programmers hate nature? It has too many bugs and no documentation! 🌿🐛",
]

ACTIVITIES = [
    "How about going for a short walk? Fresh air does wonders! 🚶 I'll be right here when you get back!",
    "Maybe try a 5-minute meditation or deep breathing exercise? 🧘 You deserve a breather!",
    "You could listen to some music or a podcast you enjoy 🎵 I can wait!",
    "How about making yourself a nice cup of coffee or tea? ☕ Treat yourself, buddy!",
    "Try sketching or doodling something — it's surprisingly relaxing 🎨",
    "Maybe do a quick stretch session? Your body will thank you! 💪",
]

MOOD_RESPONSES = {
    "happy": "That's wonderful to hear! 😊 What's making your day great? I wanna celebrate with you! 🎉",
    "sad": "I'm sorry you're feeling down 😔 Remember, it's okay to have tough days. Want to talk about it? I'm right here for you.",
    "tired": "Sounds like you could use some rest, buddy. Maybe take a short break? 😴 I'll be here when you're recharged!",
    "bored": "Let's fix that! 🎯 I can suggest an activity, tell a joke, or we can chat about anything. What sounds good?",
    "stressed": "I hear you 💙 Take a deep breath with me... in... out... Better? Want to talk about what's on your mind?",
    "excited": "That's awesome energy! 🔥 What's got you so pumped? Tell me everything!",
    "angry": "I get it, frustration is real 😤 Want to vent? Or should I distract you with something fun?",
}


class CompanionAgent(BaseAgent):
    """Open conversation, emotional support, and companionship."""

    name = "companion"
    description = "Open conversation, emotional support, and companionship"
    tier = ModelTier.EXECUTOR
    system_prompt = (
        "You are a warm, emotionally intelligent companion. You engage in open "
        "conversation, provide emotional support, check in on mood, suggest activities, "
        "and share humor. Be authentic, empathetic, and personable. Remember user "
        "preferences and past conversations."
    )

    offline_responses = {
        "chat": "I'm here to chat, buddy! 💬 What's on your mind?",
        "joke": "",
        "mood": "How are you feeling? I'm here to listen 😊",
        "activity": "",
        "conversation": "I'm all ears! 👂 What would you like to talk about?",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            Tool(name="chat", description="General conversation",
                 parameters={"topic": {"type": "str", "description": "Conversation topic"}}),
            Tool(name="check_mood", description="Assess and respond to mood",
                 parameters={"observation": {"type": "str", "description": "Observed mood cues"}}),
            Tool(name="suggest_activity", description="Suggest activities",
                 parameters={"preferences": {"type": "str", "description": "User preferences"}}),
            Tool(name="tell_joke", description="Tell a joke",
                 parameters={"category": {"type": "str", "description": "Joke category"}}),
        ]

    def respond_offline(self, state: VocaState) -> str:
        """Smart offline responses for companion interactions."""
        transcript = state.get("transcript", "").lower()
        intent = state.get("intent", "")
        user_name = state.get("user_name", "")

        # Name introduction detection
        if any(phrase in transcript for phrase in ["my name is", "call me", "i'm ", "i am "]):
            if user_name:
                return f"Nice to meet you, {user_name}! 🎉 I'm Voca, your buddy! I'll remember your name. What can I do for you?"
            return "Nice to meet you! 🎉 I'm Voca, your buddy! What can I help you with?"

        name_greeting = f", {user_name}" if user_name else ""

        # Jokes
        if intent == "joke" or "joke" in transcript or "funny" in transcript or "laugh" in transcript:
            joke = random.choice(JOKES)
            return f"Here's one for you{name_greeting}! 😄\n\n{joke}"

        # Activities
        if intent == "activity" or "bored" in transcript or "activity" in transcript or "suggest" in transcript:
            return random.choice(ACTIVITIES)

        # Mood check
        if intent == "mood" or "feeling" in transcript or "how am i" in transcript:
            for mood, response in MOOD_RESPONSES.items():
                if mood in transcript:
                    return response
            return f"How are you feeling{name_greeting}? I'm here to listen, buddy! 😊"

        # Time-based greetings
        hour = datetime.now().hour
        if hour < 12:
            greeting = f"Good morning{name_greeting}! ☀️"
        elif hour < 17:
            greeting = f"Hey{name_greeting}! Hope your afternoon's going well 🌤️"
        else:
            greeting = f"Good evening{name_greeting}! 🌙"

        # First-time greeting if no name known
        if not user_name:
            prompts = [
                f"{greeting} I'm Voca, your AI buddy! 👋 What should I call you?",
                "Hey there! I'm Voca! 👋 Before we get started — what's your name?",
                f"{greeting} I don't think we've properly met! What's your name, friend?",
            ]
            return random.choice(prompts)

        # General chat with name
        prompts = [
            f"{greeting} What's on your mind?",
            f"Hey {user_name}! I'm here whenever you need to chat 💬 What's up?",
            f"Hey {user_name}! How can I brighten your day? ✨",
            f"{greeting} I'm all ears — tell me anything!",
        ]
        return random.choice(prompts)
