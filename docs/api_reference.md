# 🔌 API Reference

All endpoints are served by the FastAPI backend on `http://localhost:8000`.

---

## Authentication

If `VOCA_SERVER_API_KEY` is set, all endpoints (except `/`, `/health`, and `/static/*`) require authentication:

```
Authorization: Bearer <your-api-key>
```

Or as a query parameter:

```
GET /status?api_key=<your-api-key>
```

---

## REST Endpoints

### `GET /health`

Health check.

**Response:**
```json
{"status": "ok"}
```

---

### `GET /status`

System status with memory stats and LLM usage.

**Response:**
```json
{
  "status": "running",
  "memory": {
    "working_turns": 12,
    "episodic_events": 45,
    "semantic_facts": 8
  },
  "llm_usage": {...},
  "memory_facts": {"user_name": "Srikanth", "favorite_color": "blue"}
}
```

---

### `GET /agents`

List all registered agents.

**Response:**
```json
{
  "companion": {"description": "Casual conversation...", "tier": 1},
  "operator": {"description": "Controls PC...", "tier": 2},
  ...
}
```

---

### `POST /chat`

Send a text transcript and receive a processed response.

**Request:**
```json
{
  "transcript": "What time is it?",
  "session_id": "user-123"
}
```

**Response:**
```json
{
  "response": "It's 3:45 PM! ⏰",
  "agent": "tier0",
  "tier": 0,
  "intent": "get_time",
  "needs_confirmation": false,
  "mood": "happy",
  "metadata": null
}
```

---

### `GET /memory/facts`

List all semantic memory facts.

**Response:**
```json
{"user_name": "Srikanth", "favorite_food": "pizza"}
```

---

### `POST /memory/facts`

Store a semantic fact.

**Request:**
```json
{"key": "favorite_color", "value": "blue"}
```

**Response:**
```json
{"key": "favorite_color", "value": "blue"}
```

---

### `POST /crew`

Run a multi-agent crew on a complex task.

**Request:**
```json
{
  "task": "Research AI news, draft a summary, and post it to LinkedIn",
  "agents": ["researcher", "writer", "browser"],
  "strategy": "sequential"
}
```

**Response:**
```json
{
  "response": "Done! I researched AI news, drafted a summary, and posted it.",
  "strategy": "sequential",
  "agents_used": ["researcher", "writer", "browser"],
  "tasks": 3,
  "time_ms": 15420
}
```

---

### `GET /workflows`

List all saved workflows.

### `POST /workflows`

Create a new workflow from a JSON definition.

### `POST /workflows/{name}/run`

Execute a workflow by name.

---

### `GET /admin/users`

List all RBAC users.

### `GET /admin/audit`

View audit log (last 100 entries).

---

## Webhook Endpoints

### `POST /webhook/tradingview`

TradingView alert webhook. Requires `X-Webhook-Secret` header if `VOCA_SERVER_WEBHOOK_SECRET` is set.

**Request:**
```json
{
  "action": "buy",
  "symbol": "AAPL",
  "quantity": 10
}
```

### `POST /webhook/slack`

Slack Events API webhook handler.

### `POST /webhook/discord`

Discord Interactions webhook handler.

### `POST /webhook/telegram`

Telegram Bot webhook handler.

---

## WebSocket

### `WS /ws`

Real-time bidirectional chat with confirmation flow.

**Connect:** `ws://localhost:8000/ws`

**On connect:** Server sends a greeting message:
```json
{
  "type": "response",
  "response": "Hey Srikanth! 👋 Welcome back, buddy!",
  "agent": "companion",
  "tier": 0,
  "intent": "greeting",
  "needs_confirmation": false,
  "mood": "happy"
}
```

**Send transcript:**
```json
{"type": "transcript", "data": "Open Chrome"}
```

**Receive response:**
```json
{
  "type": "response",
  "response": "Done! ✅ Opening Chrome for you! 🚀",
  "agent": "operator",
  "tier": 0,
  "intent": "open_app",
  "needs_confirmation": false,
  "mood": "happy"
}
```

**Confirmation flow:**
- If `needs_confirmation: true`, send `{"type": "transcript", "data": "yes"}` to confirm
- Send `{"type": "transcript", "data": "no"}` to cancel

**Other message types:**
- `{"type": "confirm"}` — Confirm pending action
- `{"type": "ping"}` → `{"type": "pong"}`
- `{"type": "get_status"}` → Full system status

---

## SSE Streams

### `GET /events/stream`

Live event stream from the EventBus.

```
data: {"event": "chat", "agent": "companion", "timestamp": "..."}

data: {"event": "tool_call", "agent": "operator", "tool": "open_application"}
```

### `GET /agents/stream`

Real-time agent status events for the dashboard.

```
data: {"agent": "operator", "status": "working", "tool": "open_application", "progress": 0.5}

data: {"agent": "operator", "status": "done", "result": "Opened Chrome", "progress": 1}

data: {"type": "heartbeat"}
```
