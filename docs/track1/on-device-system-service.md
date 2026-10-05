# eVera as the on-device system service (Track 1)

**Status:** Design sketch. **Date:** 2026-10-05
**Cross-links:** `eAI` `docs/track1/runtime-api.md`, `eIPC`
`docs/track1/zero-copy-tensor-ipc.md`, EoSim `docs/mcp-gateway-eval.md`,
`eos` `docs/track1/accelerator-hal-profiles.md`.

> Constraint: org billing is exhausted, so this is a docs-only change.
> No code lands until CI can verify it (blocked register).

## 1. The flip: from cloud chatbot to resident system service

eVera today reads as a cloud chatbot. Track 1 reframes it: eVera is the
**resident system service with a body** — the on-device agent that owns
the user's intent loop and drives the local MCP fabric on their behalf.

What changes:

- **Residency:** eVera runs as a system service, not an app. It starts
  at boot, outlives any single app, and is addressable by the rest of
  the system (other services, the shell, hardware buttons).
- **A body:** it has actuators — it can drive the EoSim MCP server, the
  hardware bridges (serial/MQTT/Modbus), and the CAD surface through
  the MCP gateway, not just answer questions.
- **Local-first:** inference runs through the eAI runtime API
  (on-device models via the accelerator HAL). The cloud is a fallback
  for intents the local model declines, not the default path.

What doesn't change: eVera remains the conversational interface. The
flip is architectural (where it runs, what it can touch), not a rebrand.

## 2. Service shape

### Lifecycle

```
boot → register tools → serve intents → suspend on power budget
```

- **Boot:** the service starts with the system, attests its model
  envelope (eos #162), and loads its capability claims.
- **Register tools:** it connects to the MCP gateway as a client and
  discovers the tools relevant to the current context (progressive
  discovery — it doesn't hold every tool, just the ones the gateway
  offers for the active intent).
- **Serve intents:** the intent loop — parse intent, plan tool calls,
  execute via the gateway, report. Tensor payloads move over the
  zero-copy eIPC transport; control stays on eIPC channels.
- **Suspend on power budget:** when the power manager signals a budget,
  eVera sheds load in order — pause background intents, drop to a
  smaller local model, and finally suspend tool access while keeping
  the conversational core warm. Resume reverses the order.

### Capability scoping

eVera inherits the envelope capability claims: it can only drive tools
its claimed capabilities allow (e.g. `camera_frames: read` →
vision tools; `mic_frames: none` → no audio tools). The gateway
enforces per-call; violations revoke the session (fail closed, per the
eIPC transport design).

### Inference path

Local-first via the eAI runtime API: models are loadable modules with
declared capabilities; the accelerator HAL picks the backend tier
(tiny: CMSIS-NN/ESP-NN class; large: AIE class). Cloud fallback only
for declined intents, and only when the manifest allows
`inference.cloud` (cf. eApps `ai_capabilities`).

## 3. Relationship to the MCP gateway

The gateway evaluation (EoSim `docs/mcp-gateway-eval.md`) selected
**Klavis Strata**. To be explicit about roles:

- **Strata is the gateway.** It fronts the MCP servers (EoSim MCP,
  fw-context-mcp, hardware bridges, CAD surface, embeddedos-docs).
- **eVera is a client of the gateway.** It does not implement gateway
  duties (routing, discovery, policy) — it consumes them.

This keeps the architecture honest: one gateway to secure and audit,
many clients (eVera, EoStudio agents, CI agents) that inherit its
policy.

## Open questions

- Intent-planning model size vs. on-device RAM budget (tiny-tier HAL).
- How eVera's tool-access audit log feeds the CRA incident runbook
  (eSec) — agent tool calls are security-relevant events.
- Multi-user / multi-tenant scoping when the device is shared.
