"""AI-powered code analysis functions — summarize, explain, find issues.

@file vera/brain/agents/code_analysis.py
@brief Reusable async functions for AI code analysis via ProviderManager.

Used by the /api/code/analyze endpoint in app.py. Not a full agent —
just standalone functions that call the LLM with structured prompts.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


def compute_complexity(content: str, file_path: str = "") -> str:
    """Heuristic complexity rating based on LOC and nesting depth.

    @param content: Source code text.
    @param file_path: Optional file path (unused but kept for API symmetry).
    @return 'low', 'medium', or 'high'.
    """
    lines = content.splitlines()
    loc = len([l for l in lines if l.strip() and not l.strip().startswith("#")])

    max_indent = 0
    for line in lines:
        stripped = line.lstrip()
        if stripped:
            indent = len(line) - len(stripped)
            spaces = indent if line[0] == " " else indent * 4
            max_indent = max(max_indent, spaces // 4)

    if loc > 200 or max_indent > 4:
        return "high"
    if loc > 50:
        return "medium"
    return "low"


async def summarize_code(
    file_path: str,
    content: str,
    provider: Any,
) -> dict[str, Any]:
    """AI-powered code summary.

    @param file_path: Path to the file being analyzed.
    @param content: Source code content.
    @param provider: ProviderManager instance.
    @return Dict with summary, complexity, and key_concepts[].
    """
    from vera.brain.agents.codebase_indexer import _extract_definitions

    defs = _extract_definitions(Path(file_path))
    defs_text = ", ".join(d["name"] for d in defs[:20]) if defs else "none found"
    complexity = compute_complexity(content, file_path)

    result = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior code reviewer. Summarize the following source file concisely. "
                    "Return JSON with keys: summary (1-3 sentences), key_concepts (array of 3-6 short concept strings). "
                    "Only output valid JSON, no markdown fences."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"File: {file_path}\nSymbols: {defs_text}\nComplexity: {complexity}\n\n```\n{content[:6000]}\n```"
                ),
            },
        ],
        tier=ModelTier.SPECIALIST,
    )

    try:
        import json

        data = json.loads(result.content)
    except Exception:
        data = {"summary": result.content.strip(), "key_concepts": []}

    data["complexity"] = complexity
    return data


async def explain_code(
    file_path: str,
    content: str,
    provider: Any,
) -> dict[str, Any]:
    """AI-powered step-by-step code explanation.

    @param file_path: Path to the file being analyzed.
    @param content: Source code content.
    @param provider: ProviderManager instance.
    @return Dict with steps[] and key_line {number, explanation}.
    """
    result = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a code educator. Explain the following source file step by step. "
                    "Return JSON with keys: steps (array of explanation strings), "
                    "key_line (object with 'number' (int) and 'explanation' (string) for the most important line). "
                    "Only output valid JSON, no markdown fences."
                ),
            },
            {
                "role": "user",
                "content": f"File: {file_path}\n\n```\n{content[:6000]}\n```",
            },
        ],
        tier=ModelTier.SPECIALIST,
    )

    try:
        import json

        data = json.loads(result.content)
    except Exception:
        data = {"steps": [result.content.strip()], "key_line": {"number": 1, "explanation": ""}}

    return data


async def find_issues(
    file_path: str,
    content: str,
    provider: Any,
) -> dict[str, Any]:
    """AI-powered issue/bug detection.

    @param file_path: Path to the file being analyzed.
    @param content: Source code content.
    @param provider: ProviderManager instance.
    @return Dict with issues[] containing line, severity, description, suggestion.
    """
    result = await provider.complete(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior code auditor. Analyze the following file for bugs, code smells, "
                    "security issues, and improvements. Return JSON with key: issues (array of objects "
                    "with keys: line (int), severity ('low'|'medium'|'high'|'critical'), "
                    "description (string), suggestion (string)). "
                    'If no issues found, return {"issues": []}. '
                    "Only output valid JSON, no markdown fences."
                ),
            },
            {
                "role": "user",
                "content": f"File: {file_path}\n\n```\n{content[:6000]}\n```",
            },
        ],
        tier=ModelTier.SPECIALIST,
    )

    try:
        import json

        data = json.loads(result.content)
    except Exception:
        data = {"issues": []}

    return data
