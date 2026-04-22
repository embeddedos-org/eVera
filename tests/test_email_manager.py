"""Tests for email_manager — IMAP/SMTP email tools."""

from __future__ import annotations

import email
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

import pytest

from vera.brain.agents.email_manager import (
    ReadEmailTool,
    ReadInboxTool,
    ReplyEmailTool,
    SearchEmailsTool,
    _get_imap_connection,
    _parse_email,
)


class TestGetImapConnection:
    """Tests for _get_imap_connection()."""

    def test_no_env_vars_returns_none(self):
        with patch.dict("os.environ", {}, clear=True):
            conn, err = _get_imap_connection()
            assert conn is None
            assert "IMAP not configured" in err

    def test_host_but_no_user_returns_none(self):
        with patch.dict("os.environ", {"VERA_IMAP_HOST": "imap.test.com"}, clear=True):
            conn, err = _get_imap_connection()
            assert conn is None
            assert "IMAP not configured" in err

    def test_successful_connection(self):
        mock_conn = MagicMock()
        with patch.dict(
            "os.environ",
            {
                "VERA_IMAP_HOST": "imap.test.com",
                "VERA_IMAP_USER": "user@test.com",
                "VERA_IMAP_PASS": "password123",
            },
            clear=True,
        ):
            with patch("vera.brain.agents.email_manager.imaplib.IMAP4_SSL", return_value=mock_conn):
                conn, err = _get_imap_connection()
                assert conn is mock_conn
                assert err is None
                mock_conn.login.assert_called_once_with("user@test.com", "password123")

    def test_connection_failure(self):
        with patch.dict(
            "os.environ",
            {
                "VERA_IMAP_HOST": "imap.test.com",
                "VERA_IMAP_USER": "user@test.com",
                "VERA_IMAP_PASS": "wrong",
            },
            clear=True,
        ):
            with patch(
                "vera.brain.agents.email_manager.imaplib.IMAP4_SSL", side_effect=Exception("Connection refused")
            ):
                conn, err = _get_imap_connection()
                assert conn is None
                assert "IMAP connection failed" in err

    def test_falls_back_to_smtp_user(self):
        mock_conn = MagicMock()
        with patch.dict(
            "os.environ",
            {
                "VERA_IMAP_HOST": "imap.test.com",
                "VERA_SMTP_USER": "smtp_user@test.com",
                "VERA_SMTP_PASS": "smtp_pass",
            },
            clear=True,
        ):
            with patch("vera.brain.agents.email_manager.imaplib.IMAP4_SSL", return_value=mock_conn):
                conn, err = _get_imap_connection()
                assert conn is mock_conn
                assert err is None
                mock_conn.login.assert_called_once_with("smtp_user@test.com", "smtp_pass")


class TestParseEmail:
    """Tests for _parse_email()."""

    def test_simple_email(self):
        msg = MIMEText("Hello, this is a test email body.")
        msg["From"] = "Sender Name <sender@example.com>"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Test Subject"
        msg["Date"] = "Mon, 1 Jan 2024 10:00:00 +0000"
        msg["Message-ID"] = "<test123@example.com>"

        parsed = _parse_email(msg.as_bytes())

        assert parsed["from"] == "sender@example.com"
        assert parsed["from_name"] == "Sender Name"
        assert parsed["to"] == "recipient@example.com"
        assert parsed["subject"] == "Test Subject"
        assert "test email body" in parsed["body"]
        assert parsed["message_id"] == "<test123@example.com>"

    def test_simple_email_bare_address(self):
        """When From is just 'user@example.com' without angle brackets."""
        msg = MIMEText("Body text here")
        msg["From"] = "sender@example.com"
        msg["Subject"] = "Bare Address"

        parsed = _parse_email(msg.as_bytes())
        # The regex puts bare addresses in from_name, from is empty
        assert parsed["from_name"] == "sender@example.com"
        assert parsed["subject"] == "Bare Address"

    def test_multipart_email(self):
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = '"John Doe" <john@example.com>'
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Multipart Test"

        text_part = MIMEText("Plain text body content", "plain")
        html_part = MIMEText("<html><body>HTML content</body></html>", "html")
        msg.attach(text_part)
        msg.attach(html_part)

        parsed = _parse_email(msg.as_bytes())

        assert parsed["from"] == "john@example.com"
        assert parsed["from_name"] == "John Doe"
        assert "Plain text body" in parsed["body"]
        assert parsed["subject"] == "Multipart Test"

    def test_email_with_no_subject(self):
        msg = MIMEText("Body text")
        msg["From"] = "sender@example.com"
        # No Subject header set

        parsed = _parse_email(msg.as_bytes())
        assert parsed["subject"] == "(no subject)"

    def test_body_truncated_to_2000(self):
        long_body = "x" * 5000
        msg = MIMEText(long_body)
        msg["From"] = "sender@example.com"

        parsed = _parse_email(msg.as_bytes())
        assert len(parsed["body"]) <= 2000


class TestReadInboxTool:
    """Tests for ReadInboxTool.execute()."""

    @pytest.mark.asyncio
    async def test_no_imap_config_returns_error(self):
        tool = ReadInboxTool()
        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(None, "IMAP not configured")):
            result = await tool.execute()
            assert result["status"] == "error"
            assert "IMAP not configured" in result["message"]

    @pytest.mark.asyncio
    async def test_empty_inbox(self):
        tool = ReadInboxTool()
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])
        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(mock_conn, None)):
            result = await tool.execute()
            assert result["status"] == "success"
            assert result["count"] == 0
            assert result["emails"] == []

    @pytest.mark.asyncio
    async def test_reads_emails_successfully(self):
        tool = ReadInboxTool()
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2"])

        msg = MIMEText("Hello from inbox")
        msg["From"] = "sender@test.com"
        msg["Subject"] = "Test"
        msg["Date"] = "Mon, 1 Jan 2024 10:00:00 +0000"

        mock_conn.fetch.return_value = ("OK", [(b"1", msg.as_bytes())])

        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(mock_conn, None)):
            result = await tool.execute(count=5)
            assert result["status"] == "success"
            assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_count_capped_at_30(self):
        tool = ReadInboxTool()
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])
        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(mock_conn, None)):
            result = await tool.execute(count=100)
            # No crash — count was capped internally
            assert result["status"] == "success"


class TestReadEmailTool:
    """Tests for ReadEmailTool.execute()."""

    @pytest.mark.asyncio
    async def test_no_email_id_returns_error(self):
        tool = ReadEmailTool()
        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(MagicMock(), None)):
            result = await tool.execute()
            assert result["status"] == "error"
            assert "No email_id" in result["message"]

    @pytest.mark.asyncio
    async def test_no_imap_config_returns_error(self):
        tool = ReadEmailTool()
        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(None, "IMAP not configured")):
            result = await tool.execute(email_id="123")
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_reads_specific_email(self):
        tool = ReadEmailTool()
        mock_conn = MagicMock()

        msg = MIMEText("Full email body here")
        msg["From"] = "sender@test.com"
        msg["Subject"] = "Specific Email"

        mock_conn.fetch.return_value = ("OK", [(b"5", msg.as_bytes())])

        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(mock_conn, None)):
            result = await tool.execute(email_id="5")
            assert result["status"] == "success"
            assert result["email"]["subject"] == "Specific Email"
            assert result["email"]["id"] == "5"

    @pytest.mark.asyncio
    async def test_email_not_found(self):
        tool = ReadEmailTool()
        mock_conn = MagicMock()
        mock_conn.fetch.return_value = ("OK", [None])

        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(mock_conn, None)):
            result = await tool.execute(email_id="999")
            assert result["status"] == "error"
            assert "not found" in result["message"]


class TestReplyEmailTool:
    """Tests for ReplyEmailTool.execute()."""

    @pytest.mark.asyncio
    async def test_missing_email_id_and_body(self):
        tool = ReplyEmailTool()
        result = await tool.execute()
        assert result["status"] == "error"
        assert "required" in result["message"]

    @pytest.mark.asyncio
    async def test_missing_body_only(self):
        tool = ReplyEmailTool()
        result = await tool.execute(email_id="1")
        assert result["status"] == "error"
        assert "required" in result["message"]

    @pytest.mark.asyncio
    async def test_no_imap_returns_error(self):
        tool = ReplyEmailTool()
        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(None, "IMAP not configured")):
            result = await tool.execute(email_id="1", body="Thanks!")
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_no_smtp_config_returns_error(self):
        tool = ReplyEmailTool()

        # Mock IMAP to succeed
        mock_conn = MagicMock()
        msg = MIMEText("Original email body")
        msg["From"] = "sender@test.com"
        msg["Subject"] = "Original"
        msg["Message-ID"] = "<orig@test.com>"
        msg["Date"] = "Mon, 1 Jan 2024 10:00:00 +0000"
        mock_conn.fetch.return_value = ("OK", [(b"1", msg.as_bytes())])

        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(mock_conn, None)):
            with patch.dict("os.environ", {}, clear=True):
                result = await tool.execute(email_id="1", body="Thanks!")
                assert result["status"] == "error"
                assert "SMTP not configured" in result["message"]


class TestSearchEmailsTool:
    """Tests for SearchEmailsTool.execute()."""

    @pytest.mark.asyncio
    async def test_no_imap_returns_error(self):
        tool = SearchEmailsTool()
        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(None, "IMAP not configured")):
            result = await tool.execute(query="test")
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_search_by_query(self):
        tool = SearchEmailsTool()
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1"])

        msg = MIMEText("Found result body")
        msg["From"] = "found@test.com"
        msg["Subject"] = "Search Result"

        mock_conn.fetch.return_value = ("OK", [(b"1", msg.as_bytes())])

        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(mock_conn, None)):
            result = await tool.execute(query="test search")
            assert result["status"] == "success"
            assert result["count"] >= 1

    @pytest.mark.asyncio
    async def test_search_by_from_addr(self):
        tool = SearchEmailsTool()
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])

        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(mock_conn, None)):
            result = await tool.execute(from_addr="boss@company.com")
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_search_by_subject(self):
        tool = SearchEmailsTool()
        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])

        with patch("vera.brain.agents.email_manager._get_imap_connection", return_value=(mock_conn, None)):
            result = await tool.execute(subject="Invoice")
            assert result["status"] == "success"
