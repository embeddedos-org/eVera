"""Language support — multi-language detection, translation, and spell correction."""

from __future__ import annotations

import logging
import re
from difflib import get_close_matches

logger = logging.getLogger(__name__)

# Supported languages with speech recognition codes
SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "speech_code": "en-US", "flag": "🇺🇸"},
    "es": {"name": "Spanish", "speech_code": "es-ES", "flag": "🇪🇸"},
    "fr": {"name": "French", "speech_code": "fr-FR", "flag": "🇫🇷"},
    "de": {"name": "German", "speech_code": "de-DE", "flag": "🇩🇪"},
    "hi": {"name": "Hindi", "speech_code": "hi-IN", "flag": "🇮🇳"},
    "te": {"name": "Telugu", "speech_code": "te-IN", "flag": "🇮🇳"},
    "ta": {"name": "Tamil", "speech_code": "ta-IN", "flag": "🇮🇳"},
    "ja": {"name": "Japanese", "speech_code": "ja-JP", "flag": "🇯🇵"},
    "ko": {"name": "Korean", "speech_code": "ko-KR", "flag": "🇰🇷"},
    "zh": {"name": "Chinese", "speech_code": "zh-CN", "flag": "🇨🇳"},
    "pt": {"name": "Portuguese", "speech_code": "pt-BR", "flag": "🇧🇷"},
    "ru": {"name": "Russian", "speech_code": "ru-RU", "flag": "🇷🇺"},
    "ar": {"name": "Arabic", "speech_code": "ar-SA", "flag": "🇸🇦"},
    "it": {"name": "Italian", "speech_code": "it-IT", "flag": "🇮🇹"},
    "nl": {"name": "Dutch", "speech_code": "nl-NL", "flag": "🇳🇱"},
    "pl": {"name": "Polish", "speech_code": "pl-PL", "flag": "🇵🇱"},
    "tr": {"name": "Turkish", "speech_code": "tr-TR", "flag": "🇹🇷"},
    "vi": {"name": "Vietnamese", "speech_code": "vi-VN", "flag": "🇻🇳"},
    "th": {"name": "Thai", "speech_code": "th-TH", "flag": "🇹🇭"},
}

# Common voice command words for spell correction
COMMAND_VOCABULARY = [
    # Apps
    "chrome",
    "firefox",
    "edge",
    "safari",
    "spotify",
    "discord",
    "slack",
    "zoom",
    "teams",
    "outlook",
    "excel",
    "word",
    "powerpoint",
    "notepad",
    "calculator",
    "terminal",
    "explorer",
    "vscode",
    "code",
    # Actions
    "open",
    "close",
    "launch",
    "start",
    "stop",
    "play",
    "pause",
    "search",
    "find",
    "create",
    "delete",
    "move",
    "copy",
    "edit",
    "write",
    "read",
    "send",
    "schedule",
    "remind",
    "set",
    "check",
    "turn",
    "lock",
    "unlock",
    "buy",
    "sell",
    "login",
    "navigate",
    # Targets
    "lights",
    "thermostat",
    "temperature",
    "door",
    "music",
    "volume",
    "calendar",
    "reminder",
    "email",
    "todo",
    "file",
    "folder",
    "screenshot",
    "screen",
    "browser",
    "website",
    # Stock
    "stock",
    "price",
    "portfolio",
    "watchlist",
    "market",
    "shares",
    "apple",
    "tesla",
    "google",
    "microsoft",
    "amazon",
    "nvidia",
    # Misc
    "hello",
    "hey",
    "vera",
    "buddy",
    "thanks",
    "help",
    "joke",
    "weather",
    "time",
    "date",
    "timer",
    "alarm",
]

# Common spelling mistakes from voice recognition
VOICE_CORRECTIONS = {
    "boca": "vera",
    "boka": "vera",
    "veral": "vera",
    "walker": "vera",
    "crome": "chrome",
    "chrom": "chrome",
    "fire fox": "firefox",
    "edg": "edge",
    "spottify": "spotify",
    "discorde": "discord",
    "vs cod": "vscode",
    "vis code": "vscode",
    "calculater": "calculator",
    "calender": "calendar",
    "calander": "calendar",
    "remaind": "remind",
    "remined": "remind",
    "scedule": "schedule",
    "shcedule": "schedule",
    "temperture": "temperature",
    "temprature": "temperature",
    "thermastat": "thermostat",
    "termstat": "thermostat",
    "screanshot": "screenshot",
    "screeenshot": "screenshot",
    "portfoilio": "portfolio",
    "potfolio": "portfolio",
    "watchilist": "watchlist",
    "watchlust": "watchlist",
    "opne": "open",
    "oepn": "open",
    "serach": "search",
    "seach": "search",
    "delet": "delete",
    "deleet": "delete",
    "creat": "create",
    "craete": "create",
}


def correct_spelling(text: str) -> str:
    """Correct common voice recognition spelling errors."""
    if not text:
        return text

    corrected = text.lower()

    # Apply known corrections
    for wrong, right in VOICE_CORRECTIONS.items():
        corrected = re.sub(r"\b" + re.escape(wrong) + r"\b", right, corrected, flags=re.I)

    # Fuzzy match each word against command veraboulary
    words = corrected.split()
    fixed_words = []
    for word in words:
        if len(word) < 3:
            fixed_words.append(word)
            continue

        # Check if word is already valid
        if word.lower() in COMMAND_VOCABULARY:
            fixed_words.append(word)
            continue

        # Try fuzzy match
        matches = get_close_matches(word.lower(), COMMAND_VOCABULARY, n=1, cutoff=0.9)
        if matches:
            fixed_words.append(matches[0])
            logger.debug("Spell corrected: '%s' → '%s'", word, matches[0])
        else:
            fixed_words.append(word)

    # Preserve original case for first word
    result = " ".join(fixed_words)
    if text[0].isupper() and result:
        result = result[0].upper() + result[1:]

    return result


def detect_language(text: str) -> str:
    """Simple language detection based on character ranges."""
    if not text:
        return "en"

    # Check for non-Latin scripts
    for char in text:
        code = ord(char)
        if 0x0900 <= code <= 0x097F:
            return "hi"  # Devanagari (Hindi)
        if 0x0C00 <= code <= 0x0C7F:
            return "te"  # Telugu
        if 0x0B80 <= code <= 0x0BFF:
            return "ta"  # Tamil
        if 0x3040 <= code <= 0x309F or 0x30A0 <= code <= 0x30FF:
            return "ja"  # Japanese
        if 0xAC00 <= code <= 0xD7AF:
            return "ko"  # Korean
        if 0x4E00 <= code <= 0x9FFF:
            return "zh"  # Chinese
        if 0x0400 <= code <= 0x04FF:
            return "ru"  # Cyrillic (Russian)
        if 0x0600 <= code <= 0x06FF:
            return "ar"  # Arabic

    # Check for common language indicators in Latin text
    lower = text.lower()
    if any(w in lower for w in ["¿", "¡", "está", "hola", "cómo", "qué", "gracias"]):
        return "es"
    if any(w in lower for w in ["bonjour", "merci", "comment", "oui", "très"]):
        return "fr"
    if any(w in lower for w in ["danke", "bitte", "guten", "wie", "ich"]):
        return "de"
    if any(w in lower for w in ["obrigado", "como", "você", "muito"]):
        return "pt"
    if any(w in lower for w in ["grazie", "come", "molto", "buongiorno"]):
        return "it"

    return "en"


def get_speech_code(lang: str) -> str:
    """Get the Web Speech API language code."""
    lang_info = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["en"])
    return lang_info["speech_code"]


def get_language_name(lang: str) -> str:
    """Get the display name for a language code."""
    lang_info = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["en"])
    return f"{lang_info['flag']} {lang_info['name']}"


def get_multilingual_system_prompt(lang: str) -> str:
    """Get system prompt instruction for responding in the user's language."""
    if lang == "en":
        return ""
    name = SUPPORTED_LANGUAGES.get(lang, {}).get("name", "English")
    return (
        f"\nThe user is communicating in {name}. "
        f"Respond in {name} naturally while maintaining your buddy personality. "
        f"Use {name} emoji and cultural references when appropriate.\n"
    )
