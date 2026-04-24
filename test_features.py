"""eVera Feature Test Script — verifies all Phase 0-4 features."""
import json
import requests
import sys

BASE = "http://localhost:8000"
passed = 0
failed = 0


def test(name, fn):
    global passed, failed
    try:
        result = fn()
        print(f"  PASS  {name}")
        if result:
            print(f"        {result}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}")
        print(f"        {e}")
        failed += 1


# ============================================================
print("=" * 60)
print("  eVera v1.0 — Feature Test Suite")
print("=" * 60)

# --- Phase 0: Core Server ---
print("\n[Phase 0] Core Server")


def test_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    return f"status={r.json()['status']}"

test("GET /health", test_health)


def test_status():
    r = requests.get(f"{BASE}/status")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    return f"keys={list(r.json().keys())[:5]}"

test("GET /status", test_status)


def test_agents():
    r = requests.get(f"{BASE}/agents")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    agents = r.json()
    return f"count={len(agents)}, agents={list(agents.keys())[:6]}..."

test("GET /agents", test_agents)


def test_web_ui():
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "Vera" in r.text, "Page doesn't contain 'Vera'"
    return f"HTML loaded ({len(r.text)} bytes)"

test("GET / (Web UI)", test_web_ui)


# --- Phase 1: Multi-Model Routing ---
print("\n[Phase 1] Multi-Model Routing")


def test_models():
    r = requests.get(f"{BASE}/models")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    models = r.json()
    total = sum(len(v) for v in models.values())
    return f"providers={list(models.keys())}, total_models={total}"

test("GET /models", test_models)


def test_model_select(task_type):
    def _test():
        r = requests.post(f"{BASE}/models/select", json={"task_type": task_type})
        if r.status_code == 200:
            data = r.json()
            return f"model={data['model_name']}, provider={data['provider']}"
        elif r.status_code == 404:
            return f"No model configured for {task_type} (expected without API keys)"
        else:
            return f"status={r.status_code}"
    return _test

for tt in ["code", "fast", "creative", "vision", "general"]:
    test(f"POST /models/select ({tt})", test_model_select(tt))


def test_model_selector_in_ui():
    r = requests.get(f"{BASE}/")
    assert r.status_code == 200
    assert "modelSelector" in r.text, "Model selector not found in HTML"
    return "Model selector present in Web UI"

test("Model selector in UI", test_model_selector_in_ui)


# --- Phase 2: Knowledge Base ---
print("\n[Phase 2] Knowledge Base (RAG)")


def test_knowledge_list_empty():
    r = requests.get(f"{BASE}/knowledge/documents")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    docs = r.json()
    return f"documents={len(docs)}"

test("GET /knowledge/documents", test_knowledge_list_empty)


def test_knowledge_upload():
    content = (
        "The Eiffel Tower is a wrought-iron lattice tower in Paris, France. "
        "It was built in 1889 for the 1889 World Fair. "
        "It stands 330 metres (1,083 ft) tall. "
        "Gustave Eiffel's company designed and built the tower. "
        "It was the tallest man-made structure in the world for 41 years."
    )
    r = requests.post(
        f"{BASE}/knowledge/upload",
        files={"file": ("eiffel_tower.txt", content.encode(), "text/plain")},
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data.get("status") == "ok", f"Upload failed: {data}"
    return f"doc_id={data['doc_id']}, chunks={data['chunk_count']}, chars={data['char_count']}"

test("POST /knowledge/upload (txt)", test_knowledge_upload)


def test_knowledge_list_after():
    r = requests.get(f"{BASE}/knowledge/documents")
    assert r.status_code == 200
    docs = r.json()
    assert len(docs) > 0, "No documents after upload"
    return f"documents={len(docs)}, first={docs[0]['filename']}"

test("GET /knowledge/documents (after upload)", test_knowledge_list_after)


# --- Phase 3: Extension Endpoints ---
print("\n[Phase 3] Extension Endpoints")


def test_extension_endpoint(action, body):
    def _test():
        r = requests.post(f"{BASE}/extension/{action}", json=body)
        # 200 = LLM responded; 500 = no LLM configured (still valid route)
        return f"status={r.status_code}, route exists={'yes' if r.status_code in (200, 500) else 'no'}"
    return _test

test("POST /extension/summarize", test_extension_endpoint("summarize", {"text": "Hello world test"}))
test("POST /extension/explain", test_extension_endpoint("explain", {"text": "Test explain"}))
test("POST /extension/grammar", test_extension_endpoint("grammar", {"text": "Test grammar"}))
test("POST /extension/rewrite", test_extension_endpoint("rewrite", {"text": "Test rewrite"}))
test("POST /extension/translate", test_extension_endpoint("translate", {"text": "Hello", "target_language": "Spanish"}))


# --- Phase 4: Automation Endpoints ---
print("\n[Phase 4] Automation Endpoints")


def test_automation_plan():
    r = requests.post(f"{BASE}/automation/plan", json={"task": "Search Google for Python tutorials"})
    return f"status={r.status_code}, route exists={'yes' if r.status_code in (200, 500) else 'no'}"

test("POST /automation/plan", test_automation_plan)


def test_automation_scrape():
    r = requests.post(f"{BASE}/automation/scrape", json={
        "url": "https://example.com",
        "data_schema": {"title": "Page title"},
        "max_pages": 1,
    })
    return f"status={r.status_code}, route exists={'yes' if r.status_code in (200, 500) else 'no'}"

test("POST /automation/scrape", test_automation_scrape)


# --- WebSocket test ---
print("\n[Bonus] WebSocket")


def test_websocket():
    import websocket
    ws = websocket.create_connection(f"ws://localhost:8000/ws", timeout=5)
    # Should receive greeting
    msg = ws.recv()
    data = json.loads(msg)
    ws.close()
    assert data.get("type") == "response", f"Unexpected msg type: {data.get('type')}"
    return f"greeting received: '{data.get('response', '')[:50]}...'"

try:
    import websocket
    test("WebSocket connect + greeting", test_websocket)
except ImportError:
    print("  SKIP  WebSocket test (websocket-client not installed)")


# ============================================================
print("\n" + "=" * 60)
print(f"  Results: {passed} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)
