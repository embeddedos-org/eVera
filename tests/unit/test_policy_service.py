"""Unit tests for the safety PolicyService (issue #46 coverage drive).

Covers vera/safety/policy.py's PolicyService — used across the
agent fabric but previously exercised only indirectly. Pins the
documented evaluation order: specific rule, then agent wildcard,
then the config-level denied / confirm / allowed lists, then the
default of CONFIRM for unknown actions — plus the custom-rules
override contract.
"""

from types import SimpleNamespace

import pytest

import vera.safety.policy as policy_module
from vera.safety.policy import PolicyAction, PolicyService


@pytest.fixture
def empty_settings(monkeypatch):
    """Replace the module's settings with empty safety lists so the
    config-list layers are exercised only when a test opts in."""
    stub = SimpleNamespace(safety=SimpleNamespace(
        denied_actions=[], confirm_actions=[], allowed_actions=[]))
    monkeypatch.setattr(policy_module, "settings", stub)
    return stub


class TestSpecificRules:
    def test_allow_rule(self, policy_service):
        d = policy_service.check("companion", "chat")
        assert d.action is PolicyAction.ALLOW
        assert "Rule match: companion.chat" in d.reason

    def test_confirm_rule(self, policy_service):
        d = policy_service.check("operator", "execute_script")
        assert d.action is PolicyAction.CONFIRM

    def test_deny_rule_for_money_movement(self, policy_service):
        for agent in ("finance", "income"):
            d = policy_service.check(agent, "transfer_money")
            assert d.action is PolicyAction.DENY

    def test_decision_echoes_agent_and_tool(self, policy_service):
        d = policy_service.check("operator", "execute_script")
        assert d.agent_name == "operator"
        assert d.tool_name == "execute_script"

    def test_upload_needs_confirmation(self, policy_service):
        d = policy_service.check("media_factory", "upload_youtube")
        assert d.action is PolicyAction.CONFIRM
        gen = policy_service.check("media_factory", "generate_image")
        assert gen.action is PolicyAction.ALLOW


class TestWildcards:
    def test_wildcard_allow(self, policy_service):
        d = policy_service.check("language_tutor", "some_unlisted_tool")
        assert d.action is PolicyAction.ALLOW
        assert "Wildcard match: language_tutor.*" in d.reason

    def test_wildcard_confirm(self, policy_service):
        d = policy_service.check("work_pilot", "some_unlisted_tool")
        assert d.action is PolicyAction.CONFIRM

    def test_specific_beats_wildcard(self):
        svc = PolicyService()
        # companion.* is ALLOW and companion.chat is ALLOW too, so
        # use a custom pair where they differ to prove precedence.
        svc = PolicyService({"demo.*": PolicyAction.DENY,
                             "demo.safe_tool": PolicyAction.ALLOW})
        assert svc.check("demo", "safe_tool").action is PolicyAction.ALLOW
        assert svc.check("demo", "other").action is PolicyAction.DENY


class TestSettingsLists:
    def test_denied_list(self, policy_service, empty_settings):
        empty_settings.safety.denied_actions = ["wipe_disk"]
        d = policy_service.check("unknown_agent", "wipe_disk")
        assert d.action is PolicyAction.DENY
        assert "denied list" in d.reason

    def test_confirm_list(self, policy_service, empty_settings):
        empty_settings.safety.confirm_actions = ["send_email"]
        d = policy_service.check("unknown_agent", "send_email")
        assert d.action is PolicyAction.CONFIRM

    def test_allowed_list(self, policy_service, empty_settings):
        empty_settings.safety.allowed_actions = ["read_clock"]
        d = policy_service.check("unknown_agent", "read_clock")
        assert d.action is PolicyAction.ALLOW

    def test_denied_beats_allowed(self, policy_service, empty_settings):
        empty_settings.safety.denied_actions = ["dual_listed"]
        empty_settings.safety.allowed_actions = ["dual_listed"]
        d = policy_service.check("unknown_agent", "dual_listed")
        assert d.action is PolicyAction.DENY

    def test_rule_beats_settings_list(self, policy_service, empty_settings):
        # A specific rule resolves before the config lists are read.
        empty_settings.safety.denied_actions = ["chat"]
        d = policy_service.check("companion", "chat")
        assert d.action is PolicyAction.ALLOW


class TestDefaultAndCustomRules:
    def test_unknown_action_defaults_to_confirm(
            self, policy_service, empty_settings):
        d = policy_service.check("ghost", "haunt")
        assert d.action is PolicyAction.CONFIRM
        assert "defaulting to confirm" in d.reason

    def test_custom_rule_extends_defaults(self):
        svc = PolicyService({"lab.run_experiment": PolicyAction.DENY})
        assert svc.check("lab", "run_experiment").action is PolicyAction.DENY
        # Defaults still apply alongside the extension.
        assert svc.check("companion", "chat").action is PolicyAction.ALLOW

    def test_custom_rule_overrides_default(self):
        svc = PolicyService({"operator.execute_script": PolicyAction.DENY})
        assert svc.check("operator", "execute_script").action is PolicyAction.DENY

    def test_custom_rules_do_not_leak_between_instances(self):
        PolicyService({"lab.run_experiment": PolicyAction.DENY})
        fresh = PolicyService()
        d = fresh.check("lab", "run_experiment")
        assert d.action is PolicyAction.CONFIRM  # fell through to default

    def test_args_parameter_accepted(self, policy_service):
        d = policy_service.check("companion", "chat", args={"text": "hi"})
        assert d.action is PolicyAction.ALLOW
