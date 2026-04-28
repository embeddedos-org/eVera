"""FastAPI application with REST + WebSocket endpoints.

@file vera/app.py
@brief Application factory that creates the FastAPI app with all routes.

Endpoints include REST API (health, status, chat, agents, memory, workflows,
RBAC admin), WebSocket (real-time chat with confirmation flow), SSE streams
(events and agent status), and webhook handlers (TradingView, Slack, Discord,
Telegram).
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from vera.brain.agents import AGENT_REGISTRY
from vera.core import VeraBrain

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


def create_app(brain: VeraBrain | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Factory function that sets up all routes, middleware, authentication,
    and lifespan events.

    @param brain: Optional pre-initialized VeraBrain instance.
                  If None, a new singleton is created.
    @return Configured FastAPI application instance.
    """
    brain_instance = brain or VeraBrain()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await brain_instance.start()
        yield
        await brain_instance.stop()

    app = FastAPI(
        title="Vera API",
        description="Voice-first multi-agent AI assistant",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Merge configured origins with chrome-extension support
    cors_origins = list(settings.server.cors_origins)
    if "chrome-extension://*" not in cors_origins:
        cors_origins.append("chrome-extension://*")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=r"^chrome-extension://.*$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Authentication middleware ---

    @app.middleware("http")
    async def api_key_middleware(request: Request, call_next):
        """Verify API key if configured. Skip for static files and health check."""
        if settings.server.api_key:
            path = request.url.path
            if path not in ("/", "/health") and not path.startswith("/static"):
                auth_header = request.headers.get("Authorization", "")
                if auth_header != f"Bearer {settings.server.api_key}":
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or missing API key"},
                    )
        return await call_next(request)

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

            from vera.brain.agents.brokers import SmartTradeTool, _log_trade

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
        from vera.messaging import handle_slack_event

        return await handle_slack_event(body, headers, brain_instance)

    @app.post("/webhook/discord")
    async def discord_webhook(request: Request):
        """Discord Interactions webhook."""
        body = await request.json()
        from vera.messaging import handle_discord_interaction

        return await handle_discord_interaction(body, brain_instance)

    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request):
        """Telegram Bot webhook."""
        body = await request.json()
        from vera.messaging import handle_telegram_update

        return await handle_telegram_update(body, brain_instance)

    # --- Crew / Multi-agent endpoint ---

    @app.post("/crew")
    async def run_crew_endpoint(request: Request):
        """Run a multi-agent crew on a complex task."""
        body = await request.json()
        from vera.brain.crew import run_crew

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
        from vera.brain.workflow import WorkflowEngine

        engine = WorkflowEngine()
        return engine.list_all()

    @app.post("/workflows")
    async def create_workflow(request: Request):
        """Create a new workflow."""
        body = await request.json()
        from vera.brain.workflow import WorkflowEngine

        engine = WorkflowEngine()
        wf = engine.create(body)
        return {"status": "created", "name": wf.name, "steps": len(wf.steps)}

    @app.post("/workflows/{name}/run")
    async def run_workflow(name: str, request: Request):
        """Execute a workflow by name."""
        body = await request.json() if await request.body() else {}
        from vera.brain.workflow import WorkflowEngine

        engine = WorkflowEngine()
        return await engine.execute(name, brain_instance, variables=body.get("variables"))

    # --- RBAC endpoints ---

    @app.get("/admin/users")
    async def list_users():
        from vera.rbac import RBACManager

        return RBACManager().list_users()

    @app.get("/admin/audit")
    async def audit_log():
        from vera.rbac import RBACManager

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

    # --- Model endpoints (Phase 1) ---

    @app.get("/models")
    async def list_models():
        """Return all models grouped by provider with availability status."""
        return brain_instance.provider_manager.get_available_models()

    @app.post("/models/select")
    async def select_model(request: Request):
        """Select the best model for a given task type."""
        body = await request.json()
        task_type = body.get("task_type", "general")
        model = brain_instance.provider_manager.select_model(task_type)
        if model:
            return {
                "model_name": model.model_name,
                "provider": model.provider,
                "description": model.description,
                "tier": model.tier.name,
            }
        return JSONResponse(status_code=404, content={"detail": f"No model available for task type: {task_type}"})

    @app.get("/models/health")
    async def models_health():
        """Check health of all configured providers."""
        return await brain_instance.provider_manager.provider_health_check()

    # --- Knowledge Base endpoints (Phase 2) ---

    @app.post("/knowledge/upload")
    async def upload_document(request: Request):
        """Upload a document to the knowledge base."""
        from vera.knowledge.rag import RAGPipeline

        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            raise HTTPException(status_code=400, detail="Expected multipart/form-data")

        form = await request.form()
        file = form.get("file")
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")

        # Check file size (50MB limit)
        contents = await file.read()
        if len(contents) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large (max 50MB)")

        rag = RAGPipeline(brain_instance.provider_manager)
        result = await rag.ingest_document(
            filename=file.filename,
            content=contents,
            content_type=file.content_type or "",
        )

        return result

    @app.get("/knowledge/documents")
    async def list_documents():
        """List all documents in the knowledge base."""
        from vera.knowledge.rag import RAGPipeline

        rag = RAGPipeline(brain_instance.provider_manager)
        return rag.list_documents()

    @app.delete("/knowledge/documents/{doc_id}")
    async def delete_document(doc_id: str):
        """Delete a document from the knowledge base."""
        from vera.knowledge.rag import RAGPipeline

        rag = RAGPipeline(brain_instance.provider_manager)
        success = rag.remove_document(doc_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
        return {"status": "deleted", "doc_id": doc_id}

    @app.post("/knowledge/query")
    async def query_knowledge(request: Request):
        """Query the knowledge base with RAG."""
        body = await request.json()
        query = body.get("query", "")
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        from vera.knowledge.rag import RAGPipeline

        rag = RAGPipeline(brain_instance.provider_manager)
        result = await rag.query(query, top_k=body.get("top_k", 5))
        return result

    # --- Extension endpoints (Phase 3) ---

    class ExtensionActionRequest(BaseModel):
        text: str
        context: str | None = None
        model: str | None = None

    @app.post("/extension/summarize")
    async def extension_summarize(request: ExtensionActionRequest):
        """Summarize text for Chrome extension."""
        from vera.providers.models import ModelTier

        result = await brain_instance.provider_manager.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise summarizer. Provide a clear, brief summary of the given text. Use bullet points for key takeaways.",
                },
                {"role": "user", "content": f"Summarize this text:\n\n{request.text}"},
            ],
            tier=ModelTier.SPECIALIST,
            model_override=request.model,
        )
        return {"result": result.content, "model": result.model}

    @app.post("/extension/translate")
    async def extension_translate(request: Request):
        """Translate text for Chrome extension."""
        from vera.providers.models import ModelTier

        body = await request.json()
        text = body.get("text", "")
        target_lang = body.get("target_language", "English")

        result = await brain_instance.provider_manager.complete(
            messages=[
                {
                    "role": "system",
                    "content": f"You are a professional translator. Translate the given text to {target_lang}. Provide only the translation, no explanations.",
                },
                {"role": "user", "content": text},
            ],
            tier=ModelTier.SPECIALIST,
            model_override=body.get("model"),
        )
        return {"result": result.content, "model": result.model, "target_language": target_lang}

    @app.post("/extension/rewrite")
    async def extension_rewrite(request: ExtensionActionRequest):
        """Rewrite text for Chrome extension."""
        from vera.providers.models import ModelTier

        style = "professional and clear"
        result = await brain_instance.provider_manager.complete(
            messages=[
                {
                    "role": "system",
                    "content": f"You are an expert editor. Rewrite the given text to be {style}. Maintain the original meaning but improve clarity and impact.",
                },
                {"role": "user", "content": f"Rewrite this text:\n\n{request.text}"},
            ],
            tier=ModelTier.SPECIALIST,
            model_override=request.model,
        )
        return {"result": result.content, "model": result.model}

    @app.post("/extension/explain")
    async def extension_explain(request: ExtensionActionRequest):
        """Explain text for Chrome extension."""
        from vera.providers.models import ModelTier

        context = f"\n\nPage context: {request.context}" if request.context else ""
        result = await brain_instance.provider_manager.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful explainer. Explain the given text in simple terms. If it contains technical jargon, break it down clearly.",
                },
                {"role": "user", "content": f"Explain this:{context}\n\n{request.text}"},
            ],
            tier=ModelTier.SPECIALIST,
            model_override=request.model,
        )
        return {"result": result.content, "model": result.model}

    @app.post("/extension/grammar")
    async def extension_grammar(request: ExtensionActionRequest):
        """Fix grammar for Chrome extension."""
        from vera.providers.models import ModelTier

        result = await brain_instance.provider_manager.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are a grammar expert. Fix grammar, spelling, and punctuation errors in the given text. Return only the corrected text. If the text is already correct, return it unchanged.",
                },
                {"role": "user", "content": request.text},
            ],
            tier=ModelTier.SPECIALIST,
            model_override=request.model,
        )
        return {"result": result.content, "model": result.model}

    # --- Automation endpoints (Phase 4) ---

    class AutomationPlanRequest(BaseModel):
        task: str

    class AutomationScrapeRequest(BaseModel):
        url: str
        data_schema: dict[str, str]
        max_pages: int = 5
        output_format: str = "json"

    @app.post("/automation/plan")
    async def automation_plan(request: AutomationPlanRequest):
        """Plan a browser automation task."""
        from vera.brain.agents.browser_planner import BrowserPlanner

        planner = BrowserPlanner(brain_instance.provider_manager)
        plan = await planner.plan(request.task)
        return {
            "task": plan.task,
            "steps": [
                {"action": s.action, "args": s.args, "description": s.description, "on_fail": s.on_fail}
                for s in plan.steps
            ],
            "step_count": len(plan.steps),
        }

    @app.post("/automation/execute")
    async def automation_execute(request: AutomationPlanRequest):
        """Plan and execute a browser automation task."""
        from vera.brain.agents.browser_executor import BrowserExecutor

        executor = BrowserExecutor(brain_instance.provider_manager)
        result = await executor.plan_and_execute(request.task)
        return {
            "task_id": result.task_id,
            "task": result.task,
            "status": result.status,
            "steps_completed": result.steps_completed,
            "steps_total": result.steps_total,
            "total_duration_ms": round(result.total_duration_ms),
            "step_results": [
                {
                    "step_index": sr.step_index,
                    "action": sr.action,
                    "status": sr.status,
                    "duration_ms": round(sr.duration_ms),
                    "error": sr.error,
                }
                for sr in result.step_results
            ],
        }

    @app.post("/automation/scrape")
    async def automation_scrape(request: AutomationScrapeRequest):
        """Scrape structured data from a web page."""
        from vera.brain.agents.scraper import WebScraper

        scraper = WebScraper(brain_instance.provider_manager)
        result = await scraper.scrape(
            url=request.url,
            schema=request.data_schema,
            max_pages=request.max_pages,
            output_format=request.output_format,
        )

        output = {
            "url": result.url,
            "status": result.status,
            "pages_scraped": result.pages_scraped,
            "total_items": result.total_items,
            "items": result.items,
            "error": result.error,
        }

        # Convert to requested format
        if request.output_format == "csv":
            output["csv"] = WebScraper.to_csv(result.items)
        elif request.output_format == "markdown":
            output["markdown"] = WebScraper.to_markdown(result.items)

        return output

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
        from vera.events.bus import _agent_status_queue

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

    # --- Streaming chat endpoint ---

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest):
        """Stream LLM response tokens via SSE for faster perceived response."""
        from vera.brain.agents.base import BUDDY_PERSONALITY
        from vera.providers.models import ModelTier

        async def generate():
            try:
                provider = brain_instance.provider_manager
                messages = [
                    {"role": "system", "content": BUDDY_PERSONALITY},
                    {"role": "user", "content": request.transcript},
                ]
                async for chunk in provider.stream(messages, tier=ModelTier.SPECIALIST):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # --- WebSocket endpoint ---

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        # Verify API key on WebSocket handshake
        if settings.server.api_key:
            ws_api_key = websocket.query_params.get("api_key", "")
            if ws_api_key != settings.server.api_key:
                await websocket.close(code=4001, reason="Invalid or missing API key")
                return

        await websocket.accept()
        session_id = f"ws-{id(websocket)}"
        logger.info("WebSocket connected: %s", session_id)

        # Restore previous conversation history for this session
        brain_instance.memory_vault.load_session(session_id)

        # Send a buddy greeting on connect
        user_name = brain_instance.memory_vault.recall_fact("user_name")
        if user_name:
            greeting = f"Hey {user_name}! 👋 Welcome back, buddy! What can I do for you?"
            mood = "happy"
        else:
            greeting = "Hey there! 👋 I'm Vera, your AI buddy! What should I call you?"
            mood = "excited"

        await websocket.send_json(
            {
                "type": "response",
                "response": greeting,
                "agent": "companion",
                "tier": 0,
                "intent": "greeting",
                "needs_confirmation": False,
                "mood": mood,
            }
        )

        # Register proactive notification handler for this WebSocket
        async def push_notification(notification: dict) -> None:
            try:
                await websocket.send_json(
                    {
                        "type": "response",
                        "response": notification.get("message", ""),
                        "agent": "scheduler",
                        "tier": 0,
                        "intent": notification.get("type", "notification"),
                        "needs_confirmation": False,
                        "mood": notification.get("mood", "neutral"),
                    }
                )
                # Also broadcast to messaging platforms
                from vera.messaging import broadcast_notification

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
                    model_override = msg.get("model_override") or msg.get("model")

                    # Handle yes/no as confirmation if there's a pending action
                    lower = transcript.strip().lower()
                    if lower in ("yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "do it", "go ahead", "proceed"):
                        result = await brain_instance.confirm_action(session_id)
                        await websocket.send_json(
                            {
                                "type": "response",
                                "response": result.response,
                                "agent": result.agent,
                                "tier": result.tier,
                                "intent": "confirm",
                                "needs_confirmation": False,
                                "mood": result.mood,
                            }
                        )
                        continue
                    if lower in ("no", "nope", "cancel", "nevermind", "never mind", "don't", "stop"):
                        await websocket.send_json(
                            {
                                "type": "response",
                                "response": "No worries, cancelled! 👍 Let me know if you need anything else.",
                                "agent": "system",
                                "tier": 0,
                                "intent": "cancel",
                                "needs_confirmation": False,
                                "mood": "neutral",
                            }
                        )
                        continue

                    result = await brain_instance.process(transcript, session_id)

                    # Stream tokens if client requested streaming
                    if msg.get("stream"):
                        try:
                            from vera.brain.agents.base import BUDDY_PERSONALITY
                            from vera.providers.models import ModelTier

                            provider = brain_instance.provider_manager
                            messages = [
                                {"role": "system", "content": BUDDY_PERSONALITY},
                                {"role": "user", "content": transcript},
                            ]
                            full_response = ""
                            async for chunk in provider.stream(messages, tier=ModelTier.SPECIALIST):
                                full_response += chunk
                                await websocket.send_json(
                                    {
                                        "type": "stream_token",
                                        "content": chunk,
                                    }
                                )
                            await websocket.send_json(
                                {
                                    "type": "stream_end",
                                    "response": full_response,
                                    "agent": result.agent,
                                    "tier": result.tier,
                                    "intent": result.intent,
                                    "mood": result.mood,
                                }
                            )
                            continue
                        except Exception:
                            pass  # Fall through to non-streaming response

                    await websocket.send_json(
                        {
                            "type": "response",
                            "response": result.response,
                            "agent": result.agent,
                            "tier": result.tier,
                            "intent": result.intent,
                            "needs_confirmation": result.needs_confirmation,
                            "mood": result.mood,
                        }
                    )

                elif msg_type == "confirm":
                    result = await brain_instance.confirm_action(session_id)
                    await websocket.send_json(
                        {
                            "type": "response",
                            "response": result.response,
                            "agent": result.agent,
                        }
                    )

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                elif msg_type == "get_status":
                    await websocket.send_json(
                        {
                            "type": "status",
                            **brain_instance.get_status(),
                        }
                    )

                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"Unknown message type: {msg_type}",
                        }
                    )

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: %s", session_id)
        except Exception as e:
            logger.exception("WebSocket error: %s", e)
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
            except Exception:
                pass
        finally:
            # Clean up: remove notification handler, pending actions, and session memory
            brain_instance.scheduler.remove_notification_handler(push_notification)
            if hasattr(brain_instance, "_pending_actions"):
                brain_instance._pending_actions.pop(session_id, None)
            brain_instance.memory_vault.working.remove_session(session_id)

    # --- Voice WebSocket (STT/TTS streaming) ---

    @app.websocket("/ws/voice")
    async def voice_websocket(websocket: WebSocket):
        """WebSocket endpoint for voice I/O in server mode.

        Client sends binary PCM16 frames (16 kHz, mono, 30 ms).
        Server runs VAD → STT → Brain → TTS and streams audio + JSON back.
        """
        if not settings.voice.server_enabled:
            await websocket.close(code=4003, reason="Voice server not enabled")
            return

        # Auth
        if settings.server.api_key:
            ws_api_key = websocket.query_params.get("api_key", "")
            if ws_api_key != settings.server.api_key:
                await websocket.close(code=4001, reason="Invalid API key")
                return

        await websocket.accept()
        session_id = f"voice-{id(websocket)}"

        try:
            from vera.action.tts import EdgeTTSEngine, get_tts_engine
            from vera.perception.stt import SpeechToText
            from vera.perception.vad import VoiceActivityDetector

            vad = VoiceActivityDetector()
            stt = SpeechToText()
            tts = get_tts_engine()

            await websocket.send_json({"type": "ready", "session_id": session_id})
            logger.info("Voice WS connected: %s", session_id)

            while True:
                data = await websocket.receive()

                if "bytes" in data and data["bytes"]:
                    # Binary PCM16 audio frame
                    chunk = data["bytes"]
                    result = vad.process_chunk(chunk)

                    if result.is_speech_end:
                        transcript = stt.transcribe(result.audio_buffer)
                        if transcript.strip():
                            await websocket.send_json(
                                {
                                    "type": "transcript",
                                    "text": transcript,
                                }
                            )

                            response = await brain_instance.process(transcript, session_id)
                            await websocket.send_json(
                                {
                                    "type": "response",
                                    "text": response.response,
                                    "agent": response.agent,
                                }
                            )

                            # Stream TTS audio back if using edge-tts
                            if isinstance(tts, EdgeTTSEngine):
                                await websocket.send_json({"type": "tts_start"})
                                async for audio_chunk in tts.synthesize(response.response):
                                    await websocket.send_bytes(audio_chunk)
                                await websocket.send_json({"type": "tts_done"})

                elif "text" in data and data["text"]:
                    msg = json.loads(data["text"])
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg.get("type") == "interrupt":
                        tts.interrupt()

        except WebSocketDisconnect:
            logger.info("Voice WS disconnected: %s", session_id)
        except Exception as e:
            logger.exception("Voice WS error: %s", e)

    # --- Mobile device control sessions ---

    _mobile_sessions: dict[str, dict[str, Any]] = {}

    @app.websocket("/ws/mobile")
    async def mobile_websocket(websocket: WebSocket):
        """WebSocket endpoint for mobile device control.

        Mobile client sends device_status on connect.
        Server sends device_command; mobile responds with device_command_result.
        """
        if not settings.mobile.control_enabled:
            await websocket.close(code=4003, reason="Mobile control not enabled")
            return

        if settings.server.api_key:
            ws_api_key = websocket.query_params.get("api_key", "")
            if ws_api_key != settings.server.api_key:
                await websocket.close(code=4001, reason="Invalid API key")
                return

        await websocket.accept()
        session_id = f"mobile-{id(websocket)}"
        _mobile_sessions[session_id] = {
            "websocket": websocket,
            "capabilities": [],
            "platform": "unknown",
            "pending": {},  # cmd_id -> asyncio.Future
        }

        try:
            await websocket.send_json({"type": "connected", "session_id": session_id})
            logger.info("Mobile WS connected: %s", session_id)

            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "device_status":
                    _mobile_sessions[session_id]["platform"] = msg.get("platform", "unknown")
                    _mobile_sessions[session_id]["capabilities"] = msg.get("capabilities", [])
                    logger.info(
                        "Mobile device registered: %s (%s)",
                        session_id,
                        msg.get("platform"),
                    )

                elif msg_type == "device_command_result":
                    cmd_id = msg.get("id")
                    pending = _mobile_sessions[session_id].get("pending", {})
                    fut = pending.pop(cmd_id, None)
                    if fut and not fut.done():
                        fut.set_result(msg)

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

        except WebSocketDisconnect:
            logger.info("Mobile WS disconnected: %s", session_id)
        except Exception as e:
            logger.exception("Mobile WS error: %s", e)
        finally:
            _mobile_sessions.pop(session_id, None)

    # Store mobile sessions on the app for agent access
    app.state.mobile_sessions = _mobile_sessions

    # --- Diagram endpoints ---

    class DiagramExportRequest(BaseModel):
        mermaid: str
        format: str = "svg"
        filename: str = "diagram"

    @app.post("/diagrams/export")
    async def export_diagram(request: DiagramExportRequest):
        """Export a Mermaid diagram to SVG/PNG/PDF."""
        import subprocess
        import tempfile

        fmt = request.format.lower()
        if fmt not in ("svg", "png", "pdf"):
            raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

        output_dir = Path(settings.data_dir) / "diagrams"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{request.filename}.{fmt}"

        # Write mermaid text to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False, encoding="utf-8") as f:
            f.write(request.mermaid)
            input_file = f.name

        try:
            result = subprocess.run(
                ["mmdc", "-i", input_file, "-o", str(output_file), "-b", "transparent"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"mmdc failed: {result.stderr}. Install with: npm install -g @mermaid-js/mermaid-cli",
                )

            return FileResponse(
                str(output_file),
                media_type=f"image/{fmt}" if fmt != "pdf" else "application/pdf",
                filename=f"{request.filename}.{fmt}",
            )
        except FileNotFoundError:
            # mmdc not installed — return raw mermaid as .mmd
            mmd_path = output_dir / f"{request.filename}.mmd"
            mmd_path.write_text(request.mermaid, encoding="utf-8")
            raise HTTPException(
                status_code=501,
                detail="mmdc not installed. Install with: npm install -g @mermaid-js/mermaid-cli",
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Diagram export timed out")
        finally:
            import os

            try:
                os.unlink(input_file)
            except OSError:
                pass

    @app.get("/diagrams", include_in_schema=False)
    async def serve_diagrams_page():
        """Serve the standalone diagram editor/viewer page."""
        return FileResponse(STATIC_DIR / "diagrams.html")

    # --- Code Viewer endpoints ---

    @app.get("/code-viewer", include_in_schema=False)
    async def serve_code_viewer_page():
        """Serve the standalone code viewer page."""
        return FileResponse(STATIC_DIR / "code-viewer.html")

    @app.get("/api/code/files")
    async def code_files(request: Request):
        """Return file tree for a given path."""
        from config import settings
        from vera.brain.agents.codebase_indexer import _build_tree
        from vera.brain.agents.coder import _is_path_safe

        raw_path = request.query_params.get("path", ".")
        project = Path(raw_path).resolve()
        if not project.is_dir():
            project = Path(settings.codebase_indexer.default_project_path).resolve()
        if not project.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {project}")

        safe, reason = _is_path_safe(project)
        if not safe:
            raise HTTPException(status_code=403, detail=f"Forbidden: {reason}")

        tree = _build_tree(project, max_depth=4)
        return JSONResponse({"tree": tree, "root": str(project)})

    @app.get("/api/code/file")
    async def code_file(request: Request):
        """Return file content, language, definitions, and complexity."""
        from vera.brain.agents.code_analysis import compute_complexity
        from vera.brain.agents.codebase_indexer import _extract_definitions
        from vera.brain.agents.coder import _is_path_safe

        file_path = request.query_params.get("path", "")
        if not file_path:
            raise HTTPException(status_code=400, detail="path query parameter required")

        fp = Path(file_path).resolve()

        safe, reason = _is_path_safe(fp)
        if not safe:
            raise HTTPException(status_code=403, detail=f"Forbidden: {reason}")

        if not fp.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        try:
            content = fp.read_text(errors="ignore")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".md": "markdown",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".sh": "bash",
        }
        language = ext_map.get(fp.suffix.lower(), "text")
        definitions = _extract_definitions(fp)
        complexity = compute_complexity(content, str(fp))

        return JSONResponse(
            {
                "path": str(fp),
                "name": fp.name,
                "content": content,
                "language": language,
                "definitions": definitions,
                "complexity": complexity,
            }
        )

    class CodeAnalyzeRequest(BaseModel):
        path: str
        content: str | None = None
        action: str  # summarize, explain, find_issues

    @app.post("/api/code/analyze")
    async def code_analyze(request: CodeAnalyzeRequest):
        """Run AI analysis on a code file."""
        from vera.brain.agents.code_analysis import explain_code, find_issues, summarize_code

        fp = Path(request.path).resolve()
        content = request.content
        if not content:
            if fp.is_file():
                try:
                    content = fp.read_text(errors="ignore")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            else:
                raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

        provider = brain_instance.provider_manager
        action = request.action.lower()

        try:
            if action == "summarize":
                result = await summarize_code(str(fp), content, provider)
            elif action == "explain":
                result = await explain_code(str(fp), content, provider)
            elif action == "find_issues":
                result = await find_issues(str(fp), content, provider)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
        except Exception as e:
            logger.exception("Code analysis error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

        return JSONResponse({"action": action, "path": str(fp), **result})

    @app.get("/api/code/dependency-graph")
    async def code_dependency_graph(request: Request):
        """Return dependency graph nodes and edges for a path."""
        from config import settings
        from vera.brain.tools.dependency_parser import parse_dependencies

        raw_path = request.query_params.get("path", ".")
        project = Path(raw_path).resolve()
        if not project.is_dir():
            project = Path(settings.codebase_indexer.default_project_path).resolve()
        if not project.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {project}")

        try:
            graph = parse_dependencies(str(project))
        except Exception as e:
            logger.exception("Dependency graph error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

        return JSONResponse(graph)

    @app.get("/api/memory/graph")
    async def memory_graph():
        """Return memory knowledge graph for visualization."""
        vault = brain_instance.memory_vault
        stats = vault.get_stats()

        nodes = [
            {
                "id": "working",
                "label": "Working Memory",
                "type": "hub",
                "color": "#60a5fa",
                "count": stats.get("working_turns", 0),
            },
            {
                "id": "episodic",
                "label": "Episodic Memory",
                "type": "hub",
                "color": "#a78bfa",
                "count": stats.get("episodic_events", 0),
            },
            {
                "id": "semantic",
                "label": "Semantic Memory",
                "type": "hub",
                "color": "#4ade80",
                "count": stats.get("semantic_facts", 0),
            },
            {"id": "secure", "label": "Secure Vault", "type": "hub", "color": "#fb923c", "count": 0},
        ]
        edges = []

        # Add child nodes for semantic facts
        all_facts = vault.semantic.get_all()
        for i, (key, value) in enumerate(list(all_facts.items())[:30]):
            fact_id = f"fact_{i}"
            nodes.append(
                {
                    "id": fact_id,
                    "label": key,
                    "type": "fact",
                    "color": "#4ade80",
                    "value": str(value)[:80],
                }
            )
            edges.append({"source": "semantic", "target": fact_id, "type": "contains"})

        # Cross-layer relations
        edges.append({"source": "working", "target": "episodic", "type": "relates_to"})
        edges.append({"source": "episodic", "target": "semantic", "type": "relates_to"})

        return JSONResponse({"nodes": nodes, "edges": edges})

    return app
