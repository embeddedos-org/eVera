"""Tests for shared env_writer utility."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


class TestUpdateEnvFile:
    def test_create_new_file(self, tmp_path):
        env_path = tmp_path / ".env"
        from vera.utils.env_writer import update_env_file
        update_env_file("MY_KEY", "my_value", str(env_path))
        assert env_path.exists()
        assert "MY_KEY=my_value" in env_path.read_text()

    def test_update_existing_key(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("MY_KEY=old_value\nOTHER=keep\n")
        from vera.utils.env_writer import update_env_file
        update_env_file("MY_KEY", "new_value", str(env_path))
        content = env_path.read_text()
        assert "MY_KEY=new_value" in content
        assert "old_value" not in content
        assert "OTHER=keep" in content

    def test_preserve_comments(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("# This is a comment\nKEY=value\n")
        from vera.utils.env_writer import update_env_file
        update_env_file("NEW_KEY", "new_val", str(env_path))
        content = env_path.read_text()
        assert "# This is a comment" in content
        assert "KEY=value" in content
        assert "NEW_KEY=new_val" in content

    def test_quote_value_with_spaces(self, tmp_path):
        env_path = tmp_path / ".env"
        from vera.utils.env_writer import update_env_file
        update_env_file("MY_KEY", "hello world", str(env_path))
        content = env_path.read_text()
        assert '"hello world"' in content

    def test_quote_value_with_hash(self, tmp_path):
        env_path = tmp_path / ".env"
        from vera.utils.env_writer import update_env_file
        update_env_file("URL", "http://example.com#anchor", str(env_path))
        content = env_path.read_text()
        assert '"http://example.com#anchor"' in content


class TestReadEnvValue:
    def test_read_existing_key(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("MY_KEY=hello\n")
        from vera.utils.env_writer import read_env_value
        assert read_env_value("MY_KEY", str(env_path)) == "hello"

    def test_read_missing_key(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("OTHER=value\n")
        from vera.utils.env_writer import read_env_value
        assert read_env_value("MY_KEY", str(env_path)) is None

    def test_read_nonexistent_file(self, tmp_path):
        from vera.utils.env_writer import read_env_value
        assert read_env_value("MY_KEY", str(tmp_path / "nope.env")) is None

    def test_read_quoted_value(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text('MY_KEY="hello world"\n')
        from vera.utils.env_writer import read_env_value
        assert read_env_value("MY_KEY", str(env_path)) == "hello world"

    def test_skip_comments(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("# MY_KEY=not_this\nMY_KEY=this_one\n")
        from vera.utils.env_writer import read_env_value
        assert read_env_value("MY_KEY", str(env_path)) == "this_one"
