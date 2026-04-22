"""Codebase Indexer Agent — project structure analysis and architecture understanding.

@file vera/brain/agents/codebase_indexer.py
@brief Indexes project files, extracts definitions, and answers architectural questions.

Provides tools for building a searchable project index, querying codebase structure,
summarizing architecture, and finding related files.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"

GITIGNORE_DEFAULTS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv", ".env",
    "dist", "build", ".next", ".cache", ".tox", "*.pyc", "*.pyo",
    ".mypy_cache", ".pytest_cache", "egg-info", ".eggs",
}


def _should_ignore(path: Path, gitignore_patterns: set[str]) -> bool:
    """Check if a path should be ignored based on gitignore patterns."""
    name = path.name
    for pattern in gitignore_patterns:
        if pattern.startswith("*."):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern or pattern in str(path):
            return True
    return False


def _load_gitignore(project_path: Path) -> set[str]:
    """Load .gitignore patterns from a project."""
    patterns = set(GITIGNORE_DEFAULTS)
    gitignore = project_path / ".gitignore"
    if gitignore.exists():
        try:
            for line in gitignore.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.add(line.rstrip("/"))
        except Exception:
            pass
    return patterns


def _build_tree(path: Path, max_depth: int = 4, _depth: int = 0, _ignore: set[str] | None = None) -> dict:
    """Build a recursive directory tree respecting .gitignore."""
    if _ignore is None:
        _ignore = _load_gitignore(path)

    result = {"name": path.name, "type": "directory", "children": []}
    if _depth >= max_depth:
        result["truncated"] = True
        return result

    try:
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return result

    for entry in entries:
        if _should_ignore(entry, _ignore):
            continue
        if entry.is_dir():
            child = _build_tree(entry, max_depth, _depth + 1, _ignore)
            result["children"].append(child)
        else:
            result["children"].append({"name": entry.name, "type": "file", "size": entry.stat().st_size})

    return result


def _extract_definitions(filepath: Path) -> list[dict]:
    """Extract class/function names from Python, JS, TS files using regex."""
    defs = []
    suffix = filepath.suffix.lower()

    try:
        content = filepath.read_text(errors="ignore")
    except Exception:
        return defs

    if suffix == ".py":
        for match in re.finditer(r"^(?:class|def|async\s+def)\s+(\w+)", content, re.MULTILINE):
            kind = "class" if content[match.start():match.start() + 5] == "class" else "function"
            defs.append({"name": match.group(1), "kind": kind, "line": content[:match.start()].count("\n") + 1})
    elif suffix in (".js", ".jsx", ".ts", ".tsx"):
        for match in re.finditer(r"(?:export\s+)?(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)", content, re.MULTILINE):
            defs.append({"name": match.group(1), "kind": "definition", "line": content[:match.start()].count("\n") + 1})
    elif suffix in (".java", ".go", ".rs", ".cpp", ".c", ".h"):
        for match in re.finditer(r"(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:class|struct|fn|func|void|int|string)\s+(\w+)", content, re.MULTILINE):
            defs.append({"name": match.group(1), "kind": "definition", "line": content[:match.start()].count("\n") + 1})

    return defs


def _analyze_key_files(path: Path) -> dict:
    """Identify README, config files, and entry points."""
    key_files = {
        "readme": None, "config": [], "entry_points": [], "package_manager": None, "tech_stack": [],
    }

    checks = {
        "README.md": "readme", "README.rst": "readme", "README.txt": "readme", "README": "readme",
    }
    for name, role in checks.items():
        if (path / name).exists():
            key_files[role] = name
            break

    config_patterns = [
        "package.json", "pyproject.toml", "setup.py", "setup.cfg", "Cargo.toml",
        "go.mod", "pom.xml", "build.gradle", "Makefile", "CMakeLists.txt",
        "tsconfig.json", "webpack.config.js", "vite.config.ts", ".eslintrc*",
        "requirements.txt", "Pipfile", "poetry.lock",
    ]
    for pattern in config_patterns:
        matches = list(path.glob(pattern))
        for m in matches:
            key_files["config"].append(m.name)

    if (path / "package.json").exists():
        key_files["package_manager"] = "npm/yarn"
        key_files["tech_stack"].append("Node.js")
        try:
            pkg = json.loads((path / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            for fw in ["react", "vue", "angular", "next", "express", "fastify", "svelte"]:
                if any(fw in d for d in deps):
                    key_files["tech_stack"].append(fw.capitalize())
        except Exception:
            pass
    if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
        key_files["package_manager"] = "pip/poetry"
        key_files["tech_stack"].append("Python")
    if (path / "Cargo.toml").exists():
        key_files["package_manager"] = "cargo"
        key_files["tech_stack"].append("Rust")
    if (path / "go.mod").exists():
        key_files["package_manager"] = "go modules"
        key_files["tech_stack"].append("Go")

    entry_candidates = ["main.py", "app.py", "index.js", "index.ts", "main.go", "main.rs", "Main.java", "server.py", "manage.py"]
    for name in entry_candidates:
        if (path / name).exists():
            key_files["entry_points"].append(name)
    for src_dir in ["src", "lib", "app"]:
        src = path / src_dir
        if src.is_dir():
            for name in entry_candidates:
                if (src / name).exists():
                    key_files["entry_points"].append(f"{src_dir}/{name}")

    return key_files


class IndexProjectTool(Tool):
    def __init__(self):
        super().__init__(
            name="index_project",
            description="Index a project — build file tree, extract definitions, identify key files",
            parameters={"project_path": {"type": "str", "description": "Path to the project directory"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings
        project_path = Path(kwargs.get("project_path", settings.codebase_indexer.default_project_path)).resolve()

        if not project_path.is_dir():
            return {"status": "error", "message": f"Directory not found: {project_path}"}

        ignore = _load_gitignore(project_path)
        allowed_ext = set(settings.codebase_indexer.index_extensions)
        max_files = settings.codebase_indexer.max_files

        tree = _build_tree(project_path, max_depth=4, _ignore=ignore)
        key_files = _analyze_key_files(project_path)

        definitions: dict[str, list] = {}
        file_count = 0
        for f in project_path.rglob("*"):
            if file_count >= max_files:
                break
            if not f.is_file() or f.suffix.lower() not in allowed_ext:
                continue
            if _should_ignore(f, ignore):
                continue
            rel = str(f.relative_to(project_path))
            defs = _extract_definitions(f)
            if defs:
                definitions[rel] = defs
            file_count += 1

        index = {
            "project_path": str(project_path),
            "tree": tree,
            "key_files": key_files,
            "definitions": definitions,
            "file_count": file_count,
            "indexed_at": __import__("datetime").datetime.now().isoformat(),
        }

        index_path = DATA_DIR / "codebase_index.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps(index, indent=2, default=str))

        total_defs = sum(len(d) for d in definitions.values())
        return {
            "status": "success",
            "project": project_path.name,
            "files_indexed": file_count,
            "definitions_found": total_defs,
            "tech_stack": key_files.get("tech_stack", []),
            "entry_points": key_files.get("entry_points", []),
        }


class QueryCodebaseTool(Tool):
    def __init__(self):
        super().__init__(
            name="query_codebase",
            description="Ask a question about the codebase architecture or structure",
            parameters={
                "question": {"type": "str", "description": "Question about the codebase"},
                "project_path": {"type": "str", "description": "Project path (uses last indexed if not set)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        question = kwargs.get("question", "")
        if not question:
            return {"status": "error", "message": "question is required"}

        index_path = DATA_DIR / "codebase_index.json"
        if not index_path.exists():
            return {"status": "error", "message": "No codebase index found. Run 'index_project' first."}

        try:
            index = json.loads(index_path.read_text())
        except Exception as e:
            return {"status": "error", "message": f"Failed to load index: {e}"}

        context = json.dumps({
            "project": index.get("project_path", ""),
            "key_files": index.get("key_files", {}),
            "definitions": {k: v for k, v in list(index.get("definitions", {}).items())[:30]},
            "file_count": index.get("file_count", 0),
        }, indent=1)

        try:
            from vera.providers.manager import ProviderManager
            provider = ProviderManager()
            result = await provider.complete(
                messages=[
                    {"role": "system", "content": (
                        "You are a codebase analyst. Using the project index below, answer the user's "
                        "question about the architecture, structure, or code organization. Be specific "
                        "and reference actual file paths and definitions.\n\n"
                        f"Project Index:\n{context}"
                    )},
                    {"role": "user", "content": question},
                ],
                tier=ModelTier.SPECIALIST,
            )
            return {"status": "success", "answer": result.content}
        except Exception as e:
            return {"status": "error", "message": f"LLM query failed: {e}"}


class GetArchitectureSummaryTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_architecture_summary",
            description="Get a high-level architecture summary of a project",
            parameters={"project_path": {"type": "str", "description": "Project path (uses last indexed if not set)"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        project_path = kwargs.get("project_path", "")

        index_path = DATA_DIR / "codebase_index.json"
        if project_path:
            p = Path(project_path).resolve()
            if not p.is_dir():
                return {"status": "error", "message": f"Directory not found: {p}"}
            key_files = _analyze_key_files(p)
            tree = _build_tree(p, max_depth=3)
            project_name = p.name
        elif index_path.exists():
            try:
                index = json.loads(index_path.read_text())
                key_files = index.get("key_files", {})
                tree = index.get("tree", {})
                project_name = Path(index.get("project_path", "")).name
            except Exception:
                return {"status": "error", "message": "Failed to load index"}
        else:
            return {"status": "error", "message": "No project path or index available. Run 'index_project' first."}

        def _tree_to_text(node, indent=0):
            lines = []
            prefix = "  " * indent
            name = node.get("name", "")
            if node.get("type") == "directory":
                lines.append(f"{prefix}{name}/")
                for child in node.get("children", [])[:20]:
                    lines.extend(_tree_to_text(child, indent + 1))
                if len(node.get("children", [])) > 20:
                    lines.append(f"{prefix}  ... and {len(node['children']) - 20} more")
            else:
                lines.append(f"{prefix}{name}")
            return lines

        tree_text = "\n".join(_tree_to_text(tree))

        return {
            "status": "success",
            "project": project_name,
            "tech_stack": key_files.get("tech_stack", []),
            "entry_points": key_files.get("entry_points", []),
            "config_files": key_files.get("config", []),
            "readme": key_files.get("readme"),
            "package_manager": key_files.get("package_manager"),
            "tree": tree_text[:3000],
        }


class FindRelatedFilesTool(Tool):
    def __init__(self):
        super().__init__(
            name="find_related_files",
            description="Find files that import or reference a given file",
            parameters={
                "file_path": {"type": "str", "description": "File to find references for"},
                "project_path": {"type": "str", "description": "Project root path"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings

        file_path = kwargs.get("file_path", "")
        project_path = Path(kwargs.get("project_path", settings.codebase_indexer.default_project_path)).resolve()

        if not file_path:
            return {"status": "error", "message": "file_path is required"}

        target = Path(file_path)
        target_stem = target.stem
        target_name = target.name

        ignore = _load_gitignore(project_path)
        allowed_ext = set(settings.codebase_indexer.index_extensions)

        related = []
        for f in project_path.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in allowed_ext:
                continue
            if _should_ignore(f, ignore):
                continue
            if f.name == target_name:
                continue

            try:
                content = f.read_text(errors="ignore")
                if target_stem in content or target_name in content:
                    rel = str(f.relative_to(project_path))
                    lines = [i + 1 for i, line in enumerate(content.splitlines())
                             if target_stem in line or target_name in line]
                    related.append({"file": rel, "reference_lines": lines[:10]})
            except Exception:
                continue

            if len(related) >= 30:
                break

        return {
            "status": "success",
            "target": file_path,
            "related_files": related,
            "count": len(related),
        }


class CodebaseIndexerAgent(BaseAgent):
    """Codebase indexing, architecture analysis, and project understanding."""

    name = "codebase_indexer"
    description = "Index and analyze codebases — project structure, architecture, definitions, related files"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a codebase analysis assistant. You can index projects to build a searchable "
        "map of files and definitions, answer architectural questions, summarize project structure, "
        "and find related files. Always index the project first before answering questions."
    )

    offline_responses = {
        "index": "📁 I can help index your project! Give me the path.",
        "codebase": "🗺️ Let me analyze the codebase for you!",
        "architecture": "🏗️ I'll map out the architecture!",
        "project_structure": "📂 Let me look at the project structure!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            IndexProjectTool(),
            QueryCodebaseTool(),
            GetArchitectureSummaryTool(),
            FindRelatedFilesTool(),
        ]
