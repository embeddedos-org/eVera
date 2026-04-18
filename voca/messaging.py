"""Messaging integrations — Slack, Discord, Telegram bots.

Voca can receive commands from and send proactive notifications to messaging apps.
Each integration runs as a webhook listener on the FastAPI server.

Setup:
- Slack: Create a Slack App, set VOCA_SLACK_BOT_TOKEN and VOCA_SLACK_SIGNING_SECRET
- Discord: Create a Discord Bot, set VOCA_DISCORD_BOT_TOKEN
- Telegram: Create via @BotFather, set VOCA_TELEGRAM_BOT_TOKEN
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# Config from env
SLACK_BOT_TOKEN = os.getenv("VOCA_SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET = os.getenv("VOCA_SLACK_SIGNING_SECRET", "")
DISCORD_BOT_TOKEN = os.getenv("VOCA_DISCORD_BOT_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.getenv("VOCA_TELEGRAM_BOT_TOKEN", "")


# ============================================================
# SLACK
# ============================================================

async def handle_slack_event(body: dict, headers: dict, brain: Any) -> dict:
    """Handle incoming Slack events (messages, slash commands)."""
    # URL verification challenge
    if body.get("type") == "url_verification":
        return {"challenge": body["challenge"]}

    # Verify request signature
    if SLACK_SIGNING_SECRET and not _verify_slack_signature(body, headers):
        return {"error": "Invalid signature"}

    event = body.get("event", {})
    event_type = event.get("type")

    if event_type == "message" and not event.get("bot_id"):
        text = event.get("text", "")
        channel = event.get("channel", "")
        user = event.get("user", "")

        if text.strip():
            result = await brain.process(text, session_id=f"slack-{user}")
            await _send_slack_message(channel, result.response)

            return {"status": "ok", "response": result.response}

    return {"status": "ok"}


async def _send_slack_message(channel: str, text: str) -> None:
    """Send a message to a Slack channel."""
    if not SLACK_BOT_TOKEN:
        return
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                json={"channel": channel, "text": text},
            )
    except Exception as e:
        logger.warning("Slack send failed: %s", e)


def _verify_slack_signature(body: dict, headers: dict) -> bool:
    """Verify Slack request signature."""
    timestamp = headers.get("x-slack-request-timestamp", "")
    signature = headers.get("x-slack-signature", "")

    if abs(time.time() - int(timestamp or 0)) > 300:
        return False

    sig_basestring = f"v0:{timestamp}:{json.dumps(body)}"
    my_sig = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(), sig_basestring.encode(), hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(my_sig, signature)


async def send_slack_notification(channel: str, message: str) -> bool:
    """Proactively send a notification to Slack."""
    if not SLACK_BOT_TOKEN:
        return False
    await _send_slack_message(channel, message)
    return True


# ============================================================
# DISCORD
# ============================================================

async def handle_discord_interaction(body: dict, brain: Any) -> dict:
    """Handle Discord interactions (slash commands, messages)."""
    interaction_type = body.get("type")

    # Ping verification
    if interaction_type == 1:
        return {"type": 1}

    # Slash command or message
    if interaction_type == 2:
        data = body.get("data", {})
        text = data.get("options", [{}])[0].get("value", "") if data.get("options") else data.get("name", "")
        user_id = body.get("member", {}).get("user", {}).get("id", "unknown")

        if text:
            result = await brain.process(text, session_id=f"discord-{user_id}")
            return {
                "type": 4,
                "data": {"content": result.response},
            }

    return {"type": 4, "data": {"content": "I didn't understand that."}}


async def send_discord_message(channel_id: str, message: str) -> bool:
    """Send a message to a Discord channel."""
    if not DISCORD_BOT_TOKEN:
        return False
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
                json={"content": message},
            )
        return True
    except Exception as e:
        logger.warning("Discord send failed: %s", e)
        return False


# ============================================================
# TELEGRAM
# ============================================================

async def handle_telegram_update(body: dict, brain: Any) -> dict:
    """Handle incoming Telegram updates (messages)."""
    message = body.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id", "unknown")

    if text and chat_id:
        # Skip /start command
        if text == "/start":
            await send_telegram_message(
                chat_id,
                "Hey! 👋 I'm Voca, your AI buddy! Just send me a message and I'll help you out!",
            )
            return {"status": "ok"}

        result = await brain.process(text, session_id=f"telegram-{user_id}")
        await send_telegram_message(chat_id, result.response)
        return {"status": "ok", "response": result.response}

    return {"status": "ok"}


async def send_telegram_message(chat_id: int | str, message: str) -> bool:
    """Send a message to a Telegram chat."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            )
        return True
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
        return False


# ============================================================
# NOTIFICATION ROUTER — sends to all configured channels
# ============================================================

async def broadcast_notification(message: str, channels: dict | None = None) -> dict:
    """Send a notification to all configured messaging platforms.

    channels = {"slack": "#general", "discord": "123456", "telegram": "789012"}
    """
    results = {}

    if SLACK_BOT_TOKEN:
        slack_channel = (channels or {}).get("slack", "#general")
        results["slack"] = await send_slack_notification(slack_channel, message)

    if DISCORD_BOT_TOKEN:
        discord_channel = (channels or {}).get("discord", "")
        if discord_channel:
            results["discord"] = await send_discord_message(discord_channel, message)

    if TELEGRAM_BOT_TOKEN:
        telegram_chat = (channels or {}).get("telegram", "")
        if telegram_chat:
            results["telegram"] = await send_telegram_message(telegram_chat, message)

    return results
