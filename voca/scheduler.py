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
            asyncio.create_task(self._scheduled_tasks_loop()),
            asyncio.create_task(self._content_publisher_loop()),
            asyncio.create_task(self._spending_alert_loop()),
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

    # --- Scheduled recurring tasks ---

    async def _scheduled_tasks_loop(self) -> None:
        """Execute user-defined scheduled/recurring tasks every minute."""
        while self._running:
            try:
                await self._check_scheduled_tasks()
            except Exception as e:
                logger.warning("Scheduled tasks check failed: %s", e)
            await asyncio.sleep(60)

    async def _check_scheduled_tasks(self) -> None:
        """Check and execute due scheduled tasks."""
        tasks_path = DATA_DIR / "scheduled_tasks.json"
        if not tasks_path.exists():
            return

        try:
            tasks = json.loads(tasks_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        now = datetime.now()
        updated = False

        for task in tasks:
            if not task.get("enabled", True):
                continue

            schedule = task.get("schedule", {})
            task_type = schedule.get("type", "")

            should_run = False

            if task_type == "daily":
                run_time = schedule.get("time", "08:00")
                h, m = map(int, run_time.split(":"))
                if now.hour == h and now.minute == m:
                    last_run = task.get("last_run", "")
                    if last_run != now.strftime("%Y-%m-%d"):
                        should_run = True

            elif task_type == "weekly":
                run_day = schedule.get("day", "monday").lower()
                run_time = schedule.get("time", "08:00")
                h, m = map(int, run_time.split(":"))
                day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                if now.strftime("%A").lower() == run_day and now.hour == h and now.minute == m:
                    last_run = task.get("last_run", "")
                    if last_run != now.strftime("%Y-%m-%d"):
                        should_run = True

            elif task_type == "interval":
                interval_min = schedule.get("minutes", 60)
                last_run = task.get("last_run_ts", 0)
                if (now.timestamp() - last_run) >= (interval_min * 60):
                    should_run = True

            if should_run:
                await self._notify({
                    "type": "scheduled_task",
                    "message": f"⏰ Scheduled task: {task.get('name', 'Unknown')}\n{task.get('description', '')}",
                    "mood": "thinking",
                    "data": task,
                })
                task["last_run"] = now.strftime("%Y-%m-%d")
                task["last_run_ts"] = now.timestamp()
                task["run_count"] = task.get("run_count", 0) + 1
                updated = True

        if updated:
            tasks_path.write_text(json.dumps(tasks, indent=2, default=str))

    # --- Content publisher ---

    async def _content_publisher_loop(self) -> None:
        """Check for scheduled social media posts ready to publish."""
        while self._running:
            try:
                await self._check_scheduled_posts()
            except Exception as e:
                logger.warning("Content publisher check failed: %s", e)
            await asyncio.sleep(60)

    async def _check_scheduled_posts(self) -> None:
        """Publish any posts whose schedule time has arrived."""
        posts_path = DATA_DIR / "scheduled_posts.json"
        if not posts_path.exists():
            return

        try:
            posts = json.loads(posts_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        now = datetime.now()
        updated = False

        for post in posts:
            if post.get("status") != "scheduled":
                continue

            try:
                schedule_at = datetime.fromisoformat(post["schedule_at"])
                if schedule_at <= now:
                    await self._notify({
                        "type": "content_publish",
                        "message": f"📱 Time to publish on {post['platform']}!\n{post['content'][:100]}...",
                        "mood": "excited",
                        "data": post,
                    })
                    post["status"] = "ready_to_publish"
                    post["notified_at"] = now.isoformat()
                    updated = True
            except (ValueError, KeyError):
                continue

        if updated:
            posts_path.write_text(json.dumps(posts, indent=2, default=str))

    # --- Spending alert ---

    async def _spending_alert_loop(self) -> None:
        """Check spending against budgets every hour."""
        while self._running:
            try:
                await self._check_spending_alerts()
            except Exception as e:
                logger.warning("Spending alert check failed: %s", e)
            await asyncio.sleep(3600)  # Every hour

    async def _check_spending_alerts(self) -> None:
        """Alert if spending exceeds 80% of any budget category."""
        finance_path = DATA_DIR / "finance.json"
        if not finance_path.exists():
            return

        try:
            finance = json.loads(finance_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        budgets = finance.get("budgets", {})
        transactions = finance.get("transactions", [])

        if not budgets:
            return

        # Calculate this month's spending by category
        month_start = datetime.now().replace(day=1).isoformat()
        monthly_txns = [t for t in transactions if t.get("date", "") >= month_start and t.get("amount", 0) < 0]

        by_category: dict[str, float] = {}
        for t in monthly_txns:
            cat = t.get("category", "Other")
            by_category[cat] = by_category.get(cat, 0) + abs(t.get("amount", 0))

        for cat, limit in budgets.items():
            spent = by_category.get(cat, 0)
            pct = (spent / limit * 100) if limit > 0 else 0

            if pct >= 100:
                await self._notify({
                    "type": "budget_alert",
                    "message": f"🚨 Budget exceeded for {cat}! Spent ${spent:.2f} of ${limit:.2f} ({pct:.0f}%)",
                    "mood": "error",
                    "data": {"category": cat, "spent": spent, "budget": limit, "percent": pct},
                })
            elif pct >= 80:
                await self._notify({
                    "type": "budget_warning",
                    "message": f"⚠️ Approaching budget limit for {cat}: ${spent:.2f} of ${limit:.2f} ({pct:.0f}%)",
                    "mood": "thinking",
                    "data": {"category": cat, "spent": spent, "budget": limit, "percent": pct},
                })
