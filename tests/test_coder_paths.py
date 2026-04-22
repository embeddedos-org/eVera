"""Tests for Feature 5: Coder agent path restrictions override."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_settings():
    """Reset safety settings between tests."""
    from config import settings
    original_unsafe = settings.safety.coder_unsafe_paths
    original_extra = list(settings.safety.coder_allowed_extra_paths)
    yield
    settings.safety.coder_unsafe_paths = original_unsafe
    settings.safety.coder_allowed_extra_paths = original_extra


class TestIsPathSafe:
    def test_home_dir_allowed(self):
        from vera.brain.agents.coder import _is_path_safe
        safe, reason = _is_path_safe(Path.home() / "somefile.txt")
        assert safe is True
        assert reason == ""

    def test_blocked_path_rejected_by_default(self):
        from vera.brain.agents.coder import _is_path_safe
        safe, reason = _is_path_safe(Path.home() / ".ssh" / "id_rsa")
        assert safe is False
        assert ".ssh" in reason

    def test_blocked_path_allowed_with_unsafe_flag(self):
        from config import settings
        settings.safety.coder_unsafe_paths = True
        from vera.brain.agents.coder import _is_path_safe
        safe, reason = _is_path_safe(Path.home() / ".ssh" / "id_rsa")
        assert safe is True

    def test_outside_roots_rejected_by_default(self):
        from vera.brain.agents.coder import _is_path_safe
        safe, reason = _is_path_safe(Path("/nonexistent/random/path"))
        assert safe is False
        assert "outside allowed" in reason

    def test_outside_roots_allowed_with_unsafe_flag(self):
        from config import settings
        settings.safety.coder_unsafe_paths = True
        from vera.brain.agents.coder import _is_path_safe
        safe, reason = _is_path_safe(Path("/nonexistent/random/path"))
        assert safe is True

    def test_env_file_blocked_by_default(self):
        from vera.brain.agents.coder import _is_path_safe
        safe, reason = _is_path_safe(Path.home() / "project" / ".env")
        assert safe is False
        assert ".env" in reason

    def test_extra_paths_respected(self):
        from config import settings
        from vera.brain.agents.coder import ALLOWED_ROOTS
        test_path = Path("/opt/custom/project")
        was_present = test_path.resolve() in [r.resolve() for r in ALLOWED_ROOTS]
        if not was_present:
            ALLOWED_ROOTS.append(test_path.resolve())
        from vera.brain.agents.coder import _is_path_safe
        safe, _ = _is_path_safe(test_path / "file.py")
        assert safe is True
        if not was_present:
            ALLOWED_ROOTS.remove(test_path.resolve())
