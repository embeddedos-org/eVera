"""Tests for safety and privacy."""

from __future__ import annotations

from voca.safety.policy import PolicyAction, PolicyService
from voca.safety.privacy import PrivacyGuard


def test_allow_action(policy_service: PolicyService):
    decision = policy_service.check("companion", "chat")
    assert decision.action == PolicyAction.ALLOW


def test_confirm_action(policy_service: PolicyService):
    decision = policy_service.check("operator", "execute_script")
    assert decision.action == PolicyAction.CONFIRM


def test_deny_action(policy_service: PolicyService):
    decision = policy_service.check("income", "transfer_money")
    assert decision.action == PolicyAction.DENY


def test_wildcard_rule(policy_service: PolicyService):
    decision = policy_service.check("researcher", "web_search")
    assert decision.action == PolicyAction.ALLOW


def test_default_confirm(policy_service: PolicyService):
    decision = policy_service.check("unknown_agent", "unknown_tool")
    assert decision.action == PolicyAction.CONFIRM


def test_privacy_detect_pii(privacy_guard: PrivacyGuard):
    text = "My SSN is 123-45-6789 and email is test@example.com"
    detections = privacy_guard.detect_pii(text)
    types = {d.pii_type for d in detections}
    assert "ssn" in types
    assert "email" in types


def test_privacy_detect_phone(privacy_guard: PrivacyGuard):
    text = "Call me at 555-123-4567"
    detections = privacy_guard.detect_pii(text)
    assert any(d.pii_type == "phone" for d in detections)


def test_privacy_detect_credit_card(privacy_guard: PrivacyGuard):
    text = "Card number: 4111-1111-1111-1111"
    detections = privacy_guard.detect_pii(text)
    assert any(d.pii_type == "credit_card" for d in detections)


def test_privacy_anonymize(privacy_guard: PrivacyGuard):
    text = "My SSN is 123-45-6789"
    anonymized = privacy_guard.anonymize(text)
    assert "123-45-6789" not in anonymized
    assert "[REDACTED_SSN]" in anonymized


def test_privacy_no_pii(privacy_guard: PrivacyGuard):
    text = "The weather is nice today"
    assert privacy_guard.has_pii(text) is False
    assert privacy_guard.anonymize(text) == text


def test_privacy_sensitive_keywords(privacy_guard: PrivacyGuard):
    assert privacy_guard.should_process_locally("What is my password?") is True
    assert privacy_guard.should_process_locally("Tell me a joke") is False
    assert privacy_guard.should_process_locally("Store my API key") is True
