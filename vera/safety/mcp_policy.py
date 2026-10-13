"""MCP tool-use policy as code — server-config gate (Refs #46).

@file vera/safety/mcp_policy.py
@brief Enforces docs/mcp-tool-use-policy.md for MCP server configs:
       no executable commands from configuration, server allowlist,
       no credential fields in config, and pinned source/version
       (provenance) for every server.

Credential isolation (design rule): following the gateway-broker
pattern, a gateway brokers credentials at call time and the agent
never holds the token. This policy enforces that rule from the
config side: a server config that itself carries credential fields
(``api_key``, ``token``, ``password``, credential-bearing ``env``,
...) is denied outright, so credentials can only ever arrive via
the broker at call time — never via a config file an agent (or an
attacker who can influence one) supplies. The Langflow
CVE-2026-105697 shape — a config whose ``command``/``args`` were
executed via ``bash -c`` — is denied for the same reason: config is
data, never a source of executables.

The gate is deny-closed: with no allowlist configured, every server
is denied.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

from vera.safety.policy import PolicyAction, PolicyDecision

logger = logging.getLogger(__name__)

# Fields that turn a config into an executable (Langflow shape).
_EXECUTABLE_FIELDS = ("command", "args", "shell")

# Top-level fields that mean the config itself carries credentials.
_CREDENTIAL_FIELDS = {
    "api_key",
    "apikey",
    "api_key_env",
    "token",
    "access_token",
    "refresh_token",
    "auth_token",
    "authorization",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "credentials",
    "credential",
    "private_key",
}

# Substrings that mark a credential inside a nested ``env`` mapping.
_CREDENTIAL_MARKERS = ("key", "token", "secret", "password", "passwd", "credential")

# Fields that pin a server to a reviewed source/version.
_PIN_FIELDS = ("version", "pin", "pinned_version", "digest", "sha256", "commit")


def _load_allowlist_from_settings() -> frozenset:
    """Allowlist from settings; safe empty default (deny-closed).

    Reads ``settings.safety.mcp_allowlist`` (or ``mcp_allowed_servers``)
    when present. Any failure — settings unavailable, field absent —
    yields the empty allowlist, which denies everything.
    """
    try:
        from config import settings

        safety = getattr(settings, "safety", None)
        raw = getattr(safety, "mcp_allowlist", None)
        if raw is None:
            raw = getattr(safety, "mcp_allowed_servers", None)
        if isinstance(raw, dict):
            return frozenset(str(k) for k in raw)
        if isinstance(raw, (list, tuple, set, frozenset)):
            return frozenset(str(v) for v in raw)
    except Exception:  # settings must never open the gate on failure
        logger.debug("MCP allowlist: settings unavailable; deny-closed", exc_info=True)
    return frozenset()


#: Server ids / names / URLs that may be connected to. Empty = deny all.
MCP_ALLOWLIST: frozenset = _load_allowlist_from_settings()


def _norm_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def _decision(action: PolicyAction, reason: str, server: str) -> PolicyDecision:
    return PolicyDecision(
        action=action,
        reason=reason,
        agent_name="mcp",
        tool_name=server or "unknown",
    )


def _credential_field_in(entry: dict) -> Optional[str]:
    """Name of the first credential field the entry carries, if any."""
    for key in entry:
        if _norm_key(key) in _CREDENTIAL_FIELDS:
            return str(key)
    env = entry.get("env")
    if isinstance(env, dict):
        for key in env:
            norm = _norm_key(key)
            if any(marker in norm for marker in _CREDENTIAL_MARKERS):
                return f"env.{key}"
    return None


def _is_pinned(entry: dict) -> bool:
    return any(entry.get(field) for field in _PIN_FIELDS)


def _check_one(entry: Any, server_key: Optional[str], allowlist: frozenset) -> PolicyDecision:
    """Check a single server entry against every rule (deny-first)."""
    if not isinstance(entry, dict):
        return _decision(
            PolicyAction.DENY, "MCP server config entry must be an object", server_key or "unknown"
        )
    server_id = str(entry.get("id") or entry.get("name") or server_key or "")
    url = str(entry.get("url") or entry.get("endpoint") or "")
    label = server_id or url or "unknown"

    # Rule: no executable commands from configuration (Langflow shape).
    for field in _EXECUTABLE_FIELDS:
        if entry.get(field):
            return _decision(
                PolicyAction.DENY,
                f"MCP server {label!r} denied: config carries executable "
                f"field {field!r}; commands must come from the allowlist, "
                "never from configuration",
                label,
            )

    # Rule: configs never carry credentials (brokered at call time).
    cred = _credential_field_in(entry)
    if cred is not None:
        return _decision(
            PolicyAction.DENY,
            f"MCP server {label!r} denied: config carries credential "
            f"field {cred!r}; credentials are brokered by the gateway "
            "at call time and are never held in config",
            label,
        )

    # Rule: server must be identifiable and allowlisted (deny-closed).
    if not server_id and not url:
        return _decision(
            PolicyAction.DENY,
            "MCP server denied: config has no server id/name or URL to "
            "match against the allowlist",
            label,
        )
    if server_id not in allowlist and url not in allowlist:
        return _decision(
            PolicyAction.DENY,
            f"MCP server {label!r} denied: not in the MCP allowlist",
            label,
        )

    # Rule: provenance — a pinned source/version is required.
    if not _is_pinned(entry):
        return _decision(
            PolicyAction.DENY,
            f"MCP server {label!r} denied: no pinned source/version "
            f"(one of {', '.join(_PIN_FIELDS)} is required)",
            label,
        )

    return _decision(
        PolicyAction.ALLOW,
        f"MCP server {label!r} allowed: allowlisted and pinned, no "
        "executable or credential fields in config",
        label,
    )


def check_server_config(
    cfg: dict, allowlist: Optional[Iterable[str]] = None
) -> PolicyDecision:
    """Decide whether an MCP server config may be used.

    ``cfg`` is either a single server entry (``{"id"/"name"/"url": ...,
    "version"/"digest": ...}``) or a wrapper holding entries under
    ``mcpServers`` (a mapping of server id -> entry, the common MCP
    config shape) or ``servers`` (a list of entries). A wrapper is
    allowed only when *every* entry is allowed.

    ``allowlist`` overrides :data:`MCP_ALLOWLIST` (from settings) when
    given; the default is deny-closed.
    """
    allowed = MCP_ALLOWLIST if allowlist is None else frozenset(str(v) for v in allowlist)
    if not isinstance(cfg, dict):
        return _decision(PolicyAction.DENY, "MCP server config must be an object", "unknown")

    entries: list[tuple[Any, Optional[str]]] = []
    servers = cfg.get("mcpServers", cfg.get("mcp_servers"))
    if isinstance(servers, dict):
        entries = [(entry, str(key)) for key, entry in servers.items()]
    elif isinstance(cfg.get("servers"), list):
        entries = [(entry, None) for entry in cfg["servers"]]
    else:
        entries = [(cfg, None)]

    if not entries:
        return _decision(PolicyAction.DENY, "MCP server config names no servers", "unknown")

    last_allow: Optional[PolicyDecision] = None
    for entry, key in entries:
        decision = _check_one(entry, key, allowed)
        if decision.action == PolicyAction.DENY:
            return decision
        last_allow = decision
    assert last_allow is not None  # entries is non-empty
    return last_allow


__all__ = ["MCP_ALLOWLIST", "check_server_config"]
