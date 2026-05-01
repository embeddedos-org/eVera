"""API Agent -- API testing, documentation, mocking, generation."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class APIRequestTool(Tool):
    def __init__(self):
        super().__init__(
            name="api_request",
            description="Make HTTP API requests (GET/POST/PUT/DELETE)",
            parameters={
                "method": {"type": "str", "description": "GET|POST|PUT|DELETE|PATCH"},
                "url": {"type": "str", "description": "API URL"},
                "headers": {"type": "str", "description": "JSON headers"},
                "body": {"type": "str", "description": "JSON request body"},
                "auth_token": {"type": "str", "description": "Bearer token"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import httpx

            headers = json.loads(kw.get("headers", "{}")) if isinstance(kw.get("headers"), str) else {}
            if kw.get("auth_token"):
                headers["Authorization"] = f"Bearer {kw['auth_token']}"
            body = json.loads(kw.get("body", "{}")) if kw.get("body") else None
            t0 = time.time()
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.request(kw.get("method", "GET"), kw["url"], headers=headers, json=body)
            elapsed = round((time.time() - t0) * 1000, 2)
            try:
                resp_body = r.json()
            except:
                resp_body = r.text[:3000]
            return {
                "status": "success",
                "code": r.status_code,
                "body": resp_body,
                "headers": dict(r.headers),
                "time_ms": elapsed,
            }
        except ImportError:
            return {"status": "error", "message": "pip install httpx"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class APIDocsTool(Tool):
    def __init__(self):
        super().__init__(
            name="api_docs",
            description="Generate API documentation from OpenAPI/Swagger spec",
            parameters={"spec_url": {"type": "str", "description": "OpenAPI spec URL or file path"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import httpx

            spec_url = kw.get("spec_url", "")
            if spec_url.startswith("http"):
                async with httpx.AsyncClient(timeout=10) as c:
                    r = await c.get(spec_url)
                    spec = r.json()
            else:
                spec = json.loads(Path(spec_url).read_text())
            endpoints = []
            for path, methods in spec.get("paths", {}).items():
                for method, details in methods.items():
                    if method in ("get", "post", "put", "delete", "patch"):
                        endpoints.append(
                            {
                                "path": path,
                                "method": method.upper(),
                                "summary": details.get("summary", ""),
                                "tags": details.get("tags", []),
                            }
                        )
            return {
                "status": "success",
                "title": spec.get("info", {}).get("title", ""),
                "version": spec.get("info", {}).get("version", ""),
                "endpoints": endpoints,
                "count": len(endpoints),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class APILoadTestTool(Tool):
    def __init__(self):
        super().__init__(
            name="api_load_test",
            description="Simple load test an API endpoint",
            parameters={
                "url": {"type": "str", "description": "API URL"},
                "method": {"type": "str", "description": "HTTP method"},
                "requests": {"type": "int", "description": "Number of requests"},
                "concurrency": {"type": "int", "description": "Concurrent requests"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import asyncio

            import httpx

            url, method = kw["url"], kw.get("method", "GET")
            n, conc = min(kw.get("requests", 10), 100), min(kw.get("concurrency", 5), 20)
            times = []
            errors = 0

            async def req():
                nonlocal errors
                try:
                    async with httpx.AsyncClient(timeout=30) as c:
                        t0 = time.time()
                        await c.request(method, url)
                        times.append(time.time() - t0)
                except:
                    errors += 1

            for batch in range(0, n, conc):
                await asyncio.gather(*[req() for _ in range(min(conc, n - batch))])
            if times:
                return {
                    "status": "success",
                    "total_requests": n,
                    "successful": len(times),
                    "errors": errors,
                    "avg_ms": round(sum(times) / len(times) * 1000, 2),
                    "min_ms": round(min(times) * 1000, 2),
                    "max_ms": round(max(times) * 1000, 2),
                    "rps": round(len(times) / sum(times), 2) if sum(times) > 0 else 0,
                }
            return {"status": "error", "message": "All requests failed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class APICollectionTool(Tool):
    def __init__(self):
        super().__init__(
            name="api_collection",
            description="Save/load API request collections (like Postman)",
            parameters={
                "action": {"type": "str", "description": "save|load|list|delete"},
                "name": {"type": "str", "description": "Collection name"},
                "request": {"type": "str", "description": "JSON request to save"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        cd = Path("data/api_collections")
        cd.mkdir(parents=True, exist_ok=True)
        a = kw.get("action", "list")
        if a == "save":
            fp = cd / f"{kw.get('name', 'default')}.json"
            col = json.loads(fp.read_text()) if fp.exists() else []
            col.append(
                json.loads(kw.get("request", "{}")) if isinstance(kw.get("request"), str) else kw.get("request", {})
            )
            fp.write_text(json.dumps(col, indent=2))
            return {"status": "success", "saved": kw.get("name", ""), "total": len(col)}
        elif a == "load":
            fp = cd / f"{kw.get('name', 'default')}.json"
            if fp.exists():
                return {"status": "success", "requests": json.loads(fp.read_text())}
            return {"status": "error", "message": "Collection not found"}
        elif a == "delete":
            fp = cd / f"{kw.get('name', '')}.json"
            if fp.exists():
                fp.unlink()
            return {"status": "success", "deleted": True}
        return {"status": "success", "collections": [f.stem for f in cd.glob("*.json")]}


class APIAgent(BaseAgent):
    name = "api"
    description = "API requests, documentation, load testing, request collections"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's API Agent. Make HTTP requests, parse OpenAPI docs, load test endpoints, manage request collections."
    offline_responses = {
        "api": "\U0001f310 API ready!",
        "request": "\U0001f4e8 Sending!",
        "test": "\U0001f9ea Testing!",
        "endpoint": "\U0001f517 Endpoint!",
    }

    def _setup_tools(self):
        self._tools = [APIRequestTool(), APIDocsTool(), APILoadTestTool(), APICollectionTool()]
