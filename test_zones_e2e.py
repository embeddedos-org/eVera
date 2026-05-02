"""eVera Network Zone E2E Tests — validates three-layer access control.

Tests the LOCAL / LAN / WWW zone system:
  - LOCAL (127.0.0.1): No auth, full access
  - LAN (192.168.x):   API key required, /admin/ blocked
  - WWW (public IP):   API key + rate limit, /admin/ + /api/code/ blocked

Uses FastAPI TestClient with mocked VeraBrain (no real LLM needed).
Simulates zones via X-Forwarded-For header to test IP classification.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ── Mock heavy dependencies before any imports ──
mock_modules = {
    "numpy": MagicMock(),
    "faiss": MagicMock(),
    "litellm": MagicMock(),
    "langgraph": MagicMock(),
    "langgraph.graph": MagicMock(),
    "sentence_transformers": MagicMock(),
    "faster_whisper": MagicMock(),
    "pyttsx3": MagicMock(),
    "webrtcvad": MagicMock(),
    "pyaudio": MagicMock(),
    "playwright": MagicMock(),
    "playwright.async_api": MagicMock(),
    "yfinance": MagicMock(),
    "duckduckgo_search": MagicMock(),
    "pyautogui": MagicMock(),
    "pygetwindow": MagicMock(),
    "pyperclip": MagicMock(),
    "psutil": MagicMock(),
    "cryptography": MagicMock(),
    "cryptography.fernet": MagicMock(),
}

for mod_name, mock in mock_modules.items():
    sys.modules.setdefault(mod_name, mock)

langgraph_mock = sys.modules["langgraph.graph"]
langgraph_mock.END = "END"
langgraph_mock.START = "START"
langgraph_mock.StateGraph = MagicMock()

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Set API key so zone auth is testable
os.environ["VERA_SERVER_API_KEY"] = "test-zone-key-2026"
os.environ["VERA_SERVER_ZONE_LOCAL_ENABLED"] = "true"
os.environ["VERA_SERVER_ZONE_LAN_ENABLED"] = "true"
os.environ["VERA_SERVER_ZONE_WWW_ENABLED"] = "true"
os.environ["VERA_SERVER_ZONE_LAN_AUTH_REQUIRED"] = "true"
os.environ["VERA_SERVER_ZONE_WWW_AUTH_REQUIRED"] = "true"
os.environ["VERA_SERVER_ZONE_WWW_RATE_LIMIT_RPM"] = "10"
os.environ["VERA_SERVER_ZONE_WWW_RATE_LIMIT_BURST"] = "3"

from fastapi.testclient import TestClient  # noqa: E402


# ── Mock Brain ──
class MockBrain:
    def __init__(self):
        self.memory_vault = MagicMock()
        self.memory_vault.recall_fact = MagicMock(return_value="TestUser")
        self.memory_vault.semantic.get_all = MagicMock(return_value={"user_name": "TestUser"})
        self.memory_vault.working.remove_session = MagicMock()
        self.memory_vault.load_session = MagicMock()
        self.provider_manager = MagicMock()
        self.scheduler = MagicMock()
        self.scheduler.add_notification_handler = MagicMock()
        self.scheduler.remove_notification_handler = MagicMock()
        self.event_bus = MagicMock()
        self._pending_actions = {}

    async def start(self):
        pass

    async def stop(self):
        pass

    async def process(self, transcript, session_id=None):
        from types import SimpleNamespace
        return SimpleNamespace(
            response=f"Mock response to: {transcript}",
            agent="companion", tier=1, intent="chat",
            needs_confirmation=False, mood="happy", metadata=None,
        )

    async def confirm_action(self, session_id):
        from types import SimpleNamespace
        return SimpleNamespace(response="No pending action", agent="system", tier=0, mood="neutral")

    def get_status(self):
        return {"status": "running", "memory": {}, "llm_usage": {}, "memory_facts": {}}

    def get_event_log(self, limit=50):
        return []

    def store_pending_action(self, session_id, action):
        self._pending_actions[session_id] = action


mock_registry = {
    "companion": MagicMock(description="Chat agent", tier=1),
    "operator": MagicMock(description="PC automation", tier=2),
}

with patch("vera.brain.agents.AGENT_REGISTRY", mock_registry):
    with patch("vera.core.VeraBrain", MockBrain):
        from vera.app import create_app
        app = create_app(brain=MockBrain())

client = TestClient(app)

API_KEY = "test-zone-key-2026"
AUTH_HEADER = {"Authorization": f"Bearer {API_KEY}"}

# Simulated IPs for each zone
LOCAL_IP = "127.0.0.1"
LAN_IP = "192.168.1.50"
WWW_IP = "8.8.8.8"

# ── Test Tracking ──
PASS = 0
FAIL = 0
ERRORS = []


def test(name, response, expected_status=200, check_body=None, check_headers=None):
    global PASS, FAIL
    ok = response.status_code == expected_status
    body_ok = True
    headers_ok = True

    if check_body and ok:
        try:
            data = response.json()
            body_ok = check_body(data)
        except Exception:
            body_ok = False

    if check_headers and ok:
        try:
            headers_ok = check_headers(response.headers)
        except Exception:
            headers_ok = False

    if ok and body_ok and headers_ok:
        PASS += 1
        print(f"  PASS  [{response.status_code}] {name}")
    else:
        FAIL += 1
        detail = f"expected {expected_status}, got {response.status_code}"
        if not body_ok:
            detail += " (body check failed)"
        if not headers_ok:
            detail += " (header check failed)"
        msg = f"  FAIL  [{response.status_code}] {name} — {detail}"
        print(msg)
        ERRORS.append(msg)


# ═══════════════════════════════════════════════════════════
print("=" * 60)
print("  eVera — Network Zone E2E Tests")
print("=" * 60)

# -- 1. Zone Detection Endpoint --
print("\n--- /network/zones endpoint ---")

# These initial requests come from 'testclient' (no real IP) -> classified as WWW
# Use LOCAL IP to avoid rate limiting
r = client.get("/network/zones", headers={"X-Forwarded-For": LOCAL_IP})
test("GET /network/zones (no auth needed -- public path)", r, 200,
     check_body=lambda d: "zones" in d and "local" in d["zones"] and "lan" in d["zones"] and "www" in d["zones"])

r = client.get("/network/zones", headers={"X-Forwarded-For": LOCAL_IP})
test("/network/zones returns your_zone", r, 200,
     check_body=lambda d: d.get("your_zone") in ("local", "lan", "www"))

r = client.get("/network/zones", headers={"X-Forwarded-For": LOCAL_IP})
test("/network/zones returns rate_limit config", r, 200,
     check_body=lambda d: d.get("rate_limit", {}).get("requests_per_minute") == 10)

# ── 2. LOCAL Zone -- No Auth Required --
print("\n--- LOCAL Zone (127.0.0.1) -- No Auth ---")

# TestClient doesn't use a real IP, so simulate LOCAL via X-Forwarded-For
local_headers = {"X-Forwarded-For": LOCAL_IP}

r = client.get("/health", headers=local_headers)
test("LOCAL: GET /health (no auth)", r, 200,
     check_headers=lambda h: h.get("x-vera-zone") == "local")

r = client.get("/status", headers=local_headers)
test("LOCAL: GET /status (no auth, full access)", r, 200)

r = client.post("/chat", json={"transcript": "hello"}, headers=local_headers)
test("LOCAL: POST /chat (no auth)", r, 200)

r = client.get("/agents", headers=local_headers)
test("LOCAL: GET /agents (no auth)", r, 200)

r = client.get("/admin/users", headers=local_headers)
test("LOCAL: GET /admin/users (full access)", r, 200)

# ── 3. LAN Zone -- Auth Required --
print("\n--- LAN Zone (192.168.x) -- Auth Required ---")

# Simulate LAN via X-Forwarded-For
lan_headers = {"X-Forwarded-For": LAN_IP}
lan_auth_headers = {**lan_headers, **AUTH_HEADER}

r = client.get("/health", headers=lan_headers)
test("LAN: GET /health (public, no auth needed)", r, 200,
     check_headers=lambda h: h.get("x-vera-zone") == "lan")

r = client.get("/network/zones", headers=lan_headers)
test("LAN: GET /network/zones (public path)", r, 200,
     check_body=lambda d: d.get("your_zone") == "lan")

r = client.get("/status", headers=lan_headers)
test("LAN: GET /status (no auth -> 401)", r, 401)

r = client.get("/status", headers=lan_auth_headers)
test("LAN: GET /status (with auth -> 200)", r, 200)

r = client.post("/chat", json={"transcript": "hello"}, headers=lan_auth_headers)
test("LAN: POST /chat (with auth)", r, 200)

r = client.get("/admin/users", headers=lan_auth_headers)
test("LAN: GET /admin/users (blocked path -> 403)", r, 403,
     check_body=lambda d: "zone" in d.get("detail", "").lower() or d.get("zone") == "lan")

# -- 4. WWW Zone -- Auth + Rate Limiting --
print("\n--- WWW Zone (8.8.8.8) -- Auth + Rate Limit ---")

# Reset rate limiter to ensure clean state for WWW tests
from vera.network_zones import rate_limiter as _rl  # noqa: E402
_rl._windows.clear()

# Use a unique IP for each test to avoid cross-test rate limit interference
www_headers = {"X-Forwarded-For": WWW_IP}
www_auth_headers = {**www_headers, **AUTH_HEADER}

r = client.get("/health", headers=www_headers)
test("WWW: GET /health (public, no auth)", r, 200,
     check_headers=lambda h: h.get("x-vera-zone") == "www")

r = client.get("/network/zones", headers={"X-Forwarded-For": "8.8.4.4"})
test("WWW: GET /network/zones (public path)", r, 200,
     check_body=lambda d: d.get("your_zone") == "www")

# Use a fresh IP for auth tests to avoid burst limits from prior requests
www_auth_ip = "104.16.1.1"
r = client.get("/status", headers={"X-Forwarded-For": www_auth_ip})
test("WWW: GET /status (no auth -> 401)", r, 401)

r = client.get("/status", headers={"X-Forwarded-For": www_auth_ip, **AUTH_HEADER})
test("WWW: GET /status (with auth -> 200)", r, 200)

r = client.get("/admin/users", headers={"X-Forwarded-For": "198.51.100.1", **AUTH_HEADER})
test("WWW: GET /admin/users (blocked -> 403)", r, 403)

r = client.get("/admin/audit", headers={"X-Forwarded-For": "198.51.100.2", **AUTH_HEADER})
test("WWW: GET /admin/audit (blocked -> 403)", r, 403)

# -- 5. Zone Headers --
print("\n--- Zone Response Headers ---")

r = client.get("/health", headers={"X-Forwarded-For": LOCAL_IP})
test("X-Vera-Zone header present", r, 200,
     check_headers=lambda h: "x-vera-zone" in h)

r = client.get("/health", headers={"X-Forwarded-For": LOCAL_IP})
test("X-Vera-Zone-Auth header present", r, 200,
     check_headers=lambda h: "x-vera-zone-auth" in h)

r = client.get("/health", headers={"X-Forwarded-For": LOCAL_IP})
test("LOCAL zone auth = none", r, 200,
     check_headers=lambda h: h.get("x-vera-zone-auth") == "none")

r = client.get("/health", headers={"X-Forwarded-For": LAN_IP})
test("LAN zone auth = required", r, 200,
     check_headers=lambda h: h.get("x-vera-zone-auth") == "required")

# ── 6. WebSocket Zone Tests --
print("\n--- WebSocket Zone Access ---")

try:
    with client.websocket_connect("/ws", headers={"X-Forwarded-For": LOCAL_IP}) as ws:
        greeting = ws.receive_json()
        ws_ok = greeting.get("type") == "response"
        PASS += 1 if ws_ok else 0
        FAIL += 0 if ws_ok else 1
        print(f"  {'PASS' if ws_ok else 'FAIL'}  WS /ws LOCAL -- no auth needed, connected")
        if not ws_ok:
            ERRORS.append(f"  FAIL  WS LOCAL: {greeting}")
except Exception as e:
    FAIL += 1
    msg = f"  FAIL  WS /ws LOCAL — {e}"
    print(msg)
    ERRORS.append(msg)

# -- 7. IP Classification Unit Tests --
print("\n--- IP Classification ---")

from vera.network_zones import classify_ip, NetworkZone as NZ  # noqa: E402

ip_tests = [
    ("127.0.0.1", NZ.LOCAL),
    ("127.0.0.50", NZ.LOCAL),
    ("::1", NZ.LOCAL),
    ("192.168.1.1", NZ.LAN),
    ("192.168.0.100", NZ.LAN),
    ("10.0.0.1", NZ.LAN),
    ("10.255.255.255", NZ.LAN),
    ("172.16.0.1", NZ.LAN),
    ("172.31.255.255", NZ.LAN),
    ("169.254.1.1", NZ.LAN),
    ("8.8.8.8", NZ.WWW),
    ("1.1.1.1", NZ.WWW),
    ("203.0.113.50", NZ.WWW),
    ("172.32.0.1", NZ.WWW),
]

for ip, expected_zone in ip_tests:
    result = classify_ip(ip)
    if result == expected_zone:
        PASS += 1
        print(f"  PASS  classify_ip({ip}) = {result.value}")
    else:
        FAIL += 1
        msg = f"  FAIL  classify_ip({ip}) = {result.value}, expected {expected_zone.value}"
        print(msg)
        ERRORS.append(msg)

# -- 8. Rate Limiter Unit Test --
print("\n--- Rate Limiter ---")

from vera.network_zones import ZoneRateLimiter  # noqa: E402

rl = ZoneRateLimiter(requests_per_minute=5, burst=2)

# First 2 should pass (within burst)
r1 = rl.is_allowed("1.2.3.4")
r2 = rl.is_allowed("1.2.3.4")
if r1 and r2:
    PASS += 1
    print("  PASS  Rate limiter: first 2 requests allowed (within burst)")
else:
    FAIL += 1
    ERRORS.append("  FAIL  Rate limiter: burst check failed")
    print("  FAIL  Rate limiter: burst check failed")

# 3rd in same second should be blocked by burst limit
r3 = rl.is_allowed("1.2.3.4")
if not r3:
    PASS += 1
    print("  PASS  Rate limiter: 3rd request blocked (burst=2)")
else:
    FAIL += 1
    ERRORS.append("  FAIL  Rate limiter: burst limit not enforced")
    print("  FAIL  Rate limiter: burst limit not enforced")

# Different IP should still be allowed
r4 = rl.is_allowed("5.6.7.8")
if r4:
    PASS += 1
    print("  PASS  Rate limiter: different IP not affected")
else:
    FAIL += 1
    ERRORS.append("  FAIL  Rate limiter: cross-IP leak")
    print("  FAIL  Rate limiter: cross-IP leak")

# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  ZONE E2E TEST REPORT")
print("=" * 60)
total = PASS + FAIL
print(f"\n  Total tests: {total}")
print(f"  Passed: {PASS}")
print(f"  Failed: {FAIL}")
if total > 0:
    print(f"  Pass rate: {PASS / total * 100:.1f}%\n")

if ERRORS:
    print("  FAILURES:")
    for e in ERRORS:
        print(f"    {e}")

if FAIL == 0:
    print("  *** ALL ZONE E2E TESTS PASSED ***")
else:
    print(f"  *** {FAIL} TEST(S) FAILED ***")

sys.exit(0 if FAIL == 0 else 1)
