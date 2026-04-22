"""AST-based dependency graph extraction — returns JSON node/edge data.

@file vera/brain/tools/dependency_parser.py
@brief Parses Python (ast) and JS (regex) files to produce a dependency graph
       with nodes (files, classes, functions) and edges (imports, calls, inherits).
"""

from __future__ import annotations

import ast
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_dependencies(
    root_path: str,
    file_paths: list[str] | None = None,
    max_files: int = 80,
) -> dict[str, Any]:
    """Build a dependency graph from source files.

    @param root_path: Project root directory.
    @param file_paths: Optional explicit list of files. If None, auto-discover.
    @param max_files: Maximum files to process.
    @return {nodes: [{id, label, type, complexity, path}], edges: [{source, target, type}]}
    """
    from vera.brain.agents.codebase_indexer import _load_gitignore, _should_ignore

    root = Path(root_path).resolve()
    ignore = _load_gitignore(root)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    if file_paths:
        paths = [Path(f) for f in file_paths if Path(f).is_file()]
    else:
        paths = _discover_files(root, ignore, max_files)

    for filepath in paths:
        rel = str(filepath.relative_to(root))
        file_id = _make_id(rel)

        if file_id not in seen_ids:
            from vera.brain.agents.code_analysis import compute_complexity
            try:
                content = filepath.read_text(errors="ignore")
            except Exception:
                content = ""
            nodes.append({
                "id": file_id,
                "label": filepath.name,
                "type": "file",
                "complexity": compute_complexity(content, rel),
                "path": rel,
            })
            seen_ids.add(file_id)

        suffix = filepath.suffix.lower()
        if suffix == ".py":
            _parse_python(filepath, root, nodes, edges, seen_ids)
        elif suffix in (".js", ".jsx", ".ts", ".tsx"):
            _parse_js(filepath, root, nodes, edges, seen_ids)

    return {"nodes": nodes, "edges": edges}


def _discover_files(root: Path, ignore: set[str], max_files: int) -> list[Path]:
    """Walk the project to find source files."""
    from vera.brain.agents.codebase_indexer import _should_ignore

    allowed = {".py", ".js", ".jsx", ".ts", ".tsx"}
    results: list[Path] = []
    for f in root.rglob("*"):
        if len(results) >= max_files:
            break
        if not f.is_file() or f.suffix.lower() not in allowed:
            continue
        if _should_ignore(f, ignore):
            continue
        results.append(f)
    return results


def _make_id(rel_path: str) -> str:
    """Create a stable node ID from a relative path."""
    return rel_path.replace(os.sep, "/").replace("/", "_").replace(".", "_")


def _parse_python(
    filepath: Path,
    root: Path,
    nodes: list[dict],
    edges: list[dict],
    seen_ids: set[str],
) -> None:
    """Extract imports, classes, functions from a Python file via AST."""
    try:
        content = filepath.read_text(errors="ignore")
        tree = ast.parse(content, filename=str(filepath))
    except Exception:
        return

    rel = str(filepath.relative_to(root))
    file_id = _make_id(rel)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            cls_id = f"{file_id}__class_{node.name}"
            if cls_id not in seen_ids:
                nodes.append({
                    "id": cls_id,
                    "label": node.name,
                    "type": "class",
                    "complexity": "medium",
                    "path": rel,
                })
                seen_ids.add(cls_id)
            edges.append({"source": file_id, "target": cls_id, "type": "contains"})

            for base in node.bases:
                base_name = _get_ast_name(base)
                if base_name and base_name != "object":
                    base_id = f"ext_{base_name}"
                    if base_id not in seen_ids:
                        nodes.append({
                            "id": base_id,
                            "label": base_name,
                            "type": "class",
                            "complexity": "low",
                            "path": "",
                        })
                        seen_ids.add(base_id)
                    edges.append({"source": cls_id, "target": base_id, "type": "inherits"})

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if isinstance(getattr(node, '_parent', None), ast.ClassDef):
                continue
            fn_id = f"{file_id}__fn_{node.name}"
            if fn_id not in seen_ids:
                nodes.append({
                    "id": fn_id,
                    "label": node.name,
                    "type": "function",
                    "complexity": "low",
                    "path": rel,
                })
                seen_ids.add(fn_id)
            edges.append({"source": file_id, "target": fn_id, "type": "contains"})

        elif isinstance(node, ast.Import):
            for alias in node.names:
                _add_import_edge(file_id, alias.name, root, nodes, edges, seen_ids)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _add_import_edge(file_id, node.module, root, nodes, edges, seen_ids)


def _add_import_edge(
    source_id: str,
    module_name: str,
    root: Path,
    nodes: list[dict],
    edges: list[dict],
    seen_ids: set[str],
) -> None:
    """Add an import edge, resolving local modules to file nodes."""
    parts = module_name.replace(".", os.sep)
    candidate = root / (parts + ".py")
    if candidate.exists():
        rel = str(candidate.relative_to(root))
        target_id = _make_id(rel)
        if target_id not in seen_ids:
            nodes.append({
                "id": target_id,
                "label": candidate.name,
                "type": "file",
                "complexity": "low",
                "path": rel,
            })
            seen_ids.add(target_id)
    else:
        target_id = f"ext_{module_name.replace('.', '_')}"
        if target_id not in seen_ids:
            nodes.append({
                "id": target_id,
                "label": module_name.split(".")[-1],
                "type": "file",
                "complexity": "low",
                "path": "",
            })
            seen_ids.add(target_id)

    edges.append({"source": source_id, "target": target_id, "type": "imports"})


def _parse_js(
    filepath: Path,
    root: Path,
    nodes: list[dict],
    edges: list[dict],
    seen_ids: set[str],
) -> None:
    """Extract imports and definitions from JS/TS files via regex."""
    try:
        content = filepath.read_text(errors="ignore")
    except Exception:
        return

    rel = str(filepath.relative_to(root))
    file_id = _make_id(rel)

    for match in re.finditer(
        r"(?:import\s+.*?from\s+['\"](.+?)['\"]|require\s*\(\s*['\"](.+?)['\"]\s*\))",
        content,
    ):
        mod = match.group(1) or match.group(2)
        if mod.startswith("."):
            target_id = f"local_{mod.replace('/', '_').replace('.', '_')}"
        else:
            target_id = f"ext_{mod.replace('/', '_').replace('.', '_').replace('@', '')}"

        if target_id not in seen_ids:
            nodes.append({
                "id": target_id,
                "label": mod.split("/")[-1],
                "type": "file",
                "complexity": "low",
                "path": mod if mod.startswith(".") else "",
            })
            seen_ids.add(target_id)

        edges.append({"source": file_id, "target": target_id, "type": "imports"})

    for match in re.finditer(
        r"(?:export\s+)?(?:default\s+)?(?:class|function)\s+(\w+)",
        content,
    ):
        def_id = f"{file_id}__def_{match.group(1)}"
        if def_id not in seen_ids:
            kind = "class" if "class" in match.group(0) else "function"
            nodes.append({
                "id": def_id,
                "label": match.group(1),
                "type": kind,
                "complexity": "low",
                "path": rel,
            })
            seen_ids.add(def_id)
        edges.append({"source": file_id, "target": def_id, "type": "contains"})


def _get_ast_name(node: ast.expr) -> str:
    """Extract a name string from an AST expression node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_get_ast_name(node.value)}.{node.attr}"
    return ""
