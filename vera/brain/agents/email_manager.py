"""Email Manager — full IMAP/SMTP email management for eVera.

@file vera/brain/agents/email_manager.py
@brief Read inbox, search, reply, categorize emails via IMAP + SMTP.

Provides read-only inbox access and AI-powered reply drafting.
Requires VERA_IMAP_* and VERA_SMTP_* env vars configured.
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from vera.brain.agents.base import Tool

logger = logging.getLogger(__name__)


def _get_imap_connection():
    host = os.getenv("VERA_IMAP_HOST", "")
    port = int(os.getenv("VERA_IMAP_PORT", "993"))
    user = os.getenv("VERA_IMAP_USER", "") or os.getenv("VERA_SMTP_USER", "")
    pwd = os.getenv("VERA_IMAP_PASS", "") or os.getenv("VERA_SMTP_PASS", "")

    if not host or not user:
        return None, "IMAP not configured. Set VERA_IMAP_HOST, VERA_IMAP_USER, VERA_IMAP_PASS in .env"

    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, pwd)
        return conn, None
    except Exception as e:
        return None, f"IMAP connection failed: {e}"


def _parse_email(raw_msg: bytes) -> dict[str, Any]:
    msg = email.message_from_bytes(raw_msg)

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="replace")

    from_header = msg.get("From", "")
    # Extract name and email
    match = re.match(r'"?([^"<]*)"?\s*<?([^>]*)>?', from_header)
    from_name = match.group(1).strip() if match else ""
    from_email = match.group(2).strip() if match else from_header

    return {
        "from": from_email,
        "from_name": from_name,
        "to": msg.get("To", ""),
        "subject": msg.get("Subject", "(no subject)"),
        "date": msg.get("Date", ""),
        "body": body[:2000],
        "message_id": msg.get("Message-ID", ""),
    }


class ReadInboxTool(Tool):
    """Read recent emails from the inbox."""

    def __init__(self) -> None:
        super().__init__(
            name="read_inbox",
            description="Read recent emails from inbox. Returns subject, from, date for each.",
            parameters={
                "count": {"type": "int", "description": "Number of emails to fetch (default: 10, max: 30)"},
                "folder": {"type": "str", "description": "Mailbox folder (default: INBOX)"},
                "unread_only": {"type": "str", "description": "Only unread emails (true/false, default: false)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        count = min(int(kwargs.get("count", 10)), 30)
        folder = kwargs.get("folder", "INBOX")
        unread_only = str(kwargs.get("unread_only", "false")).lower() == "true"

        conn, err = _get_imap_connection()
        if err:
            return {"status": "error", "message": err}

        try:
            conn.select(folder, readonly=True)
            criteria = "UNSEEN" if unread_only else "ALL"
            _, msg_ids = conn.search(None, criteria)
            ids = msg_ids[0].split()

            if not ids:
                return {"status": "success", "emails": [], "count": 0, "message": "No emails found"}

            recent_ids = ids[-count:]
            emails = []

            for mid in reversed(recent_ids):
                _, data = conn.fetch(mid, "(RFC822)")
                if data and data[0]:
                    parsed = _parse_email(data[0][1])
                    parsed["id"] = mid.decode()
                    parsed["body"] = parsed["body"][:200] + "..." if len(parsed["body"]) > 200 else parsed["body"]
                    emails.append(parsed)

            conn.logout()
            return {"status": "success", "emails": emails, "count": len(emails)}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            try:
                conn.logout()
            except Exception:
                pass


class ReadEmailTool(Tool):
    """Read the full content of a specific email."""

    def __init__(self) -> None:
        super().__init__(
            name="read_email",
            description="Read the full body of a specific email by its ID",
            parameters={
                "email_id": {"type": "str", "description": "Email ID from read_inbox results"},
                "folder": {"type": "str", "description": "Mailbox folder (default: INBOX)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        email_id = kwargs.get("email_id", "")
        folder = kwargs.get("folder", "INBOX")

        if not email_id:
            return {"status": "error", "message": "No email_id provided"}

        conn, err = _get_imap_connection()
        if err:
            return {"status": "error", "message": err}

        try:
            conn.select(folder, readonly=True)
            _, data = conn.fetch(email_id.encode(), "(RFC822)")
            if data and data[0]:
                parsed = _parse_email(data[0][1])
                parsed["id"] = email_id
                conn.logout()
                return {"status": "success", "email": parsed}
            conn.logout()
            return {"status": "error", "message": f"Email {email_id} not found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            try:
                conn.logout()
            except Exception:
                pass


class ReplyEmailTool(Tool):
    """Reply to an email."""

    def __init__(self) -> None:
        super().__init__(
            name="reply_email",
            description="Reply to an email with AI-drafted or custom content",
            parameters={
                "email_id": {"type": "str", "description": "Email ID to reply to"},
                "body": {"type": "str", "description": "Reply body content"},
                "folder": {"type": "str", "description": "Mailbox folder (default: INBOX)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        email_id = kwargs.get("email_id", "")
        body = kwargs.get("body", "")
        folder = kwargs.get("folder", "INBOX")

        if not email_id or not body:
            return {"status": "error", "message": "Both email_id and body are required"}

        # First read the original email
        conn, err = _get_imap_connection()
        if err:
            return {"status": "error", "message": err}

        try:
            conn.select(folder, readonly=True)
            _, data = conn.fetch(email_id.encode(), "(RFC822)")
            if not data or not data[0]:
                return {"status": "error", "message": f"Email {email_id} not found"}

            original = _parse_email(data[0][1])
            conn.logout()
        except Exception as e:
            return {"status": "error", "message": f"Failed to read original: {e}"}

        # Send reply via SMTP
        smtp_host = os.getenv("VERA_SMTP_HOST", "")
        smtp_port = int(os.getenv("VERA_SMTP_PORT", "587"))
        smtp_user = os.getenv("VERA_SMTP_USER", "")
        smtp_pass = os.getenv("VERA_SMTP_PASS", "")

        if not smtp_host or not smtp_user:
            return {
                "status": "error",
                "message": "SMTP not configured. Set VERA_SMTP_HOST, VERA_SMTP_USER, VERA_SMTP_PASS",
            }

        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = original["from"]
            msg["Subject"] = f"Re: {original['subject']}"
            msg["In-Reply-To"] = original.get("message_id", "")
            msg["References"] = original.get("message_id", "")

            reply_body = f"{body}\n\n--- Original Message ---\nFrom: {original['from']}\nDate: {original['date']}\nSubject: {original['subject']}\n\n{original['body'][:500]}"
            msg.attach(MIMEText(reply_body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            return {"status": "success", "replied_to": original["from"], "subject": msg["Subject"]}
        except Exception as e:
            return {"status": "error", "message": f"Failed to send reply: {e}"}


class SearchEmailsTool(Tool):
    """Search emails by keyword, sender, or date."""

    def __init__(self) -> None:
        super().__init__(
            name="search_emails",
            description="Search emails by keyword, sender, or subject",
            parameters={
                "query": {"type": "str", "description": "Search keyword"},
                "from_addr": {"type": "str", "description": "Filter by sender email"},
                "subject": {"type": "str", "description": "Filter by subject"},
                "count": {"type": "int", "description": "Max results (default: 10)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query = kwargs.get("query", "")
        from_addr = kwargs.get("from_addr", "")
        subject_filter = kwargs.get("subject", "")
        count = min(int(kwargs.get("count", 10)), 30)

        conn, err = _get_imap_connection()
        if err:
            return {"status": "error", "message": err}

        try:
            conn.select("INBOX", readonly=True)

            criteria_parts = []
            if from_addr:
                criteria_parts.append(f'FROM "{from_addr}"')
            if subject_filter:
                criteria_parts.append(f'SUBJECT "{subject_filter}"')
            if query and not from_addr and not subject_filter:
                criteria_parts.append(f'TEXT "{query}"')

            criteria = " ".join(criteria_parts) if criteria_parts else "ALL"
            _, msg_ids = conn.search(None, criteria)
            ids = msg_ids[0].split()

            recent_ids = ids[-count:]
            emails = []

            for mid in reversed(recent_ids):
                _, data = conn.fetch(mid, "(RFC822)")
                if data and data[0]:
                    parsed = _parse_email(data[0][1])
                    parsed["id"] = mid.decode()
                    parsed["body"] = parsed["body"][:150] + "..."
                    emails.append(parsed)

            conn.logout()
            return {"status": "success", "emails": emails, "count": len(emails), "query": query}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            try:
                conn.logout()
            except Exception:
                pass
