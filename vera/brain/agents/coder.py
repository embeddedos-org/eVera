"""Coder Agent — reads, writes, searches code files and integrates with VS Code."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from config import settings
from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

# Allowed base directories for file operations (user's home + current working dir)
ALLOWED_ROOTS = [
    Path.home(),
    Path.cwd(),
]

# Extend with user-configured extra paths
for _extra in settings.safety.coder_allowed_extra_paths:
    _p = Path(_extra).expanduser().resolve()
    if _p not in ALLOWED_ROOTS:
        ALLOWED_ROOTS.append(_p)

# Blocked paths (never allow reading/writing these)
BLOCKED_PATHS = [
    ".ssh",
    ".gnupg",
    ".aws",
    ".config/gcloud",
    "AppData/Roaming/Microsoft/Credentials",
    ".env",
    ".env.local",
    ".env.production",
]


def _is_path_safe(path: Path) -> tuple[bool, str]:
    """Check if a path is within allowed directories and not in blocked list.

    When VERA_SAFETY_CODER_UNSAFE_PATHS is True, blocked-path violations are
    downgraded to logged warnings instead of hard rejections.
    """
    resolved = path.resolve()

    # Check blocked paths
    path_str = str(resolved).replace("\\", "/").lower()
    for blocked in BLOCKED_PATHS:
        if blocked.lower() in path_str:
            if settings.safety.coder_unsafe_paths:
                logger.warning(
                    "UNSAFE-PATH override: allowing blocked segment '%s' in %s",
                    blocked,
                    resolved,
                )
                break  # skip block, fall through to root check
            return False, f"Access denied: path contains blocked segment '{blocked}'"

    # Check if within allowed roots
    for root in ALLOWED_ROOTS:
        try:
            resolved.relative_to(root.resolve())
            return True, ""
        except ValueError:
            continue

    if settings.safety.coder_unsafe_paths:
        logger.warning("UNSAFE-PATH override: allowing path outside roots: %s", resolved)
        return True, ""

    return False, f"Access denied: path {resolved} is outside allowed directories"


class ReadFileTool(Tool):
    """Read the contents of a file."""

    def __init__(self) -> None:
        super().__init__(
            name="read_file",
            description="Read the contents of a file",
            parameters={
                "path": {"type": "str", "description": "File path to read"},
                "start_line": {"type": "int", "description": "Start line (optional, 1-based)"},
                "end_line": {"type": "int", "description": "End line (optional, 1-based)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        path_str = kwargs.get("path", "")
        start = kwargs.get("start_line", 0)
        end = kwargs.get("end_line", 0)

        if not path_str:
            return {"status": "error", "message": "No file path provided"}

        path = Path(path_str).expanduser()
        safe, reason = _is_path_safe(path)
        if not safe:
            return {"status": "error", "message": reason}
        if not path.exists():
            return {"status": "error", "message": f"File not found: {path}"}
        if not path.is_file():
            return {"status": "error", "message": f"Not a file: {path}"}

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            if start and end:
                lines = lines[max(0, start - 1) : end]
                content = "\n".join(lines)

            # Truncate if too large
            if len(content) > 10000:
                content = content[:10000] + f"\n... [truncated, {len(lines)} total lines]"

            return {
                "status": "success",
                "path": str(path),
                "content": content,
                "lines": len(lines),
                "size": path.stat().st_size,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WriteFileTool(Tool):
    """Write or overwrite a file."""

    def __init__(self) -> None:
        super().__init__(
            name="write_file",
            description="Write content to a file (creates or overwrites)",
            parameters={
                "path": {"type": "str", "description": "File path to write"},
                "content": {"type": "str", "description": "Content to write"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        path_str = kwargs.get("path", "")
        content = kwargs.get("content", "")

        if not path_str:
            return {"status": "error", "message": "No file path provided"}

        path = Path(path_str).expanduser()
        safe, reason = _is_path_safe(path)
        if not safe:
            return {"status": "error", "message": reason}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {
                "status": "success",
                "path": str(path),
                "size": path.stat().st_size,
                "lines": len(content.splitlines()),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class EditFileTool(Tool):
    """Edit a file by replacing specific text."""

    def __init__(self) -> None:
        super().__init__(
            name="edit_file",
            description="Edit a file by replacing old text with new text",
            parameters={
                "path": {"type": "str", "description": "File path to edit"},
                "old_text": {"type": "str", "description": "Text to find and replace"},
                "new_text": {"type": "str", "description": "Replacement text"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        path_str = kwargs.get("path", "")
        old_text = kwargs.get("old_text", "")
        new_text = kwargs.get("new_text", "")

        if not path_str or not old_text:
            return {"status": "error", "message": "path and old_text are required"}

        path = Path(path_str).expanduser()
        safe, reason = _is_path_safe(path)
        if not safe:
            return {"status": "error", "message": reason}
        if not path.exists():
            return {"status": "error", "message": f"File not found: {path}"}

        try:
            content = path.read_text(encoding="utf-8")
            if old_text not in content:
                return {"status": "error", "message": "old_text not found in file"}

            new_content = content.replace(old_text, new_text, 1)
            path.write_text(new_content, encoding="utf-8")
            return {"status": "success", "path": str(path), "replaced": True}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class SearchInFilesTool(Tool):
    """Search for text patterns across files."""

    def __init__(self) -> None:
        super().__init__(
            name="search_in_files",
            description="Search for text or regex pattern in files within a directory",
            parameters={
                "pattern": {"type": "str", "description": "Text or regex pattern to search"},
                "directory": {"type": "str", "description": "Directory to search in"},
                "file_pattern": {"type": "str", "description": "File glob pattern (e.g. *.py, *.js)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        pattern = kwargs.get("pattern", "")
        directory = kwargs.get("directory", ".")
        file_glob = kwargs.get("file_pattern", "*")

        if not pattern:
            return {"status": "error", "message": "No search pattern provided"}

        dir_path = Path(directory).expanduser()
        if not dir_path.exists():
            return {"status": "error", "message": f"Directory not found: {dir_path}"}

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            regex = re.compile(re.escape(pattern), re.IGNORECASE)

        matches = []
        try:
            for file_path in dir_path.rglob(file_glob):
                if not file_path.is_file():
                    continue
                if any(part.startswith(".") for part in file_path.parts):
                    continue
                if file_path.stat().st_size > 1_000_000:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(content.splitlines(), 1):
                        if regex.search(line):
                            matches.append(
                                {
                                    "file": str(file_path),
                                    "line": i,
                                    "text": line.strip()[:200],
                                }
                            )
                            if len(matches) >= 50:
                                break
                except (UnicodeDecodeError, PermissionError):
                    continue

                if len(matches) >= 50:
                    break

            return {"status": "success", "pattern": pattern, "matches": matches, "count": len(matches)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class OpenInVSCodeTool(Tool):
    """Open a file or folder in VS Code."""

    def __init__(self) -> None:
        super().__init__(
            name="open_in_vscode",
            description="Open a file or folder in VS Code",
            parameters={
                "path": {"type": "str", "description": "File or folder path to open"},
                "line": {"type": "int", "description": "Line number to go to (optional)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        path_str = kwargs.get("path", "")
        line = kwargs.get("line", 0)

        if not path_str:
            return {"status": "error", "message": "No path provided"}

        try:
            cmd = ["code"]
            if line:
                cmd.extend(["--goto", f"{path_str}:{line}"])
            else:
                cmd.append(path_str)

            subprocess.Popen(cmd, start_new_session=True)
            return {"status": "success", "opened": path_str, "line": line}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class CoderAgent(BaseAgent):
    """Reads, writes, searches code files and integrates with VS Code."""

    name = "coder"
    description = "Read, write, edit, and search code files; open in VS Code"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a coding assistant. You can read, write, and edit code files, "
        "search across codebases, and open files in VS Code. "
        "When the user asks to create a file, use write_file. "
        "When they want to modify code, read the file first with read_file, "
        "then use edit_file to make targeted changes. "
        "When they want to find something in code, use search_in_files. "
        "When they want to open a file, use open_in_vscode. "
        "Always show the user what you changed and explain why."
    )

    offline_responses = {
        "code": "💻 I can help with code! Connect an LLM for full coding power!",
        "edit": "✏️ I'll edit that code for you!",
        "create": "📝 I'll create that file for you!",
        "find": "🔍 Searching your codebase!",
        "search": "🔍 Let me search for that in your code!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            ReadFileTool(),
            WriteFileTool(),
            EditFileTool(),
            SearchInFilesTool(),
            OpenInVSCodeTool(),
        ]
