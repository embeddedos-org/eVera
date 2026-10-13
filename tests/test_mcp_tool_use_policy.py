"""Tests for the MCP tool-use policy gate (vera/safety/mcp_policy.py).

Covers docs/mcp-tool-use-policy.md as code: the Langflow
CVE-2026-105697 config shape is denied, an allowlisted + pinned
server without a command is allowed, and unknown / credential-bearing
/ unpinned configs are all denied (deny-closed).
"""

import pytest

from vera.safety.mcp_policy import MCP_ALLOWLIST, check_server_config
from vera.safety.policy import PolicyAction

ALLOWLIST = {"filesystem", "https://mcp.example.com/files"}


def _pinned(**extra):
    cfg = {"id": "filesystem", "version": "1.2.3"}
    cfg.update(extra)
    return cfg


def test_langflow_shaped_config_is_denied():
    # CVE-2026-105697: user-supplied command/args executed via bash -c.
    cfg = {"mcpServers": {"evil": {"command": "bash", "args": ["-c", "id"]}}}
    decision = check_server_config(cfg, allowlist=ALLOWLIST)
    assert decision.action == PolicyAction.DENY
    assert "command" in decision.reason


@pytest.mark.parametrize("field,value", [("command", "bash"), ("args", ["-c", "id"]), ("shell", "bash -c id")])
def test_any_executable_field_is_denied(field, value):
    decision = check_server_config(_pinned(**{field: value}), allowlist=ALLOWLIST)
    assert decision.action == PolicyAction.DENY


def test_allowlisted_pinned_server_without_command_is_allowed():
    decision = check_server_config(_pinned(), allowlist=ALLOWLIST)
    assert decision.action == PolicyAction.ALLOW


def test_allowlist_may_match_by_url():
    cfg = {"url": "https://mcp.example.com/files", "digest": "sha256:abc123"}
    decision = check_server_config(cfg, allowlist=ALLOWLIST)
    assert decision.action == PolicyAction.ALLOW


def test_unknown_server_is_denied():
    cfg = {"id": "not-a-real-server", "version": "0.0.1"}
    decision = check_server_config(cfg, allowlist=ALLOWLIST)
    assert decision.action == PolicyAction.DENY
    assert "allowlist" in decision.reason


@pytest.mark.parametrize("field", ["api_key", "token", "password", "client_secret"])
def test_credential_field_is_denied(field):
    decision = check_server_config(_pinned(**{field: "hunter2"}), allowlist=ALLOWLIST)
    assert decision.action == PolicyAction.DENY
    assert "credential" in decision.reason


def test_credential_in_env_is_denied():
    decision = check_server_config(_pinned(env={"OPENAI_API_KEY": "sk-x"}), allowlist=ALLOWLIST)
    assert decision.action == PolicyAction.DENY


def test_allowlisted_but_unpinned_is_denied():
    decision = check_server_config({"id": "filesystem"}, allowlist=ALLOWLIST)
    assert decision.action == PolicyAction.DENY
    assert "pinned" in decision.reason


def test_default_allowlist_is_deny_closed(monkeypatch):
    # Safe empty default: with nothing allowlisted, even a clean,
    # pinned config is denied.
    monkeypatch.setattr("vera.safety.mcp_policy.MCP_ALLOWLIST", frozenset())
    decision = check_server_config(_pinned())
    assert decision.action == PolicyAction.DENY
    assert isinstance(MCP_ALLOWLIST, frozenset)


def test_wrapper_denies_if_any_entry_denies():
    cfg = {
        "mcpServers": {
            "filesystem": {"version": "1.2.3"},
            "sneaky": {"version": "9.9.9", "command": "bash"},
        }
    }
    decision = check_server_config(cfg, allowlist=ALLOWLIST)
    assert decision.action == PolicyAction.DENY
