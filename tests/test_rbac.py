"""Tests for RBAC — users, roles, permissions, audit."""

from __future__ import annotations

import pytest


@pytest.fixture
def rbac_manager(tmp_path):
    import vera.rbac as rbac_mod
    from vera.rbac import RBACManager

    rbac_mod.RBAC_DIR = tmp_path / "rbac"
    return RBACManager()


class TestRBAC:
    def test_create_user(self, rbac_manager):
        result = rbac_manager.create_user("alice", "password123", role="admin")
        assert result["status"] == "success"
        assert result["username"] == "alice"
        assert result["api_key"].startswith("vera_")

    def test_duplicate_user(self, rbac_manager):
        rbac_manager.create_user("alice", "pass1")
        result = rbac_manager.create_user("alice", "pass2")
        assert result["status"] == "error"

    def test_authenticate(self, rbac_manager):
        rbac_manager.create_user("bob", "secret")
        result = rbac_manager.authenticate("bob", "secret")
        assert result is not None
        assert result["username"] == "bob"

    def test_wrong_password(self, rbac_manager):
        rbac_manager.create_user("bob", "secret")
        result = rbac_manager.authenticate("bob", "wrong")
        assert result is None

    def test_api_key_auth(self, rbac_manager):
        create_result = rbac_manager.create_user("carol", "pass")
        api_key = create_result["api_key"]
        result = rbac_manager.authenticate_api_key(api_key)
        assert result is not None
        assert result["username"] == "carol"

    def test_admin_permissions(self, rbac_manager):
        rbac_manager.create_user("admin1", "pass", role="admin")
        assert rbac_manager.check_permission("admin1", "operator", "execute_script") is True
        assert rbac_manager.check_permission("admin1", "income", "alpaca_trade") is True

    def test_viewer_restricted(self, rbac_manager):
        rbac_manager.create_user("viewer1", "pass", role="viewer")
        assert rbac_manager.check_permission("viewer1", "companion", "chat") is True
        assert rbac_manager.check_permission("viewer1", "operator", "execute_script") is False

    def test_disable_user(self, rbac_manager):
        rbac_manager.create_user("dave", "pass")
        rbac_manager.disable_user("dave")
        assert rbac_manager.authenticate("dave", "pass") is None

    def test_audit_log(self, rbac_manager):
        rbac_manager.create_user("eve", "pass")
        log = rbac_manager.get_audit_log()
        assert len(log) >= 1
        assert log[-1]["action"] == "user_created"

    def test_list_users(self, rbac_manager):
        rbac_manager.create_user("user1", "p1")
        rbac_manager.create_user("user2", "p2")
        users = rbac_manager.list_users()
        assert len(users) == 2

    def test_update_role(self, rbac_manager):
        rbac_manager.create_user("frank", "pass", role="user")
        rbac_manager.update_role("frank", "admin")
        assert rbac_manager.check_permission("frank", "operator", "execute_script") is True
