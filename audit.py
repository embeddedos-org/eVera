"""Quick audit of eVera project completeness."""
import ast, os, re

print("=" * 50)
print("  eVera v0.5.1 — Project Audit")
print("=" * 50)

# 1. Syntax check all Python files
syntax_ok = 0
syntax_fail = []
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules", ".venv", "dist", "build", ".git")]
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, encoding="utf-8") as fh:
                    ast.parse(fh.read())
                syntax_ok += 1
            except SyntaxError as e:
                syntax_fail.append(f"{path}: {e}")

print(f"\n[Syntax] {syntax_ok} files OK, {len(syntax_fail)} errors")
for e in syntax_fail:
    print(f"  FAIL: {e}")

# 2. Agents
with open("vera/brain/agents/__init__.py") as f:
    content = f.read()
agents = re.findall(r'"(\w+)":\s*\w+Agent', content)
print(f"\n[Agents] {len(agents)} registered: {', '.join(agents)}")

# 3. Plugins
plugins = [f for f in os.listdir("plugins") if f.endswith(".py") and not f.startswith("_")]
print(f"[Plugins] {len(plugins)}: {', '.join(plugins)}")

# 4. Tool classes
tool_count = 0
for root, dirs, files in os.walk("vera/brain/agents"):
    for f in files:
        if f.endswith(".py") and f != "__init__.py":
            with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            for base in node.bases:
                                if isinstance(base, ast.Name) and base.id == "Tool":
                                    tool_count += 1
for f in os.listdir("plugins"):
    if f.endswith(".py") and not f.startswith("_"):
        with open(os.path.join("plugins", f), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "Tool":
                            tool_count += 1
print(f"[Tools] {tool_count} tool classes")

# 5. Docs
docs = [f for f in os.listdir("docs") if f.endswith(".md")]
print(f"[Docs] {len(docs)} markdown files")

# 6. Tests
tests = [f for f in os.listdir("tests") if f.startswith("test_")]
print(f"[Tests] {len(tests)} test files")

# 7. Safety rules
with open("vera/safety/policy.py", encoding="utf-8") as f:
    rules = [l for l in f.readlines() if "PolicyAction." in l and ":" in l and "#" not in l.split(":")[0]]
print(f"[Safety] {len(rules)} policy rules")

# 8. Scheduler loops
with open("vera/scheduler.py", encoding="utf-8") as f:
    loops = re.findall(r"async def _(\w+)_loop", f.read())
print(f"[Scheduler] {len(loops)} loops: {', '.join(loops)}")

# 9. Files summary
py_files = sum(1 for r, d, fs in os.walk("vera") for f in fs if f.endswith(".py"))
print(f"\n[Summary]")
print(f"  Python files in vera/: {py_files}")
print(f"  Agents: {len(agents)} + {len(plugins)} plugins = {len(agents) + len(plugins)}")
print(f"  Tools: {tool_count}")
print(f"  Docs: {len(docs)}")
print(f"  Tests: {len(tests)}")
print(f"  Scheduler loops: {len(loops)}")
print(f"  Syntax errors: {len(syntax_fail)}")
print(f"\n{'ALL CLEAR' if not syntax_fail else 'ISSUES FOUND'}")
