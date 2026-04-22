"""Privacy guard — PII detection and anonymization."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# PII detection patterns
PII_PATTERNS: dict[str, re.Pattern] = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}

# Keywords indicating sensitive topics
SENSITIVE_KEYWORDS = {
    "password",
    "secret",
    "api key",
    "token",
    "credential",
    "bank account",
    "routing number",
    "social security",
    "credit card",
    "ssn",
    "pin number",
}


@dataclass
class PIIDetection:
    """A detected PII instance."""

    pii_type: str
    value: str
    start: int
    end: int


class PrivacyGuard:
    """Detects and anonymizes PII in text."""

    def __init__(self, custom_patterns: dict[str, re.Pattern] | None = None) -> None:
        self._patterns = dict(PII_PATTERNS)
        if custom_patterns:
            self._patterns.update(custom_patterns)

    def detect_pii(self, text: str) -> list[PIIDetection]:
        detections = []
        for pii_type, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                detections.append(
                    PIIDetection(
                        pii_type=pii_type,
                        value=match.group(),
                        start=match.start(),
                        end=match.end(),
                    )
                )
        return detections

    def anonymize(self, text: str) -> str:
        """Replace all detected PII with [REDACTED_TYPE] placeholders."""
        result = text
        # Process in reverse order to preserve positions
        detections = sorted(self.detect_pii(text), key=lambda d: d.start, reverse=True)
        for det in detections:
            placeholder = f"[REDACTED_{det.pii_type.upper()}]"
            result = result[: det.start] + placeholder + result[det.end :]
        return result

    def has_pii(self, text: str) -> bool:
        return len(self.detect_pii(text)) > 0

    def should_process_locally(self, transcript: str) -> bool:
        """Check if transcript contains sensitive content that should stay local."""
        lower = transcript.lower()
        # Check for sensitive keywords
        for keyword in SENSITIVE_KEYWORDS:
            if keyword in lower:
                logger.info("Sensitive keyword detected: '%s' — routing locally", keyword)
                return True
        # Check for PII
        if self.has_pii(transcript):
            logger.info("PII detected in transcript — routing locally")
            return True
        return False
