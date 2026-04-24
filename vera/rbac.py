"""Enterprise RBAC — users, roles, permissions, audit logging.

Multi-user support with role-based access control.

Roles:
- admin: Full access, manage users, view audit logs
- user: Use all agents, manage own data
- viewer: Read-only, view responses but can't execute tools

Usage:
    rbac = RBACManager()
    rbac.create_user("alice", "password123", role="admin")
    rbac.create_user("bob", "secret", role="user")

    if rbac.check_permission(user_id, "operator", "execute_script"):
        # proceed
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RBAC_DIR = DATA_DIR / "rbac"


class Role:
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


# Default permissions per role
ROLE_PERMISSIONS = {
    Role.ADMIN: {
        "agents": "*",  # All agents
        "tools": "*",  # All tools
        "manage_users": True,
        "view_audit": True,
        "manage_workflows": True,
        "real_trading": True,
    },
    Role.USER: {
        "agents": "*",
        "tools": "*",
        "manage_users": False,
        "view_audit": False,
        "manage_workflows": True,
        "real_trading": False,  # Only paper trading by default
    },
    Role.VIEWER: {
        "agents": ["companion", "researcher"],
        "tools": ["chat", "web_search", "summarize_url"],
        "manage_users": False,
        "view_audit": False,
        "manage_workflows": False,
        "real_trading": False,
    },
}


def _hash_password(password: str, salt: str = "") -> tuple[str, str]:
    """Hash a password with salt."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return hashed.hex(), salt


class RBACManager:
    """Manages users, roles, and permissions."""

    def __init__(self) -> None:
        RBAC_DIR.mkdir(parents=True, exist_ok=True)
        self._users: dict[str, dict] = {}
        self._sessions: dict[str, str] = {}  # api_key → user_id
        self._load_users()

    def _load_users(self) -> None:
        users_file = RBAC_DIR / "users.json"
        if users_file.exists():
            try:
                self._users = json.loads(users_file.read_text())
            except Exception as e:
                logger.error("Failed to load users file: %s", e)
                self._users = {}

    def _save_users(self) -> None:
        (RBAC_DIR / "users.json").write_text(json.dumps(self._users, indent=2, default=str))

    def create_user(self, username: str, password: str, role: str = Role.USER) -> dict:
        """Create a new user."""
        if username in self._users:
            return {"status": "error", "message": f"User '{username}' already exists"}

        hashed, salt = _hash_password(password)
        api_key = f"vera_{secrets.token_urlsafe(32)}"

        self._users[username] = {
            "username": username,
            "password_hash": hashed,
            "salt": salt,
            "role": role,
            "api_key": api_key,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "enabled": True,
        }
        self._sessions[api_key] = username
        self._save_users()

        self._audit("user_created", username, {"role": role})
        return {"status": "success", "username": username, "api_key": api_key, "role": role}

    def authenticate(self, username: str, password: str) -> dict | None:
        """Authenticate a user and return their info."""
        user = self._users.get(username)
        if not user or not user.get("enabled"):
            return None

        hashed, _ = _hash_password(password, user["salt"])
        if hashed != user["password_hash"]:
            self._audit("login_failed", username, {})
            return None

        user["last_login"] = datetime.now().isoformat()
        self._save_users()
        self._audit("login_success", username, {})

        return {"username": username, "role": user["role"], "api_key": user["api_key"]}

    def authenticate_api_key(self, api_key: str) -> dict | None:
        """Authenticate via API key."""
        for username, user in self._users.items():
            if user.get("api_key") == api_key and user.get("enabled"):
                return {"username": username, "role": user["role"]}
        return None

    def check_permission(self, username: str, agent: str, tool: str = "") -> bool:
        """Check if a user has permission to use an agent/tool."""
        user = self._users.get(username)
        if not user or not user.get("enabled"):
            return False

        role = user["role"]
        perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS[Role.VIEWER])

        # Check agent permission
        allowed_agents = perms.get("agents", [])
        if allowed_agents != "*" and agent not in allowed_agents:
            self._audit("permission_denied", username, {"agent": agent, "tool": tool})
            return False

        # Check tool permission
        allowed_tools = perms.get("tools", [])
        if tool and allowed_tools != "*" and tool not in allowed_tools:
            self._audit("permission_denied", username, {"agent": agent, "tool": tool})
            return False

        return True

    def list_users(self) -> list[dict]:
        """List all users (without passwords)."""
        return [
            {
                "username": u["username"],
                "role": u["role"],
                "enabled": u["enabled"],
                "last_login": u["last_login"],
                "created_at": u["created_at"],
            }
            for u in self._users.values()
        ]

    def update_role(self, username: str, new_role: str) -> bool:
        if username in self._users and new_role in ROLE_PERMISSIONS:
            self._users[username]["role"] = new_role
            self._save_users()
            self._audit("role_changed", username, {"new_role": new_role})
            return True
        return False

    def disable_user(self, username: str) -> bool:
        if username in self._users:
            self._users[username]["enabled"] = False
            self._save_users()
            self._audit("user_disabled", username, {})
            return True
        return False

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        """Get recent audit log entries."""
        audit_file = RBAC_DIR / "audit.json"
        if not audit_file.exists():
            return []
        try:
            entries = json.loads(audit_file.read_text())
            return entries[-limit:]
        except Exception as e:
            logger.error("Failed to read audit log: %s", e)
            return []

    def _audit(self, action: str, username: str, details: dict) -> None:
        """Log an audit event."""
        audit_file = RBAC_DIR / "audit.json"
        entries = []
        if audit_file.exists():
            try:
                entries = json.loads(audit_file.read_text())
            except Exception as e:
                logger.error("Failed to parse audit log for append: %s", e)

        entries.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "username": username,
                "details": details,
            }
        )

        # Keep last 10000 entries
        entries = entries[-10000:]
        audit_file.write_text(json.dumps(entries, indent=2, default=str))
