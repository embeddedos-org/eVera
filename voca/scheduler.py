"""Proactive Scheduler — background tasks that reach out to the user.

Unlike reactive agents that wait for input, this scheduler:
- Fires reminders when they're due
- Checks calendar and alerts about upcoming events
- Monitors stock price alerts
- Sends daily briefings
- Pushes notifications via WebSocket, Slack, Discord, Telegram
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ProactiveScheduler:
    """Background task scheduler that proactively notifies the user."""

    def __init__(self) -> None:
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._notification_handlers: list[Callable] = []
        self._check_interval = 30  # seconds

    def add_notification_handler(self, handler: Callable) -> None:
        """Register a handler that receives proactive notifications."""
        self._notification_handlers.append(handler)

    def remove_notification_handler(self, handler: Callable) -> None:
        """Remove a notification handler (e.g., on WebSocket disconnect)."""
        try:
            self._notification_handlers.remove(handler)
        except ValueError:
            pass

    async def start(self) -> None:
        """Start all background check loops."""
        self._running = True
        self._tasks = [
            asyncio.create_task(self._reminder_loop()),
            asyncio.create_task(self._calendar_loop()),
            asyncio.create_task(self._stock_alert_loop()),
            asyncio.create_task(self._daily_briefing_loop()),
        ]
        logger.info("Proactive scheduler started with %d check loops", len(self._tasks))

    async def stop(self) -> None:
        """Stop all background tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("Proactive scheduler stopped")

    async def _notify(self, notification: dict) -> None:
        """Send notification to all registered handlers."""
        notification["timestamp"] = datetime.now().isoformat()
        for handler in self._notification_handlers:
            try:
                await handler(notification)
            except Exception as e:
                logger.warning("Notification handler failed: %s", e)

    # --- Reminder checker ---

    async def _reminder_loop(self) -> None:
        """Check for due reminders every 30 seconds."""
        while self._running:
            try:
                await self._check_reminders()
            except Exception as e:
                logger.warning("Reminder check failed: %s", e)
            await asyncio.sleep(self._check_interval)

    async def _check_reminders(self) -> None:
        """Fire any reminders that are due."""
        reminders_path = DATA_DIR / "reminders.json"
        if not reminders_path.exists():
            return

        try:
            reminders = json.loads(reminders_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        now = datetime.now()
        fired = False

        for reminder in reminders:
            if reminder.get("dismissed"):
                continue

            trigger_at = datetime.fromisoformat(reminder["trigger_at"])
            if trigger_at <= now:
                await self._notify({
                    "type": "reminder",
                    "message": f"⏰ Reminder: {reminder['text']}",
                    "mood": "excited",
                    "data": reminder,
                })
                reminder["dismissed"] = True
                fired = True

        if fired:
            reminders_path.write_text(json.dumps(reminders, indent=2, default=str))

    # --- Calendar checker ---

    async def _calendar_loop(self) -> None:
        """Check for upcoming calendar events every 5 minutes."""
        while self._running:
            try:
                await self._check_upcoming_events()
            except Exception as e:
                logger.warning("Calendar check failed: %s", e)
            await asyncio.sleep(300)  # 5 minutes

    async def _check_upcoming_events(self) -> None:
        """Alert about events starting in the next 15 minutes."""
        calendar_path = DATA_DIR / "calendar.json"
        if not calendar_path.exists():
            return

        try:
            events = json.loads(calendar_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        for event in events:
            if event.get("date") != today or not event.get("time"):
                continue
            if event.get("notified"):
                continue

            try:
                event_time = datetime.strptime(f"{event['date']} {event['time']}", "%Y-%m-%d %H:%M")
                minutes_until = (event_time - now).total_seconds() / 60

                if 0 < minutes_until <= 15:
                    await self._notify({
                        "type": "calendar",
                        "message": f"📅 Heads up! '{event['title']}' starts in {int(minutes_until)} minutes!",
                        "mood": "thinking",
                        "data": event,
                    })
                    event["notified"] = True
            except (ValueError, KeyError):
                continue

        calendar_path.write_text(json.dumps(events, indent=2, default=str))

    # --- Stock alert checker ---

    async def _stock_alert_loop(self) -> None:
        """Check stock price alerts every 10 minutes during market hours."""
        while self._running:
            try:
                now = datetime.now()
                # Only check during US market hours (9:30 AM - 4:00 PM ET, roughly)
                if 9 <= now.hour <= 16:
                    await self._check_stock_alerts()
            except Exception as e:
                logger.warning("Stock alert check failed: %s", e)
            await asyncio.sleep(600)  # 10 minutes

    async def _check_stock_alerts(self) -> None:
        """Check watchlist for significant price moves."""
        portfolio_path = DATA_DIR / "portfolio.json"
        if not portfolio_path.exists():
            return

        try:
            portfolio = json.loads(portfolio_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        watchlist = portfolio.get("watchlist", [])
        holdings = portfolio.get("holdings", {})

        symbols_to_check = list(set(watchlist + list(holdings.keys())))
        if not symbols_to_check:
            return

        try:
            import yfinance as yf
            for symbol in symbols_to_check[:10]:  # Limit to 10
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.fast_info
                    price = info.last_price if hasattr(info, "last_price") else None
                    prev_close = info.previous_close if hasattr(info, "previous_close") else None

                    if price and prev_close and prev_close > 0:
                        change_pct = ((price / prev_close) - 1) * 100

                        # Alert on > 5% move
                        if abs(change_pct) >= 5:
                            direction = "📈" if change_pct > 0 else "📉"
                            await self._notify({
                                "type": "stock_alert",
                                "message": f"{direction} {symbol} moved {change_pct:+.1f}% to ${price:.2f}!",
                                "mood": "excited" if change_pct > 0 else "empathetic",
                                "data": {"symbol": symbol, "price": price, "change_pct": round(change_pct, 2)},
                            })
                except Exception:
                    continue
        except ImportError:
            pass

    # --- Daily briefing ---

    async def _daily_briefing_loop(self) -> None:
        """Send a daily morning briefing at 8:00 AM."""
        while self._running:
            now = datetime.now()
            if now.hour == 8 and now.minute < 2:
                try:
                    await self._send_daily_briefing()
                except Exception as e:
                    logger.warning("Daily briefing failed: %s", e)
                await asyncio.sleep(120)  # Don't send again for 2 minutes
            await asyncio.sleep(60)

    async def _send_daily_briefing(self) -> None:
        """Compile and send daily briefing."""
        today = datetime.now().strftime("%Y-%m-%d")
        parts = [f"☀️ Good morning! Here's your briefing for {datetime.now().strftime('%A, %B %d')}:\n"]

        # Calendar events today
        calendar_path = DATA_DIR / "calendar.json"
        if calendar_path.exists():
            try:
                events = json.loads(calendar_path.read_text())
                today_events = [e for e in events if e.get("date") == today]
                if today_events:
                    parts.append(f"📅 {len(today_events)} event(s) today:")
                    for e in today_events:
                        parts.append(f"  • {e.get('time', '??')} — {e['title']}")
                else:
                    parts.append("📅 No events today — free day!")
            except Exception:
                pass

        # Pending todos
        todos_path = DATA_DIR / "todos.json"
        if todos_path.exists():
            try:
                todos = json.loads(todos_path.read_text())
                pending = [t for t in todos if not t.get("done")]
                if pending:
                    parts.append(f"\n✅ {len(pending)} todo(s) pending:")
                    for t in pending[:5]:
                        parts.append(f"  • {t['text']}")
            except Exception:
                pass

        # Pending reminders
        reminders_path = DATA_DIR / "reminders.json"
        if reminders_path.exists():
            try:
                reminders = json.loads(reminders_path.read_text())
                active = [r for r in reminders if not r.get("dismissed")]
                if active:
                    parts.append(f"\n⏰ {len(active)} active reminder(s)")
            except Exception:
                pass

        parts.append("\nLet me know how I can help today! 💪")

        await self._notify({
            "type": "daily_briefing",
            "message": "\n".join(parts),
            "mood": "happy",
            "data": {"date": today},
        })
