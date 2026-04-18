"""FastAPI application with REST + WebSocket endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from voca.brain.agents import AGENT_REGISTRY
from voca.core import VocaBrain

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


# --- Request/Response models ---

class ChatRequest(BaseModel):
    transcript: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    agent: str
    tier: int
    intent: str = ""
    needs_confirmation: bool = False
    mood: str = "neutral"
    metadata: dict[str, Any] | None = None


class FactRequest(BaseModel):
    key: str
    value: str


class FactResponse(BaseModel):
    key: str
    value: str | None


# --- App factory ---

def create_app(brain: VocaBrain | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    brain_instance = brain or VocaBrain()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await brain_instance.start()
        yield
        await brain_instance.stop()

    app = FastAPI(
        title="Voca API",
        description="Voice-first multi-agent AI assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Authentication ---

    async def verify_api_key(request: Request):
        """Verify API key if configured. Skip for static files and health check."""
        if not settings.server.api_key:
            return  # No auth configured — allow all
        path = request.url.path
        if path in ("/", "/health") or path.startswith("/static"):
            return  # Public endpoints
        auth_header = request.headers.get("Authorization", "")
        api_key = request.query_params.get("api_key", "")
        if auth_header == f"Bearer {settings.server.api_key}" or api_key == settings.server.api_key:
            return
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    def verify_webhook_secret(request: Request):
        """Verify webhook secret for trading webhooks."""
        if not settings.server.webhook_secret:
            return  # No secret configured
        secret = request.headers.get("X-Webhook-Secret", "")
        if secret != settings.server.webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    # Store brain on app state
    app.state.brain = brain_instance

    # --- Serve Web UI ---

    @app.get("/", include_in_schema=False)
    async def serve_ui():
        return FileResponse(STATIC_DIR / "index.html")

    # Mount static files (after the root route so / isn't shadowed)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # --- REST endpoints ---

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/webhook/tradingview")
    async def tradingview_webhook(request: Request):
        """Receive TradingView webhook alerts and execute trades."""
        verify_webhook_secret(request)
        try:
            body = await request.json()
            action = body.get("action", "")
            symbol = body.get("symbol", "")
            quantity = body.get("quantity", 0)

            if not action or not symbol or not quantity:
                return {"status": "error", "message": "Webhook needs action, symbol, quantity"}

            from voca.brain.agents.brokers import SmartTradeTool, _log_trade
            trade_tool = SmartTradeTool()
            result = await trade_tool.execute(action=action, symbol=symbol, quantity=quantity)
            _log_trade("tradingview", {"action": action, "symbol": symbol, "quantity": quantity, "result": result})

            logger.info("TradingView webhook executed: %s %s %s → %s", action, quantity, symbol, result.get("status"))
            return result
        except Exception as e:
            logger.exception("TradingView webhook error: %s", e)
            return {"status": "error", "message": str(e)}

    # --- Messaging webhooks (Slack, Discord, Telegram) ---

    @app.post("/webhook/slack")
    async def slack_webhook(request: Request):
        """Slack Events API webhook."""
        body = await request.json()
        headers = dict(request.headers)
        from voca.messaging import handle_slack_event
        return await handle_slack_event(body, headers, brain_instance)

    @app.post("/webhook/discord")
    async def discord_webhook(request: Request):
        """Discord Interactions webhook."""
        body = await request.json()
        from voca.messaging import handle_discord_interaction
        return await handle_discord_interaction(body, brain_instance)

    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request):
        """Telegram Bot webhook."""
        body = await request.json()
        from voca.messaging import handle_telegram_update
        return await handle_telegram_update(body, brain_instance)

    # --- Crew / Multi-agent endpoint ---

    @app.post("/crew")
    async def run_crew_endpoint(request: Request):
        """Run a multi-agent crew on a complex task."""
        body = await request.json()
        from voca.brain.crew import run_crew
        result = await run_crew(
            brain_instance,
            task=body.get("task", ""),
            agents=body.get("agents"),
            strategy=body.get("strategy", "sequential"),
        )
        return {
            "response": result.final_response,
            "strategy": result.strategy,
            "agents_used": result.agents_used,
            "tasks": len(result.tasks),
            "time_ms": round(result.total_time_ms),
        }

    # --- Workflow engine endpoints ---

    @app.get("/workflows")
    async def list_workflows():
        """List all saved workflows."""
        from voca.brain.workflow import WorkflowEngine
        engine = WorkflowEngine()
        return engine.list_all()

    @app.post("/workflows")
    async def create_workflow(request: Request):
        """Create a new workflow."""
        body = await request.json()
        from voca.brain.workflow import WorkflowEngine
        engine = WorkflowEngine()
        wf = engine.create(body)
        return {"status": "created", "name": wf.name, "steps": len(wf.steps)}

    @app.post("/workflows/{name}/run")
    async def run_workflow(name: str, request: Request):
        """Execute a workflow by name."""
        body = await request.json() if await request.body() else {}
        from voca.brain.workflow import WorkflowEngine
        engine = WorkflowEngine()
        return await engine.execute(name, brain_instance, variables=body.get("variables"))

    # --- RBAC endpoints ---

    @app.get("/admin/users")
    async def list_users():
        from voca.rbac import RBACManager
        return RBACManager().list_users()

    @app.get("/admin/audit")
    async def audit_log():
        from voca.rbac import RBACManager
        return RBACManager().get_audit_log(limit=100)

    @app.get("/status")
    async def status():
        return brain_instance.get_status()

    @app.get("/agents")
    async def agents():
        return {
            name: {
                "description": agent.description,
                "tier": agent.tier,
            }
            for name, agent in AGENT_REGISTRY.items()
        }

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        result = await brain_instance.process(
            transcript=request.transcript,
            session_id=request.session_id,
        )
        return ChatResponse(
            response=result.response,
            agent=result.agent,
            tier=result.tier,
            intent=result.intent,
            needs_confirmation=result.needs_confirmation,
            mood=result.mood,
            metadata=result.metadata,
        )

    @app.get("/memory/facts")
    async def get_facts():
        return brain_instance.memory_vault.semantic.get_all()

    @app.post("/memory/facts", response_model=FactResponse)
    async def set_fact(request: FactRequest):
        brain_instance.memory_vault.remember_fact(request.key, request.value)
        return FactResponse(key=request.key, value=request.value)

    @app.get("/events/stream")
    async def event_stream():
        """SSE endpoint streaming live events from the EventBus."""
        async def generate():
            last_count = 0
            while True:
                events = brain_instance.get_event_log(limit=100)
                if len(events) > last_count:
                    new_events = events[last_count:]
                    for event in new_events:
                        data = json.dumps(event, default=str)
                        yield f"data: {data}\n\n"
                    last_count = len(events)
                await asyncio.sleep(0.5)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/agents/stream")
    async def agent_status_stream():
        """SSE endpoint streaming real-time agent status events."""
        from voca.events.bus import _agent_status_queue

        async def generate():
            while True:
                try:
                    event = await asyncio.wait_for(_agent_status_queue.get(), timeout=5.0)
                    data = json.dumps(event, default=str)
                    yield f"data: {data}\n\n"
                except TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # --- WebSocket endpoint ---

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        session_id = f"ws-{id(websocket)}"
        logger.info("WebSocket connected: %s", session_id)

        # Send a buddy greeting on connect
        user_name = brain_instance.memory_vault.recall_fact("user_name")
        if user_name:
            greeting = f"Hey {user_name}! 👋 Welcome back, buddy! What can I do for you?"
            mood = "happy"
        else:
            greeting = "Hey there! 👋 I'm Voca, your AI buddy! What should I call you?"
            mood = "excited"

        await websocket.send_json({
            "type": "response",
            "response": greeting,
            "agent": "companion",
            "tier": 0,
            "intent": "greeting",
            "needs_confirmation": False,
            "mood": mood,
        })

        # Register proactive notification handler for this WebSocket
        async def push_notification(notification: dict) -> None:
            try:
                await websocket.send_json({
                    "type": "response",
                    "response": notification.get("message", ""),
                    "agent": "scheduler",
                    "tier": 0,
                    "intent": notification.get("type", "notification"),
                    "needs_confirmation": False,
                    "mood": notification.get("mood", "neutral"),
                })
                # Also broadcast to messaging platforms
                from voca.messaging import broadcast_notification
                await broadcast_notification(notification.get("message", ""))
            except Exception:
                pass

        brain_instance.scheduler.add_notification_handler(push_notification)

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    msg = {"type": "transcript", "data": raw}

                msg_type = msg.get("type", "transcript")

                if msg_type == "transcript":
                    transcript = msg.get("data", msg.get("transcript", ""))

                    # Handle yes/no as confirmation if there's a pending action
                    lower = transcript.strip().lower()
                    if lower in ("yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "do it", "go ahead", "proceed"):
                        result = await brain_instance.confirm_action(session_id)
                        await websocket.send_json({
                            "type": "response",
                            "response": result.response,
                            "agent": result.agent,
                            "tier": result.tier,
                            "intent": "confirm",
                            "needs_confirmation": False,
                            "mood": result.mood,
                        })
                        continue
                    if lower in ("no", "nope", "cancel", "nevermind", "never mind", "don't", "stop"):
                        await websocket.send_json({
                            "type": "response",
                            "response": "No worries, cancelled! 👍 Let me know if you need anything else.",
                            "agent": "system",
                            "tier": 0,
                            "intent": "cancel",
                            "needs_confirmation": False,
                            "mood": "neutral",
                        })
                        continue

                    result = await brain_instance.process(transcript, session_id)
                    await websocket.send_json({
                        "type": "response",
                        "response": result.response,
                        "agent": result.agent,
                        "tier": result.tier,
                        "intent": result.intent,
                        "needs_confirmation": result.needs_confirmation,
                        "mood": result.mood,
                    })

                elif msg_type == "confirm":
                    result = await brain_instance.confirm_action(session_id)
                    await websocket.send_json({
                        "type": "response",
                        "response": result.response,
                        "agent": result.agent,
                    })

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "get_status":
                    await websocket.send_json({
                        "type": "status",
                        **brain_instance.get_status(),
                    })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: %s", session_id)
        except Exception as e:
            logger.exception("WebSocket error: %s", e)
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            # Clean up: remove notification handler and pending actions
            brain_instance.scheduler.remove_notification_handler(push_notification)
            if hasattr(brain_instance, "_pending_actions"):
                brain_instance._pending_actions.pop(session_id, None)

    return app
