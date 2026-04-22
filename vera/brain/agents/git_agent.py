"""Git Agent — version control, code review, and CI integration."""

from __future__ import annotations

import logging
import subprocess
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


def _run_git(args: list[str], cwd: str | None = None) -> dict[str, Any]:
    """Run a git command and return the result."""
    try:
        result = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=30,
            cwd=cwd or ".",
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "output": result.stdout[:3000],
            "error": result.stderr[:500] if result.returncode != 0 else "",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


class GitStatusTool(Tool):
    def __init__(self):
        super().__init__(
            name="git_status",
            description="Show git status — modified, staged, untracked files",
            parameters={"repo_path": {"type": "str", "description": "Repository path (default: current dir)"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return _run_git(["status", "--short"], cwd=kwargs.get("repo_path"))


class GitDiffTool(Tool):
    def __init__(self):
        super().__init__(
            name="git_diff",
            description="Show git diff — changes in working directory or staged",
            parameters={
                "repo_path": {"type": "str", "description": "Repository path"},
                "staged": {"type": "bool", "description": "Show staged changes (default: false)"},
                "file": {"type": "str", "description": "Specific file to diff (optional)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        args = ["diff"]
        if kwargs.get("staged"):
            args.append("--staged")
        if kwargs.get("file"):
            args.append(kwargs["file"])
        return _run_git(args, cwd=kwargs.get("repo_path"))


class GitCommitTool(Tool):
    def __init__(self):
        super().__init__(
            name="git_commit",
            description="Stage and commit changes with a message",
            parameters={
                "message": {"type": "str", "description": "Commit message"},
                "repo_path": {"type": "str", "description": "Repository path"},
                "all": {"type": "bool", "description": "Stage all changes before commit (default: true)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        message = kwargs.get("message", "")
        if not message:
            return {"status": "error", "message": "Commit message required"}

        repo = kwargs.get("repo_path")
        if kwargs.get("all", True):
            _run_git(["add", "-A"], cwd=repo)

        return _run_git(["commit", "-m", message], cwd=repo)


class GitPushTool(Tool):
    def __init__(self):
        super().__init__(
            name="git_push",
            description="Push commits to remote",
            parameters={
                "repo_path": {"type": "str", "description": "Repository path"},
                "remote": {"type": "str", "description": "Remote name (default: origin)"},
                "branch": {"type": "str", "description": "Branch name (default: current)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        remote = kwargs.get("remote", "origin")
        branch = kwargs.get("branch", "")
        args = ["push", remote]
        if branch:
            args.append(branch)
        return _run_git(args, cwd=kwargs.get("repo_path"))


class GitPullTool(Tool):
    def __init__(self):
        super().__init__(
            name="git_pull",
            description="Pull latest changes from remote",
            parameters={
                "repo_path": {"type": "str", "description": "Repository path"},
                "remote": {"type": "str", "description": "Remote name (default: origin)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        return _run_git(["pull", kwargs.get("remote", "origin")], cwd=kwargs.get("repo_path"))


class GitBranchTool(Tool):
    def __init__(self):
        super().__init__(
            name="git_branch",
            description="List, create, or switch branches",
            parameters={
                "action": {"type": "str", "description": "list, create, switch, delete"},
                "name": {"type": "str", "description": "Branch name (for create/switch/delete)"},
                "repo_path": {"type": "str", "description": "Repository path"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "list")
        name = kwargs.get("name", "")
        repo = kwargs.get("repo_path")

        if action == "list":
            return _run_git(["branch", "-a"], cwd=repo)
        elif action == "create":
            if not name:
                return {"status": "error", "message": "Branch name required"}
            return _run_git(["checkout", "-b", name], cwd=repo)
        elif action == "switch":
            if not name:
                return {"status": "error", "message": "Branch name required"}
            return _run_git(["checkout", name], cwd=repo)
        elif action == "delete":
            return _run_git(["branch", "-d", name], cwd=repo)
        return {"status": "error", "message": f"Unknown action: {action}"}


class GitLogTool(Tool):
    def __init__(self):
        super().__init__(
            name="git_log",
            description="Show recent commit history",
            parameters={
                "repo_path": {"type": "str", "description": "Repository path"},
                "count": {"type": "int", "description": "Number of commits to show (default: 10)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        count = kwargs.get("count", 10)
        return _run_git(
            ["log", "--oneline", f"-{count}", "--graph", "--decorate"],
            cwd=kwargs.get("repo_path"),
        )


class CodeReviewTool(Tool):
    """Review code changes using LLM analysis."""

    def __init__(self):
        super().__init__(
            name="code_review",
            description="AI-powered code review of staged or recent changes",
            parameters={
                "repo_path": {"type": "str", "description": "Repository path"},
                "scope": {"type": "str", "description": "staged, last_commit, or branch_name"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        scope = kwargs.get("scope", "staged")
        repo = kwargs.get("repo_path")

        if scope == "staged":
            diff_result = _run_git(["diff", "--staged"], cwd=repo)
        elif scope == "last_commit":
            diff_result = _run_git(["diff", "HEAD~1"], cwd=repo)
        else:
            diff_result = _run_git(["diff", f"main...{scope}"], cwd=repo)

        if diff_result.get("status") != "success" or not diff_result.get("output"):
            return {"status": "error", "message": "No changes to review"}

        diff_text = diff_result["output"][:5000]

        try:
            from vera.providers.manager import ProviderManager
            from vera.providers.models import ModelTier

            provider = ProviderManager()
            result = await provider.complete(
                messages=[
                    {"role": "system", "content": (
                        "You are an expert code reviewer. Review the following diff and provide:\n"
                        "1. Summary of changes\n"
                        "2. Potential bugs or issues\n"
                        "3. Security concerns\n"
                        "4. Style/quality suggestions\n"
                        "5. Overall assessment (approve/request changes)\n"
                        "Be concise but thorough."
                    )},
                    {"role": "user", "content": f"Review this diff:\n\n```diff\n{diff_text}\n```"},
                ],
                tier=ModelTier.SPECIALIST,
            )
            return {"status": "success", "review": result.content, "diff_lines": len(diff_text.splitlines())}
        except Exception as e:
            return {"status": "error", "message": f"Review failed: {e}"}


class GitCreatePRTool(Tool):
    """Create a pull request via gh CLI or GitHub REST API fallback."""

    def __init__(self):
        super().__init__(
            name="git_create_pr",
            description="Create a GitHub pull request for the current branch",
            parameters={
                "title": {"type": "str", "description": "PR title"},
                "body": {"type": "str", "description": "PR description/body"},
                "base_branch": {"type": "str", "description": "Base branch to merge into (default: main)"},
                "head_branch": {"type": "str", "description": "Head branch (default: current branch)"},
                "reviewers": {"type": "str", "description": "Comma-separated reviewer usernames"},
                "labels": {"type": "str", "description": "Comma-separated label names"},
                "draft": {"type": "bool", "description": "Create as draft PR (default: false)"},
                "repo_path": {"type": "str", "description": "Repository path"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        import os

        title = kwargs.get("title", "")
        if not title:
            return {"status": "error", "message": "PR title is required"}

        body = kwargs.get("body", "")
        base = kwargs.get("base_branch", "main")
        head = kwargs.get("head_branch", "")
        reviewers = kwargs.get("reviewers", "")
        labels = kwargs.get("labels", "")
        draft = kwargs.get("draft", False)
        repo = kwargs.get("repo_path")

        # Try gh CLI first
        gh_args = ["gh", "pr", "create", "--title", title, "--body", body or "Created by eVera", "--base", base]
        if head:
            gh_args.extend(["--head", head])
        if reviewers:
            gh_args.extend(["--reviewer", reviewers])
        if labels:
            gh_args.extend(["--label", labels])
        if draft:
            gh_args.append("--draft")

        try:
            result = subprocess.run(
                gh_args, capture_output=True, text=True, timeout=30, cwd=repo or ".",
            )
            if result.returncode == 0:
                pr_url = result.stdout.strip()
                return {"status": "success", "method": "gh_cli", "pr_url": pr_url}
            logger.info("gh CLI failed (%s), trying REST API fallback", result.stderr[:200])
        except FileNotFoundError:
            logger.info("gh CLI not found, trying REST API fallback")
        except Exception as e:
            logger.info("gh CLI error: %s, trying REST API fallback", e)

        # Fallback: GitHub REST API
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            return {"status": "error", "message": "gh CLI not available and GITHUB_TOKEN not set. Install gh CLI or set GITHUB_TOKEN."}

        # Extract owner/repo from git remote
        remote_result = _run_git(["remote", "get-url", "origin"], cwd=repo)
        if remote_result.get("status") != "success":
            return {"status": "error", "message": "Could not determine remote URL"}

        remote_url = remote_result["output"].strip()
        # Parse owner/repo from HTTPS or SSH URL
        import re as re_mod
        match = re_mod.search(r"[:/]([^/]+)/([^/.]+?)(?:\.git)?$", remote_url)
        if not match:
            return {"status": "error", "message": f"Could not parse owner/repo from: {remote_url}"}

        owner, repo_name = match.group(1), match.group(2)

        if not head:
            branch_result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
            head = branch_result.get("output", "").strip() if branch_result.get("status") == "success" else ""

        if not head:
            return {"status": "error", "message": "Could not determine current branch"}

        payload = {"title": title, "body": body or "Created by eVera", "head": head, "base": base, "draft": draft}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"https://api.github.com/repos/{owner}/{repo_name}/pulls",
                    headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                    json=payload,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    return {"status": "success", "method": "github_api", "pr_url": data.get("html_url", ""), "pr_number": data.get("number")}
                return {"status": "error", "message": f"GitHub API error {resp.status_code}: {resp.text[:300]}"}
        except Exception as e:
            return {"status": "error", "message": f"GitHub API request failed: {e}"}


class GitStashTool(Tool):
    def __init__(self):
        super().__init__(
            name="git_stash",
            description="Stash or pop uncommitted changes",
            parameters={
                "action": {"type": "str", "description": "save, pop, list, drop"},
                "message": {"type": "str", "description": "Stash message (for save)"},
                "repo_path": {"type": "str", "description": "Repository path"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "save")
        repo = kwargs.get("repo_path")

        if action == "save":
            msg = kwargs.get("message", "")
            args = ["stash", "push"]
            if msg:
                args.extend(["-m", msg])
            return _run_git(args, cwd=repo)
        elif action == "pop":
            return _run_git(["stash", "pop"], cwd=repo)
        elif action == "list":
            return _run_git(["stash", "list"], cwd=repo)
        elif action == "drop":
            return _run_git(["stash", "drop"], cwd=repo)
        return {"status": "error", "message": f"Unknown stash action: {action}"}


class GitAgent(BaseAgent):
    """Git version control, code review, and repository management."""

    name = "git"
    description = "Git version control, code review, commit, push, branch management"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a Git and code review assistant. You can check status, view diffs, "
        "commit changes, push to remotes, manage branches, review code, and manage stashes. "
        "When the user wants to commit, always show the status/diff first. "
        "For code review, analyze the diff for bugs, security issues, and quality. "
        "Always confirm before pushing to remote."
    )

    offline_responses = {
        "git": "📦 I can help with Git! What do you need?",
        "commit": "💾 Let me help you commit! What's the message?",
        "push": "🚀 I'll push your changes!",
        "pull": "⬇️ Pulling latest changes!",
        "branch": "🌿 Branch management ready!",
        "review": "🔍 I'll review your code!",
        "diff": "📝 Let me show you the diff!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            GitStatusTool(),
            GitDiffTool(),
            GitCommitTool(),
            GitPushTool(),
            GitPullTool(),
            GitBranchTool(),
            GitLogTool(),
            CodeReviewTool(),
            GitStashTool(),
            GitCreatePRTool(),
        ]
