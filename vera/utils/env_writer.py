"""Utility for reading and writing .env files while preserving comments."""

from __future__ import annotations

import re
from pathlib import Path


def update_env_file(key: str, value: str, env_path: str = ".env") -> None:
    """Add or update a key in a .env file, preserving existing comments and order.

    If the key already exists, its value is replaced in-place.
    If it doesn't exist, a new line is appended.
    Values containing spaces or special characters are automatically quoted.
    """
    path = Path(env_path)
    lines: list[str] = []

    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    # Quote value if it contains spaces, #, or quotes
    safe_value = value
    if any(c in value for c in (" ", "#", '"', "'", "=", "\n")):
        safe_value = '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    pattern = re.compile(rf"^{re.escape(key)}\s*=", re.MULTILINE)
    found = False

    new_lines: list[str] = []
    for line in lines:
        if pattern.match(line.lstrip()):
            new_lines.append(f"{key}={safe_value}\n")
            found = True
        else:
            new_lines.append(line if line.endswith("\n") else line + "\n")

    if not found:
        new_lines.append(f"{key}={safe_value}\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(new_lines), encoding="utf-8")


def read_env_value(key: str, env_path: str = ".env") -> str | None:
    """Read a specific key from a .env file.  Returns None if not found."""
    path = Path(env_path)
    if not path.exists():
        return None

    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*(.*)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = pattern.match(stripped)
        if m:
            val = m.group(1).strip()
            # Remove surrounding quotes
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            return val
    return None
