"""Tests for vera/safety/privacy.py — PrivacyGuard (issue #46 slice).

The safety package's MCP policy module got its test batch on
2026-10-13; PrivacyGuard (PII detection/anonymization and the
route-locally decision) had none. These tests pin detection per
PII type with exact spans, anonymization output, the local-routing
triggers, and custom-pattern extension.
"""

from __future__ import annotations

import re

from vera.safety.privacy import PrivacyGuard


def types_of(guard: PrivacyGuard, text: str) -> set[str]:
    return {d.pii_type for d in guard.detect_pii(text)}


class TestDetectPii:
    def test_detects_each_builtin_type(self):
        guard = PrivacyGuard()
        assert types_of(guard, "SSN 123-45-6789 on file") == {"ssn"}
        assert "credit_card" in types_of(guard, "card 4111 1111 1111 1111")
        assert types_of(guard, "mail me at dev@example.org") == {"email"}
        assert types_of(guard, "call 555-123-4567 today") == {"phone"}
        assert types_of(guard, "host 192.168.1.10 is down") == {"ip_address"}

    def test_detection_spans_point_at_the_value(self):
        guard = PrivacyGuard()
        text = "reach dev@example.org please"
        (det,) = guard.detect_pii(text)
        assert det.value == "dev@example.org"
        assert text[det.start : det.end] == det.value

    def test_clean_text_detects_nothing(self):
        guard = PrivacyGuard()
        assert guard.detect_pii("the weather is fine today") == []
        assert guard.has_pii("the weather is fine today") is False

    def test_multiple_detections_in_one_text(self):
        guard = PrivacyGuard()
        found = types_of(guard, "from 10.0.0.1, mail dev@example.org")
        assert found == {"ip_address", "email"}


class TestAnonymize:
    def test_replaces_pii_with_typed_placeholders(self):
        guard = PrivacyGuard()
        out = guard.anonymize("mail dev@example.org or call 555-123-4567")
        assert "dev@example.org" not in out
        assert "555-123-4567" not in out
        assert "[REDACTED_EMAIL]" in out
        assert "[REDACTED_PHONE]" in out

    def test_anonymize_preserves_surrounding_text(self):
        guard = PrivacyGuard()
        out = guard.anonymize("SSN 123-45-6789 on file")
        assert out == "SSN [REDACTED_SSN] on file"

    def test_anonymize_without_pii_is_identity(self):
        guard = PrivacyGuard()
        assert guard.anonymize("nothing to hide") == "nothing to hide"


class TestShouldProcessLocally:
    def test_sensitive_keyword_routes_locally(self):
        guard = PrivacyGuard()
        assert guard.should_process_locally("what is my bank account balance") is True
        assert guard.should_process_locally("I forgot my password again") is True

    def test_pii_routes_locally_even_without_keywords(self):
        guard = PrivacyGuard()
        assert guard.should_process_locally("send it to 192.168.1.10") is True

    def test_ordinary_text_does_not_route_locally(self):
        guard = PrivacyGuard()
        assert guard.should_process_locally("summarize the meeting notes") is False


class TestCustomPatterns:
    def test_custom_pattern_is_added(self):
        guard = PrivacyGuard({"ticket": re.compile(r"\bEOS-\d+\b")})
        assert types_of(guard, "see EOS-1234 for details") == {"ticket"}
        # Builtins still work alongside.
        assert "email" in types_of(guard, "EOS-1234 or dev@example.org")

    def test_custom_pattern_can_shadow_a_builtin_name(self):
        guard = PrivacyGuard({"email": re.compile(r"\bINTERNAL\b")})
        assert types_of(guard, "this is INTERNAL only") == {"email"}
