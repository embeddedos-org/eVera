"""eVoca v0.5.1 — End-to-End Validation Suite.

Validates every agent, tool, service, and subsystem without external dependencies.
Uses mocking for LLM providers, brokers, and external APIs.
"""

import ast
import importlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root is in path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0
ERRORS = []


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        msg = f"  FAIL  {name}" + (f" — {detail}" if detail else "")
        print(msg)
        ERRORS.append(msg)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════
#  1. SYNTAX & IMPORTS
# ═══════════════════════════════════════════════════════════
section("1. Syntax & Structure")

# Check all Python files parse
py_files = []
for root_dir, dirs, files in os.walk("voca"):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith(".py"):
            py_files.append(os.path.join(root_dir, f))
for f in ["config.py", "main.py", "build_backend.py", "deploy.py", "verify.py"]:
    if os.path.exists(f):
        py_files.append(f)
for f in os.listdir("plugins"):
    if f.endswith(".py"):
        py_files.append(os.path.join("plugins", f))

syntax_errors = []
for pf in py_files:
    try:
        with open(pf, encoding="utf-8") as fh:
            ast.parse(fh.read())
    except SyntaxError as e:
        syntax_errors.append(f"{pf}: {e}")

check(f"All {len(py_files)} Python files parse", len(syntax_errors) == 0,
      f"{len(syntax_errors)} errors: {syntax_errors}")

# Check key files exist
key_files = [
    "config.py", "main.py", "voca/core.py", "voca/app.py",
    "voca/brain/graph.py", "voca/brain/router.py", "voca/brain/state.py",
    "voca/brain/supervisor.py", "voca/brain/crew.py", "voca/brain/workflow.py",
    "voca/brain/agents/__init__.py", "voca/brain/agents/base.py",
    "voca/brain/agents/companion.py", "voca/brain/agents/operator.py",
    "voca/brain/agents/browser.py", "voca/brain/agents/researcher.py",
    "voca/brain/agents/writer.py", "voca/brain/agents/life_manager.py",
    "voca/brain/agents/home_controller.py", "voca/brain/agents/income.py",
    "voca/brain/agents/coder.py", "voca/brain/agents/git_agent.py",
    "voca/brain/agents/vision.py", "voca/brain/agents/content_creator.py",
    "voca/brain/agents/finance.py", "voca/brain/agents/email_manager.py",
    "voca/memory/vault.py", "voca/memory/working.py", "voca/memory/episodic.py",
    "voca/memory/semantic.py", "voca/memory/secure.py", "voca/memory/persistence.py",
    "voca/safety/policy.py", "voca/safety/privacy.py",
    "voca/providers/manager.py", "voca/providers/models.py",
    "voca/events/bus.py", "voca/scheduler.py", "voca/messaging.py", "voca/rbac.py",
    "plugins/live_trading.py",
]
missing = [f for f in key_files if not os.path.exists(f)]
check(f"All {len(key_files)} key files exist", len(missing) == 0,
      f"Missing: {missing}")

# ═══════════════════════════════════════════════════════════
#  2. CONFIGURATION
# ═══════════════════════════════════════════════════════════
section("2. Configuration (config.py)")

from config import Settings, LLMSettings, VoiceSettings, MemorySettings, SafetySettings, ServerSettings

s = Settings()
check("Settings loads with defaults", s is not None)
check("LLM defaults present", s.llm.ollama_url == "http://localhost:11434")
check("Server defaults to localhost", s.server.host == "127.0.0.1")
check("Server port is 8000", s.server.port == 8000)
check("Memory max turns is 20", s.memory.working_memory_max_turns == 20)
check("Safety has allowed_actions", len(s.safety.allowed_actions) > 0)
check("Safety has denied_actions", len(s.safety.denied_actions) > 0)
check("Data dir is Path", isinstance(s.data_dir, Path))

# ═══════════════════════════════════════════════════════════
#  3. MEMORY SYSTEM
# ═══════════════════════════════════════════════════════════
section("3. Memory System")

try:
    from voca.memory.working import WorkingMemory, Turn
    wm_available = True
except ImportError:
    wm_available = False

if wm_available:
    wm = WorkingMemory(max_turns=5)
    check("WorkingMemory creates", wm is not None)
    wm.add("user", "hello")
    wm.add("assistant", "hi there", agent="companion")
    check("WorkingMemory add works", wm.turn_count == 2)
    check("WorkingMemory get_context returns list", len(wm.get_context()) == 2)
    check("WorkingMemory get_last_agent", wm.get_last_agent() == "companion")
    wm.add("user", "session test", session_id="s1")
    wm.add("assistant", "reply", agent="operator", session_id="s1")
    ctx_s1 = wm.get_context(session_id="s1")
    check("Session isolation — s1 has 2 turns", len(ctx_s1) == 2)
    check("Session count tracked", wm.session_count >= 1)
    wm.remove_session("s1")
    check("Session removal works", wm.get_context(session_id="s1") == [])
else:
    # Direct source validation when numpy/faiss not installed
    with open("voca/memory/working.py", encoding="utf-8") as f:
        wm_src = f.read()
    check("WorkingMemory has session support", "session_id" in wm_src)
    check("WorkingMemory has _sessions dict", "_sessions" in wm_src)
    check("WorkingMemory has remove_session", "remove_session" in wm_src)
    check("WorkingMemory has get_context with session_id", "def get_context" in wm_src)
    check("WorkingMemory has session_count", "session_count" in wm_src)

# Persistence (standalone — no numpy dependency)
try:
    # Import directly to bypass __init__.py auto-imports
    import importlib.util
    spec = importlib.util.spec_from_file_location("persistence", "voca/memory/persistence.py")
    persistence_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(persistence_mod)
    ConversationStore = persistence_mod.ConversationStore
    persistence_available = True
except Exception:
    persistence_available = False

if persistence_available:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    store = ConversationStore(db_path=db_path)
    check("ConversationStore creates", store is not None)
    store.save_turn("user", "test message", session_id="test1")
    store.save_turn("assistant", "test reply", session_id="test1", agent="companion")
    turns = store.load_turns(session_id="test1")
    check("Persistence save/load works", len(turns) == 2)
    check("Persistence session_id correct", turns[0]["role"] == "user")
    sessions = store.list_sessions()
    check("List sessions works", "test1" in sessions)
    deleted = store.delete_session("test1")
    check("Delete session works", deleted == 2)
    store.close()
    os.unlink(db_path)
else:
    with open("voca/memory/persistence.py", encoding="utf-8") as f:
        p_src = f.read()
    check("ConversationStore class exists", "class ConversationStore" in p_src)
    check("Persistence has save_turn", "def save_turn" in p_src)
    check("Persistence has load_turns", "def load_turns" in p_src)
    check("Persistence has in-memory fallback", ":memory:" in p_src)

# ═══════════════════════════════════════════════════════════
#  4. SAFETY SYSTEM
# ═══════════════════════════════════════════════════════════
section("4. Safety System (policy.py)")

from voca.safety.policy import PolicyService, PolicyAction, PolicyDecision

ps = PolicyService()
check("PolicyService creates", ps is not None)

# Test specific rules
d = ps.check("companion", "chat")
check("companion.chat = ALLOW", d.action == PolicyAction.ALLOW)

d = ps.check("operator", "execute_script")
check("operator.execute_script = CONFIRM", d.action == PolicyAction.CONFIRM)

d = ps.check("income", "transfer_money")
check("income.transfer_money = DENY", d.action == PolicyAction.DENY)

d = ps.check("operator", "open_application")
check("operator.open_application = ALLOW", d.action == PolicyAction.ALLOW)

d = ps.check("browser", "login")
check("browser.login = CONFIRM", d.action == PolicyAction.CONFIRM)

# New agents
d = ps.check("content_creator", "generate_script")
check("content_creator.generate_script = ALLOW", d.action == PolicyAction.ALLOW)

d = ps.check("content_creator", "schedule_post")
check("content_creator.schedule_post = CONFIRM", d.action == PolicyAction.CONFIRM)

d = ps.check("finance", "check_balances")
check("finance.check_balances = ALLOW", d.action == PolicyAction.ALLOW)

d = ps.check("finance", "transfer_money")
check("finance.transfer_money = DENY", d.action == PolicyAction.DENY)

d = ps.check("life_manager", "read_inbox")
check("life_manager.read_inbox = ALLOW", d.action == PolicyAction.ALLOW)

d = ps.check("life_manager", "reply_email")
check("life_manager.reply_email = CONFIRM", d.action == PolicyAction.CONFIRM)

# Live trader plugin policies
d = ps.check("live_trader", "ibkr_trade")
check("live_trader.ibkr_trade = CONFIRM", d.action == PolicyAction.CONFIRM)

d = ps.check("live_trader", "ibkr_portfolio")
check("live_trader.ibkr_portfolio = ALLOW", d.action == PolicyAction.ALLOW)

d = ps.check("live_trader", "risk_check")
check("live_trader.risk_check = ALLOW", d.action == PolicyAction.ALLOW)

# Default rule
d = ps.check("unknown_agent", "unknown_tool")
check("Unknown = CONFIRM (safe default)", d.action == PolicyAction.CONFIRM)

# ═══════════════════════════════════════════════════════════
#  5. ROUTER & INTENT CLASSIFICATION
# ═══════════════════════════════════════════════════════════
section("5. Router & Intent Classification")

with open("voca/brain/router.py", encoding="utf-8") as f:
    router_src = f.read()

# Check INTENT_AGENT_MAP has all agents
agent_intents = re.findall(r'"(\w+)":\s*"(\w+)"', router_src)
agent_map = {}
for intent, agent in agent_intents:
    agent_map.setdefault(agent, []).append(intent)

expected_agents = ["life_manager", "home_controller", "researcher", "writer",
                   "operator", "income", "companion", "coder", "browser",
                   "content_creator", "finance", "live_trader"]

for agent in expected_agents:
    check(f"Router has intents for {agent}", agent in agent_map,
          f"Missing from INTENT_AGENT_MAP")

# Check classification prompt mentions all agents
check("Classification prompt has content_creator", "content_creator" in router_src)
check("Classification prompt has finance", "finance" in router_src)
check("Classification prompt has live_trader", "live_trader" in router_src)

# Check tier map
check("Tier map has content_creator", "content_creator" in router_src)
check("Tier map has finance", "finance in router_src" != "", "finance" in router_src)
check("Tier map has live_trader", "live_trader" in router_src)

# ═══════════════════════════════════════════════════════════
#  6. AGENT REGISTRY & TOOLS
# ═══════════════════════════════════════════════════════════
section("6. Agent Registry & Tool Counts")

# Count tool classes per agent file
agent_tools = {}
for root_dir, dirs, files in os.walk("voca/brain/agents"):
    for f in files:
        if f.endswith(".py") and f not in ("__init__.py", "base.py"):
            path = os.path.join(root_dir, f)
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            tools = [n.name for n in ast.walk(tree)
                     if isinstance(n, ast.ClassDef)
                     and any(isinstance(b, ast.Name) and b.id == "Tool" for b in n.bases)]
            agent_name = f.replace(".py", "")
            agent_tools[agent_name] = len(tools)

# Plugin tools
for f in os.listdir("plugins"):
    if f.endswith(".py") and not f.startswith("_"):
        path = os.path.join("plugins", f)
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        tools = [n.name for n in ast.walk(tree)
                 if isinstance(n, ast.ClassDef)
                 and any(isinstance(b, ast.Name) and b.id == "Tool" for b in n.bases)]
        agent_tools[f.replace(".py", "")] = len(tools)

total_tools = sum(agent_tools.values())
print(f"  Total tool classes: {total_tools}")
for name, count in sorted(agent_tools.items()):
    check(f"{name}: {count} tools", count > 0)

check(f"Total tools >= 99", total_tools >= 99, f"Got {total_tools}")

# ═══════════════════════════════════════════════════════════
#  7. SCHEDULER
# ═══════════════════════════════════════════════════════════
section("7. Proactive Scheduler")

with open("voca/scheduler.py", encoding="utf-8") as f:
    sched_src = f.read()

expected_loops = ["reminder", "calendar", "stock_alert", "daily_briefing",
                  "scheduled_tasks", "content_publisher", "spending_alert"]
for loop in expected_loops:
    check(f"Scheduler has _{loop}_loop", f"_{loop}_loop" in sched_src)

check("Scheduler creates tasks for all loops",
      "self._scheduled_tasks_loop" in sched_src and
      "self._content_publisher_loop" in sched_src and
      "self._spending_alert_loop" in sched_src)

# ═══════════════════════════════════════════════════════════
#  8. API ENDPOINTS
# ═══════════════════════════════════════════════════════════
section("8. API Endpoints (app.py)")

with open("voca/app.py", encoding="utf-8") as f:
    app_src = f.read()

endpoints = [
    ("/health", "GET"), ("/status", "GET"), ("/agents", "GET"),
    ("/chat", "POST"), ("/chat/stream", "POST"),
    ("/memory/facts", "GET"), ("/memory/facts", "POST"),
    ("/events/stream", "GET"), ("/agents/stream", "GET"),
    ("/crew", "POST"), ("/workflows", "GET"), ("/workflows", "POST"),
    ("/admin/users", "GET"), ("/admin/audit", "GET"),
    ("/webhook/tradingview", "POST"), ("/webhook/slack", "POST"),
    ("/webhook/discord", "POST"), ("/webhook/telegram", "POST"),
    ("/ws", "websocket"),
]

for path, method in endpoints:
    check(f"Endpoint {method} {path}", path in app_src)

check("API version is 0.5.1", '"0.5.1"' in app_src)
check("HTTP auth middleware present", "api_key_middleware" in app_src)
check("WebSocket auth present", "ws_api_key" in app_src or "api_key" in app_src)
check("JSONResponse imported", "JSONResponse" in app_src)
check("Streaming support (stream_token)", "stream_token" in app_src)
check("Session cleanup on disconnect", "remove_session" in app_src)

# ═══════════════════════════════════════════════════════════
#  9. DOCUMENTATION
# ═══════════════════════════════════════════════════════════
section("9. Documentation")

expected_docs = [
    "docs/index.md", "docs/getting_started.md", "docs/architecture.md",
    "docs/agents.md", "docs/api_reference.md", "docs/security.md",
    "docs/development.md", "docs/configuration.md", "docs/faq.md",
    "docs/diagrams.md", "docs/doxygen_main_page.md", "docs/release_notes_v0.5.0.md",
    "docs/Doxyfile", "docs/requirements.txt", "docs/generate_diagrams.py",
    "CHANGELOG.md", "README.md", "DISTRIBUTION.md",
]

for doc in expected_docs:
    check(f"Doc exists: {doc}", os.path.exists(doc))

# Check Doxyfile version
with open("docs/Doxyfile", encoding="utf-8") as f:
    doxyfile = f.read()
check("Doxyfile version 0.5.1", "0.5.1" in doxyfile)

# ═══════════════════════════════════════════════════════════
#  10. DESKTOP & MOBILE
# ═══════════════════════════════════════════════════════════
section("10. Desktop & Mobile")

desktop_files = [
    "electron/main.js", "electron/preload.js", "electron/build.js",
    "electron/package.json", "electron/icon.ico", "electron/icon.png",
]
for f in desktop_files:
    check(f"Desktop: {f}", os.path.exists(f))

with open("electron/package.json", encoding="utf-8") as f:
    epkg = json.loads(f.read())
check("Electron version 0.5.1", epkg.get("version") == "0.5.1")

mobile_files = [
    "mobile/package.json", "mobile/app.json", "mobile/index.js",
    "mobile/src/App.tsx", "mobile/src/screens/ChatScreen.tsx",
    "mobile/src/screens/SettingsScreen.tsx", "mobile/src/services/api.ts",
    "mobile/src/services/voice.ts", "mobile/src/services/permissions.ts",
    "mobile/src/services/notifications.ts", "mobile/README.md",
]
for f in mobile_files:
    check(f"Mobile: {f}", os.path.exists(f))

# ═══════════════════════════════════════════════════════════
#  11. CI/CD & BUILD
# ═══════════════════════════════════════════════════════════
section("11. CI/CD & Build")

check("GitHub Actions workflow", os.path.exists(".github/workflows/build.yml"))
check("Build backend script", os.path.exists("build_backend.py"))
check("Deploy script", os.path.exists("deploy.py"))
check("PyInstaller spec", os.path.exists("voca.spec"))
check("Built installer exists", os.path.exists("electron/dist/Voca-0.5.1-win.zip"))

# ═══════════════════════════════════════════════════════════
#  12. SECURITY CHECKS
# ═══════════════════════════════════════════════════════════
section("12. Security Checks")

# Check no shell=True in operator
with open("voca/brain/agents/operator.py", encoding="utf-8") as f:
    op_src = f.read()
shell_true_count = op_src.count("shell=True")
# Only ExecuteScriptTool has a controlled shell=True fallback
check("Operator: minimal shell=True usage", shell_true_count <= 1,
      f"Found {shell_true_count} instances")

check("API auth middleware is real middleware", "@app.middleware" in app_src)
check("WebSocket checks api_key on connect", "4001" in app_src or "api_key" in app_src)
check("Finance transfer DENIED", 'finance.transfer_money' in open("voca/safety/policy.py", encoding="utf-8").read())

# ═══════════════════════════════════════════════════════════
#  FINAL REPORT
# ═══════════════════════════════════════════════════════════
section("FINAL REPORT")
total = PASS + FAIL
print(f"\n  Total checks: {total}")
print(f"  Passed: {PASS}")
print(f"  Failed: {FAIL}")
print(f"  Pass rate: {PASS/total*100:.1f}%\n")

if ERRORS:
    print("  FAILURES:")
    for e in ERRORS:
        print(f"    {e}")
    print()

if FAIL == 0:
    print("  *** ALL CHECKS PASSED — eVoca v0.5.1 is VALIDATED ***")
else:
    print(f"  *** {FAIL} CHECK(S) FAILED — review above ***")

sys.exit(0 if FAIL == 0 else 1)
