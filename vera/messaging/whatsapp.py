"""
eVera WhatsApp Integration
==========================
Two modes:
  1. Twilio WhatsApp API  — cloud, requires Twilio account (production)
  2. whatsapp-web.js      — local browser automation via Node.js (no account needed)

Set WHATSAPP_MODE in config to "twilio" or "wwebjs".

Twilio setup:
  TWILIO_ACCOUNT_SID=ACxxx
  TWILIO_AUTH_TOKEN=xxx
  TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

wwebjs setup (local, no API key):
  Requires Node.js + whatsapp-web.js installed:
    cd vera/messaging && npm install whatsapp-web.js qrcode-terminal
  Then run: node whatsapp_bridge.js
  The bridge listens on localhost:8766 for messages from eVera.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Callable, Optional

import httpx

logger = logging.getLogger("evera.whatsapp")


class WhatsAppTwilio:
    """
    Send/receive WhatsApp messages via Twilio.
    Incoming messages arrive at POST /webhooks/whatsapp (registered in app.py).
    """

    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv(
            "TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886"
        )
        self._enabled = bool(self.account_sid and self.auth_token)
        if not self._enabled:
            logger.warning(
                "[WhatsApp/Twilio] TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set — disabled"
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send(self, to: str, message: str) -> bool:
        """Send a WhatsApp message. `to` should be 'whatsapp:+1234567890'."""
        if not self._enabled:
            return False
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
                    auth=(self.account_sid, self.auth_token),
                    data={
                        "From": self.from_number,
                        "To": to,
                        "Body": message,
                    },
                )
                if resp.status_code in (200, 201):
                    logger.info("[WhatsApp/Twilio] Sent to %s", to)
                    return True
                else:
                    logger.error(
                        "[WhatsApp/Twilio] Send failed: %s %s", resp.status_code, resp.text
                    )
                    return False
        except Exception as e:
            logger.error("[WhatsApp/Twilio] Exception: %s", e)
            return False

    def parse_incoming(self, form_data: dict) -> Optional[dict]:
        """Parse an incoming Twilio WhatsApp webhook payload."""
        body = form_data.get("Body", "").strip()
        from_number = form_data.get("From", "").replace("whatsapp:", "")
        if not body or not from_number:
            return None
        return {
            "platform": "whatsapp",
            "provider": "twilio",
            "from": from_number,
            "message": body,
            "media_url": form_data.get("MediaUrl0"),
        }


class WhatsAppWebJS:
    """
    Send/receive WhatsApp messages via the local whatsapp-web.js bridge.
    The bridge is a Node.js process that connects to WhatsApp Web via Puppeteer.
    eVera communicates with it over a local HTTP API on port 8766.
    """

    def __init__(self, bridge_url: str = "http://localhost:8766"):
        self.bridge_url = bridge_url
        self._enabled = False
        self._message_handlers: list[Callable] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def check_bridge(self) -> bool:
        """Check if the whatsapp-web.js bridge is running."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.bridge_url}/status")
                self._enabled = resp.status_code == 200
                return self._enabled
        except Exception:
            self._enabled = False
            return False

    async def send(self, to: str, message: str) -> bool:
        """Send a WhatsApp message via the local bridge."""
        if not self._enabled:
            await self.check_bridge()
        if not self._enabled:
            logger.warning("[WhatsApp/wwebjs] Bridge not running at %s", self.bridge_url)
            return False
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.bridge_url}/send",
                    json={"to": to, "message": message},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("[WhatsApp/wwebjs] Send failed: %s", e)
            return False

    async def get_qr_code(self) -> Optional[str]:
        """Get the QR code for WhatsApp Web login (base64 PNG)."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.bridge_url}/qr")
                if resp.status_code == 200:
                    return resp.json().get("qr")
        except Exception:
            pass
        return None

    async def get_status(self) -> dict:
        """Get bridge status: connected, phone number, battery, etc."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.bridge_url}/status")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return {"connected": False}


class WhatsAppManager:
    """
    Unified WhatsApp manager — tries Twilio first, falls back to wwebjs.
    """

    def __init__(self):
        self.twilio = WhatsAppTwilio()
        self.wwebjs = WhatsAppWebJS(
            bridge_url=os.getenv("WWEBJS_BRIDGE_URL", "http://localhost:8766")
        )
        self._mode = os.getenv("WHATSAPP_MODE", "auto")  # "twilio" | "wwebjs" | "auto"

    async def send(self, to: str, message: str) -> bool:
        """Send a message using the configured provider."""
        if self._mode == "twilio" or (self._mode == "auto" and self.twilio.enabled):
            return await self.twilio.send(to, message)
        elif self._mode == "wwebjs" or self._mode == "auto":
            return await self.wwebjs.send(to, message)
        logger.warning("[WhatsApp] No provider configured")
        return False

    async def get_status(self) -> dict:
        """Get status of all WhatsApp providers."""
        twilio_ok = self.twilio.enabled
        wwebjs_status = await self.wwebjs.get_status()
        return {
            "twilio": {"enabled": twilio_ok},
            "wwebjs": wwebjs_status,
            "active_mode": self._mode,
        }

    def parse_twilio_webhook(self, form_data: dict) -> Optional[dict]:
        return self.twilio.parse_incoming(form_data)


# ── Singleton ─────────────────────────────────────────────────────────────────
_manager: Optional[WhatsAppManager] = None


def get_whatsapp() -> WhatsAppManager:
    global _manager
    if _manager is None:
        _manager = WhatsAppManager()
    return _manager
