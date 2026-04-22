"""Diagram generation tools — call graphs, class diagrams, flowcharts, and export.

@file vera/brain/agents/diagram_tools.py
@brief 4 tools that use Python's ast module to parse code and generate
       Mermaid diagram markup. For JS/TS files, uses regex-based extraction.
"""

from __future__ import annotations

import ast
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from vera.brain.agents.base import Tool

logger = logging.getLogger(__name__)


def _safe_walk(project_path: str, max_files: int = 200) -> list[str]:
    """Collect Python files from a project directory, respecting .gitignore patterns."""
    try:
        from vera.brain.agents.codebase_indexer import _load_gitignore, _should_ignore
        gitignore = _load_gitignore(project_path)
    except ImportError:
        gitignore = []

    py_files = []
    for root, dirs, files in os.walk(project_path):
        # Skip hidden and common non-source dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {
            "__pycache__", "node_modules", ".git", "venv", "env", ".venv",
            "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
        }]
        rel_root = os.path.relpath(root, project_path)

        try:
            if gitignore and _should_ignore(rel_root, gitignore):
                dirs.clear()
                continue
        except Exception:
            pass

        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
                if len(py_files) >= max_files:
                    return py_files
    return py_files


def _parse_python_file(filepath: str) -> ast.Module | None:
    """Parse a Python file into an AST, returning None on failure."""
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            return ast.parse(f.read(), filename=filepath)
    except (SyntaxError, UnicodeDecodeError, OSError) as e:
        logger.debug("Skipping %s: %s", filepath, e)
        return None


class GenerateCallGraphTool(Tool):
    """Generates a call graph Mermaid diagram from a Python project."""

    def __init__(self):
        super().__init__(
            name="generate_call_graph",
            description="Generate a call graph diagram for a Python project. Returns Mermaid markup.",
            parameters={
                "project_path": {"type": "str", "description": "Path to the project root directory"},
                "entry_file": {"type": "str", "description": "Optional entry file to start from (relative path)"},
                "max_depth": {"type": "int", "description": "Maximum call depth to traverse (default: 3)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        project_path = kwargs.get("project_path", ".")
        entry_file = kwargs.get("entry_file", "")
        max_depth = int(kwargs.get("max_depth", 3))

        if not os.path.isdir(project_path):
            return {"error": f"Directory not found: {project_path}"}

        py_files = _safe_walk(project_path)
        if not py_files:
            return {"error": "No Python files found in the project"}

        # If entry_file specified, filter and prioritize
        if entry_file:
            entry_path = os.path.join(project_path, entry_file)
            if os.path.exists(entry_path):
                py_files = [entry_path] + [f for f in py_files if f != entry_path]

        # Build function→calls adjacency map
        func_calls: dict[str, set[str]] = {}
        all_defs: set[str] = set()

        for filepath in py_files[:50]:  # Limit for performance
            tree = _parse_python_file(filepath)
            if not tree:
                continue

            module = os.path.relpath(filepath, project_path).replace(os.sep, ".").replace(".py", "")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check for class context
                    func_key = f"{module}.{node.name}"
                    all_defs.add(func_key)
                    calls = set()

                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            call_name = _get_call_name(child)
                            if call_name:
                                calls.add(call_name)

                    if calls:
                        func_calls[func_key] = calls

        # Generate Mermaid
        lines = ["graph TD"]
        edges_added = set()
        node_ids: dict[str, str] = {}
        counter = [0]

        def get_id(name: str) -> str:
            if name not in node_ids:
                counter[0] += 1
                node_ids[name] = f"N{counter[0]}"
                short = name.split(".")[-1]
                lines.append(f"    {node_ids[name]}[\"{short}\"]")
            return node_ids[name]

        # Build edges with depth limit
        visited = set()

        def add_edges(func: str, depth: int):
            if depth > max_depth or func in visited:
                return
            visited.add(func)
            calls = func_calls.get(func, set())
            for call in calls:
                # Try to resolve to known definitions
                matched = None
                for defined in all_defs:
                    if defined.endswith("." + call) or defined == call:
                        matched = defined
                        break

                target = matched or call
                edge_key = (func, target)
                if edge_key not in edges_added:
                    edges_added.add(edge_key)
                    lines.append(f"    {get_id(func)} --> {get_id(target)}")

                if matched:
                    add_edges(matched, depth + 1)

        # Start from entry points or all top-level functions
        entry_funcs = []
        if entry_file:
            module = entry_file.replace(os.sep, ".").replace(".py", "")
            entry_funcs = [k for k in func_calls if k.startswith(module)]

        if not entry_funcs:
            entry_funcs = list(func_calls.keys())[:20]

        for func in entry_funcs:
            add_edges(func, 0)

        if len(lines) <= 1:
            return {"error": "No call relationships found", "files_scanned": len(py_files)}

        mermaid = "\n".join(lines)
        return {
            "mermaid": mermaid,
            "nodes": len(node_ids),
            "edges": len(edges_added),
            "files_scanned": len(py_files),
        }


class GenerateClassDiagramTool(Tool):
    """Generates a class diagram Mermaid diagram from a Python project."""

    def __init__(self):
        super().__init__(
            name="generate_class_diagram",
            description="Generate a class diagram showing inheritance and methods. Returns Mermaid markup.",
            parameters={
                "project_path": {"type": "str", "description": "Path to the project root directory"},
                "max_classes": {"type": "int", "description": "Maximum number of classes to include (default: 30)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        project_path = kwargs.get("project_path", ".")
        max_classes = int(kwargs.get("max_classes", 30))

        if not os.path.isdir(project_path):
            return {"error": f"Directory not found: {project_path}"}

        py_files = _safe_walk(project_path)
        if not py_files:
            return {"error": "No Python files found"}

        classes: list[dict] = []
        inheritance: list[tuple[str, str]] = []

        for filepath in py_files:
            tree = _parse_python_file(filepath)
            if not tree:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and len(classes) < max_classes:
                    methods = []
                    attributes = []

                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            prefix = "+" if not item.name.startswith("_") else "-"
                            methods.append(f"{prefix}{item.name}()")
                        elif isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    attributes.append(f"+{target.id}")

                    classes.append({
                        "name": node.name,
                        "methods": methods[:10],
                        "attributes": attributes[:5],
                    })

                    # Track inheritance
                    for base in node.bases:
                        base_name = _get_name(base)
                        if base_name and base_name not in ("object",):
                            inheritance.append((node.name, base_name))

        if not classes:
            return {"error": "No classes found in the project"}

        # Generate Mermaid classDiagram
        lines = ["classDiagram"]

        for cls in classes:
            lines.append(f"    class {cls['name']} {{")
            for attr in cls["attributes"]:
                lines.append(f"        {attr}")
            for method in cls["methods"]:
                lines.append(f"        {method}")
            lines.append("    }")

        for child, parent in inheritance:
            lines.append(f"    {parent} <|-- {child}")

        mermaid = "\n".join(lines)
        return {
            "mermaid": mermaid,
            "classes": len(classes),
            "inheritance_links": len(inheritance),
        }


class GenerateFlowchartTool(Tool):
    """Generates a flowchart for a specific Python function."""

    def __init__(self):
        super().__init__(
            name="generate_flowchart",
            description="Generate a control flow flowchart for a specific function. Returns Mermaid markup.",
            parameters={
                "file_path": {"type": "str", "description": "Path to the Python file"},
                "function_name": {"type": "str", "description": "Name of the function to visualize"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        file_path = kwargs.get("file_path", "")
        function_name = kwargs.get("function_name", "")

        if not file_path or not function_name:
            return {"error": "Both file_path and function_name are required"}

        if not os.path.isfile(file_path):
            return {"error": f"File not found: {file_path}"}

        tree = _parse_python_file(file_path)
        if not tree:
            return {"error": f"Failed to parse: {file_path}"}

        # Find the function
        target_func = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    target_func = node
                    break

        if not target_func:
            return {"error": f"Function '{function_name}' not found in {file_path}"}

        # Generate flowchart from AST
        lines = ["flowchart TD"]
        counter = [0]

        def next_id():
            counter[0] += 1
            return f"S{counter[0]}"

        def process_body(stmts, parent_id=None):
            prev_id = parent_id
            for stmt in stmts:
                if isinstance(stmt, ast.If):
                    cond_id = next_id()
                    test_str = _unparse_safe(stmt.test)[:40]
                    lines.append(f"    {cond_id}{{\"{test_str}\"}}")
                    if prev_id:
                        lines.append(f"    {prev_id} --> {cond_id}")

                    # True branch
                    true_id = next_id()
                    lines.append(f"    {true_id}[\"True branch\"]")
                    lines.append(f"    {cond_id} -->|Yes| {true_id}")
                    end_true = process_body(stmt.body, true_id)

                    # False branch
                    if stmt.orelse:
                        false_id = next_id()
                        lines.append(f"    {false_id}[\"False branch\"]")
                        lines.append(f"    {cond_id} -->|No| {false_id}")
                        end_false = process_body(stmt.orelse, false_id)
                    else:
                        end_false = cond_id

                    # Merge
                    merge_id = next_id()
                    lines.append(f"    {merge_id}((\"merge\"))")
                    if end_true:
                        lines.append(f"    {end_true} --> {merge_id}")
                    if end_false and end_false != cond_id:
                        lines.append(f"    {end_false} --> {merge_id}")
                    elif not stmt.orelse:
                        lines.append(f"    {cond_id} -->|No| {merge_id}")

                    prev_id = merge_id

                elif isinstance(stmt, (ast.For, ast.While)):
                    loop_id = next_id()
                    if isinstance(stmt, ast.For):
                        target_str = _unparse_safe(stmt.target)[:20]
                        iter_str = _unparse_safe(stmt.iter)[:20]
                        label = f"for {target_str} in {iter_str}"
                    else:
                        label = f"while {_unparse_safe(stmt.test)[:30]}"
                    lines.append(f"    {loop_id}{{\"{label}\"}}")
                    if prev_id:
                        lines.append(f"    {prev_id} --> {loop_id}")

                    body_id = next_id()
                    lines.append(f"    {body_id}[\"loop body\"]")
                    lines.append(f"    {loop_id} -->|iterate| {body_id}")
                    end_body = process_body(stmt.body, body_id)
                    if end_body:
                        lines.append(f"    {end_body} --> {loop_id}")

                    exit_id = next_id()
                    lines.append(f"    {exit_id}((\"end loop\"))")
                    lines.append(f"    {loop_id} -->|done| {exit_id}")
                    prev_id = exit_id

                elif isinstance(stmt, ast.Try):
                    try_id = next_id()
                    lines.append(f"    {try_id}[\"try\"]")
                    if prev_id:
                        lines.append(f"    {prev_id} --> {try_id}")
                    end_try = process_body(stmt.body, try_id)

                    if stmt.handlers:
                        except_id = next_id()
                        handler_types = ", ".join(
                            _get_name(h.type) if h.type else "Exception"
                            for h in stmt.handlers
                        )
                        lines.append(f"    {except_id}[\"except {handler_types}\"]")
                        lines.append(f"    {try_id} -.->|error| {except_id}")

                    prev_id = end_try or try_id

                elif isinstance(stmt, ast.Return):
                    ret_id = next_id()
                    val_str = _unparse_safe(stmt.value)[:30] if stmt.value else ""
                    lines.append(f"    {ret_id}([\"return {val_str}\"])")
                    if prev_id:
                        lines.append(f"    {prev_id} --> {ret_id}")
                    prev_id = ret_id

                elif isinstance(stmt, ast.Assign):
                    assign_id = next_id()
                    targets_str = ", ".join(_unparse_safe(t)[:20] for t in stmt.targets)
                    lines.append(f"    {assign_id}[\"{targets_str} = ...\"]")
                    if prev_id:
                        lines.append(f"    {prev_id} --> {assign_id}")
                    prev_id = assign_id

                elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call_id = next_id()
                    call_str = _unparse_safe(stmt.value)[:40]
                    lines.append(f"    {call_id}[\"{call_str}\"]")
                    if prev_id:
                        lines.append(f"    {prev_id} --> {call_id}")
                    prev_id = call_id

                else:
                    # Generic statement
                    gen_id = next_id()
                    stmt_type = type(stmt).__name__
                    lines.append(f"    {gen_id}[\"{stmt_type}\"]")
                    if prev_id:
                        lines.append(f"    {prev_id} --> {gen_id}")
                    prev_id = gen_id

            return prev_id

        start_id = next_id()
        lines.append(f"    {start_id}([\"START: {function_name}()\"])")
        process_body(target_func.body, start_id)

        mermaid = "\n".join(lines)
        return {
            "mermaid": mermaid,
            "function": function_name,
            "file": file_path,
            "nodes": counter[0],
        }


class ExportDiagramTool(Tool):
    """Exports a Mermaid diagram to SVG, PNG, or PDF."""

    def __init__(self):
        super().__init__(
            name="export_diagram",
            description="Export a Mermaid diagram to SVG, PNG, or PDF file.",
            parameters={
                "mermaid_text": {"type": "str", "description": "The Mermaid diagram markup text"},
                "format": {"type": "str", "description": "Output format: svg, png, or pdf"},
                "filename": {"type": "str", "description": "Output filename (without extension)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        mermaid_text = kwargs.get("mermaid_text", "")
        fmt = kwargs.get("format", "svg").lower()
        filename = kwargs.get("filename", "diagram")

        if not mermaid_text:
            return {"error": "mermaid_text is required"}

        if fmt not in ("svg", "png", "pdf"):
            return {"error": f"Unsupported format: {fmt}. Use svg, png, or pdf."}

        # Ensure output directory exists
        from config import settings
        output_dir = Path(settings.data_dir) / "diagrams"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{filename}.{fmt}"

        # Write mermaid to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False, encoding="utf-8") as f:
            f.write(mermaid_text)
            input_file = f.name

        try:
            # Try mmdc CLI
            result = subprocess.run(
                ["mmdc", "-i", input_file, "-o", str(output_file), "-b", "transparent"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return {
                    "error": f"mmdc failed: {result.stderr}",
                    "hint": "Install with: npm install -g @mermaid-js/mermaid-cli",
                }

            return {
                "status": "exported",
                "path": str(output_file),
                "format": fmt,
                "size_bytes": output_file.stat().st_size,
            }
        except FileNotFoundError:
            # mmdc not installed — save raw Mermaid as .mmd
            mmd_path = output_dir / f"{filename}.mmd"
            mmd_path.write_text(mermaid_text, encoding="utf-8")
            return {
                "status": "saved_mermaid",
                "path": str(mmd_path),
                "hint": "Install mermaid-cli for SVG/PNG/PDF: npm install -g @mermaid-js/mermaid-cli",
            }
        except subprocess.TimeoutExpired:
            return {"error": "mmdc timed out after 30 seconds"}
        finally:
            try:
                os.unlink(input_file)
            except OSError:
                pass


# --- AST helpers ---

def _get_call_name(node: ast.Call) -> str | None:
    """Extract the function name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    elif isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _get_name(node: ast.expr) -> str:
    """Extract a name string from an AST expression node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_get_name(node.value)}.{node.attr}"
    return ""


def _unparse_safe(node: ast.expr | None) -> str:
    """Safely unparse an AST node to source code string."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__
