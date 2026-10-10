# MCP Tool-Use Policy

eVera tools that speak the Model Context Protocol (MCP) — or that consume
output from MCP servers — follow this policy. It exists because the threat
landscape moved in October 2026: the risk is now understood to sit **in the
MCP protocol itself**, not just in individual server implementations.

## Threat landscape (October 2026)

- **Six MCP attack classes (Enterprise MCP Guide, Oct 8):** prompt
  injection, tool description poisoning, OAuth token theft, excessive
  tool permissions, shadow MCP servers, and tool impersonation.
  Against eVera's on-device posture:
  - *Prompt injection / tool description poisoning* — the tool-policy
    allowlist and the "command in config" ban (Langflow rule above)
    are the controls; poisoned descriptions are untrusted input.
  - *OAuth token theft / excessive tool permissions* — eVera's Safety
    Policy Engine scopes every tool call; no tool runs with ambient
    authority.
  - *Shadow MCP servers / tool impersonation* — server identity must
    be pinned before a tool is trusted; an unlisted server is hostile
    until verified, per this policy's server-allowlist rule.
- **ClawSecure AI Agent Threat Report Vol 1** (Sept 24, reported Oct 6):
  cracked Linear MCP, Notion, and Dropbox Dash. Their conclusion: *"the gap
  sits in the MCP protocol itself, not in any one company's code."*
- **Unpatched US federal MCP servers** (reported Oct 6): five federal MCP
  servers — including one logging veterans' SSNs in **unredacted error
  responses** — remained unpatched six weeks after fixes shipped elsewhere.
- **Chain-of-trust analysis** (Oct 6): MCP servers store credentials for every
  agent on the network, and agents trust each other by default. A single
  compromised agent becomes a launchpad into every connected system.
- The MCP specification itself carries **no normative security requirements**
  (per the protocol-pivoting research disclosures); intra-network trust is
  implicit unless we explicitly remove it.
- **CVE-2026-105697 (CVSS 9.9, disclosed Oct 5):** Langflow's MCP server
  configuration executed the user-typed `command` wrapped in `bash -c`
  with no allowlist -- a config file became arbitrary OS command
  execution on the host (patch: 1.10.3). This is *exactly* what this
  policy's command-allowlist rule forbids: an agent platform that runs
  user-supplied commands from configuration is the threat model, and
  Langflow is the CVSS 9.9 validation that the rule is load-bearing,
  not bureaucratic.

## Policy

1. **Credential isolation.** MCP servers never receive eVera credentials.
   Secrets live in the agent's credential store; servers get scoped,
   short-lived tokens minted per task, never the master keys.
2. **Server allowlist.** eVera connects only to explicitly allowlisted MCP
   servers. A server not on the list is treated as hostile: no connection,
   no tool discovery, no prompt-injection surface.
3. **Pinned versions.** Each allowlisted server is pinned to a reviewed
   version (digest, not just tag). Upgrades are a deliberate, reviewed change
   — never silent auto-update.
4. **Approval on config changes.** Adding/removing/allowlisting a server, or
   changing its pin, requires explicit approval through the Safety Policy
   Engine (`CONFIRM` or stricter). See `docs/security.md`.
5. **No implicit intra-network trust.** Data arriving over MCP — tool results,
   prompts, error messages — is **untrusted input**, even when it came from
   "inside" our own tool mesh. It is validated and sanitized before it can
   influence agent decisions or reach other tools.
6. **Upstream-response redaction.** Error responses and tool outputs are
   scrubbed for PII/secrets **before** logging, display, or forwarding. The
   federal SSN-in-error-response incident is the case study: redaction is a
   transport requirement, not a logging afterthought.
7. **No executable commands from configuration.** MCP server configs
   (stdio transport `command`/`args`) are never a source of
   executables: the command must come from the allowlist, and a config
   naming an unlisted executable is rejected before any process
   spawns. The Langflow CVE-2026-105697 case study above is why this is
   a numbered rule, not a guideline — a config file became arbitrary
   OS command execution (CVSS 9.9) because the platform ran
   user-supplied commands wrapped in `bash -c`.

## Mapping to the Safety Policy Engine

| Policy item | Engine mapping |
|---|---|
| New MCP server allowlist entry | `CONFIRM` (human approval) |
| Server version pin change | `CONFIRM` |
| Tool call to an allowlisted server | `ALLOW` per `agent.tool` rule, subject to items 5–6 |
| Any MCP traffic from a non-allowlisted server | `DENY` |
| Unlisted executable in a server config | `DENY` before spawn |

## Track 1 note: always-on tier

The on-device agent needs an **always-on low-power tier**, not one big model.
The shipping pattern to follow is the dual-NPU split (performance NPU for
bursts + efficiency NPU for sensing/invocation/scheduling at a fraction of the
power): the local-model roster should pair a tiny always-on model with a
larger on-demand model, selected by power state. See `docs/track1/`.

## References

- ClawSecure AI Agent Threat Report Vol 1 (Sept 2026)
- Researcher disclosure: same MCP flaw class at Google/JPMorgan/two governments
- eVera Safety Policy Engine: `docs/security.md`
- Agent fabric posture: embeddedos-org daily plan, "Agent fabric" section
