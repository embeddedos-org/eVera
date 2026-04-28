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
from datetime import datetime, timedelta
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
            logger.debug("Notification handler not found during removal")

    async def start(self) -> None:
        """Start all background check loops."""
        from config import settings

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
        # Conditionally start loops based on settings
        if settings.job_hunter.enabled:
            self._tasks.append(asyncio.create_task(self._job_scan_loop()))
        if settings.planner.enabled:
            self._tasks.append(asyncio.create_task(self._morning_plan_loop()))
        if settings.wellness.enabled:
            self._tasks.append(asyncio.create_task(self._break_reminder_loop()))
        if settings.digest.enabled:
            self._tasks.append(asyncio.create_task(self._digest_loop()))
        if settings.planner.enabled:
            self._tasks.append(asyncio.create_task(self._daily_review_reminder_loop()))
        if settings.emotional.enabled:
            self._tasks.append(asyncio.create_task(self._mood_check_loop()))
        if settings.jira.enabled:
            self._tasks.append(asyncio.create_task(self._ticket_scan_loop()))
        if settings.channel_monitor.enabled:
            self._tasks.append(asyncio.create_task(self._channel_monitor_loop()))
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
                await self._notify(
                    {
                        "type": "reminder",
                        "message": f"⏰ Reminder: {reminder['text']}",
                        "mood": "excited",
                        "data": reminder,
                    }
                )
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
                    await self._notify(
                        {
                            "type": "calendar",
                            "message": f"📅 Heads up! '{event['title']}' starts in {int(minutes_until)} minutes!",
                            "mood": "thinking",
                            "data": event,
                        }
                    )
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
                            await self._notify(
                                {
                                    "type": "stock_alert",
                                    "message": f"{direction} {symbol} moved {change_pct:+.1f}% to ${price:.2f}!",
                                    "mood": "excited" if change_pct > 0 else "empathetic",
                                    "data": {"symbol": symbol, "price": price, "change_pct": round(change_pct, 2)},
                                }
                            )
                except Exception:
                    continue
        except ImportError:
            logger.warning("yfinance not installed; stock alerts disabled")

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
            except Exception as e:
                logger.warning("Failed to load calendar for briefing: %s", e)

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
            except Exception as e:
                logger.warning("Failed to load todos for briefing: %s", e)

        # Pending reminders
        reminders_path = DATA_DIR / "reminders.json"
        if reminders_path.exists():
            try:
                reminders = json.loads(reminders_path.read_text())
                active = [r for r in reminders if not r.get("dismissed")]
                if active:
                    parts.append(f"\n⏰ {len(active)} active reminder(s)")
            except Exception as e:
                logger.warning("Failed to load reminders for briefing: %s", e)

        parts.append

        parts.append("\nLet me know how I can help today! 💪")

        await self._notify(
            {
                "type": "daily_briefing",
                "message": "\n".join(parts),
                "mood": "happy",
                "data": {"date": today},
            }
        )

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
                await self._notify(
                    {
                        "type": "scheduled_task",
                        "message": f"⏰ Scheduled task: {task.get('name', 'Unknown')}\n{task.get('description', '')}",
                        "mood": "thinking",
                        "data": task,
                    }
                )
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
                    await self._notify(
                        {
                            "type": "content_publish",
                            "message": f"📱 Time to publish on {post['platform']}!\n{post['content'][:100]}...",
                            "mood": "excited",
                            "data": post,
                        }
                    )
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
                await self._notify(
                    {
                        "type": "budget_alert",
                        "message": f"🚨 Budget exceeded for {cat}! Spent ${spent:.2f} of ${limit:.2f} ({pct:.0f}%)",
                        "mood": "error",
                        "data": {"category": cat, "spent": spent, "budget": limit, "percent": pct},
                    }
                )
            elif pct >= 80:
                await self._notify(
                    {
                        "type": "budget_warning",
                        "message": f"⚠️ Approaching budget limit for {cat}: ${spent:.2f} of ${limit:.2f} ({pct:.0f}%)",
                        "mood": "thinking",
                        "data": {"category": cat, "spent": spent, "budget": limit, "percent": pct},
                    }
                )

    # --- Job scan ---

    async def _job_scan_loop(self) -> None:
        """Periodically run a job scan cycle when job hunter is enabled."""
        from config import settings

        if not settings.job_hunter.enabled:
            return

        interval = settings.job_hunter.scan_interval_minutes * 60
        logger.info("Job scan loop started — interval %d minutes", settings.job_hunter.scan_interval_minutes)

        while self._running:
            try:
                await self._run_job_scan()
            except Exception as e:
                logger.warning("Job scan failed: %s", e)
            await asyncio.sleep(interval)

    async def _run_job_scan(self) -> None:
        """Execute one job scan cycle and notify with results."""
        from config import settings
        from vera.brain.agents.job_hunter import RunJobScanTool, _today_application_count

        daily_count = _today_application_count()
        if daily_count >= settings.job_hunter.max_daily_applications:
            logger.info(
                "Job scan skipped — daily cap reached (%d/%d)", daily_count, settings.job_hunter.max_daily_applications
            )
            return

        scanner = RunJobScanTool()
        result = await scanner.execute()

        applied = result.get("applied", 0)
        skipped = result.get("skipped", 0)
        failed = result.get("failed", 0)
        total = result.get("total_found", 0)

        if applied > 0 or failed > 0:
            await self._notify(
                {
                    "type": "job_scan",
                    "message": (
                        f"💼 Job scan complete!\n"
                        f"Found {total} jobs — applied to {applied}, skipped {skipped}, failed {failed}."
                    ),
                    "mood": "excited" if applied > 0 else "thinking",
                    "data": result,
                }
            )
        else:
            logger.info("Job scan: found %d jobs, all skipped or no new matches", total)

    # --- Morning plan ---

    async def _morning_plan_loop(self) -> None:
        """Generate morning plan at configured time."""
        from config import settings

        if not settings.planner.enabled:
            return

        while self._running:
            now = datetime.now()
            try:
                h, m = map(int, settings.planner.morning_plan_time.split(":"))
                if now.hour == h and now.minute == m:
                    await self._run_morning_plan()
                    await asyncio.sleep(120)
            except Exception as e:
                logger.warning("Morning plan loop failed: %s", e)
            await asyncio.sleep(60)

    async def _run_morning_plan(self) -> None:
        """Execute morning plan and send notification."""
        from vera.brain.agents.planner import MorningPlanTool

        tool = MorningPlanTool()
        result = await tool.execute(date="today")

        if result.get("status") == "success":
            plan = result.get("plan", {})
            events = plan.get("events", [])
            todos = plan.get("pending_todos", [])
            goals = plan.get("active_goals", [])

            parts = ["📋 Good morning! Here's your plan for today:\n"]
            if events:
                parts.append(f"📅 {len(events)} event(s):")
                for e in events[:5]:
                    parts.append(f"  • {e.get('time', '??')} — {e.get('title', '?')}")
            if todos:
                parts.append(f"\n✅ {len(todos)} pending task(s):")
                for t in todos[:5]:
                    parts.append(f"  • {t.get('text', '?')}")
            if goals:
                parts.append(f"\n🎯 {len(goals)} active goal(s):")
                for g in goals[:3]:
                    parts.append(f"  • {g.get('title', '?')}")
            parts.append("\nReady to crush it! 💪")

            await self._notify(
                {
                    "type": "morning_plan",
                    "message": "\n".join(parts),
                    "mood": "excited",
                    "data": result,
                }
            )

    # --- Break reminder ---

    async def _break_reminder_loop(self) -> None:
        """Remind user to take a break after continuous work."""
        from config import settings

        if not settings.wellness.enabled:
            return

        interval = settings.wellness.break_reminder_interval_min
        while self._running:
            try:
                await self._check_break_needed(interval)
            except Exception as e:
                logger.warning("Break reminder check failed: %s", e)
            await asyncio.sleep(60)

    async def _check_break_needed(self, interval_min: int) -> None:
        """Check if user has been working too long without a break."""
        wellness_path = DATA_DIR / "wellness.json"
        if not wellness_path.exists():
            return

        try:
            data = json.loads(wellness_path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        sessions = data.get("sessions", [])
        breaks = data.get("breaks", [])
        now = datetime.now()

        # Find the last break or session start
        last_break_time = None
        if breaks:
            try:
                last_break_time = datetime.fromisoformat(breaks[-1].get("start", ""))
            except (ValueError, TypeError):
                pass

        # Check if there's an active session and it's been too long since last break
        active_sessions = [s for s in sessions if not s.get("end")]
        if not active_sessions:
            return

        last_activity = last_break_time or datetime.fromisoformat(active_sessions[0]["start"])
        minutes_since = (now - last_activity).total_seconds() / 60

        if minutes_since >= interval_min:
            await self._notify(
                {
                    "type": "break_reminder",
                    "message": (
                        f"⏰ You've been working for {int(minutes_since)} minutes without a break!\n"
                        "How about a quick stretch or a cup of tea? ☕\n"
                        "Say 'take a break' when you're ready!"
                    ),
                    "mood": "thinking",
                    "data": {"minutes_worked": int(minutes_since)},
                }
            )

    # --- Digest ---

    async def _digest_loop(self) -> None:
        """Generate daily digest at configured time."""
        from config import settings

        if not settings.digest.enabled or not settings.digest.auto_digest:
            return

        while self._running:
            now = datetime.now()
            try:
                h, m = map(int, settings.digest.digest_time.split(":"))
                if now.hour == h and now.minute == m:
                    await self._run_digest()
                    await asyncio.sleep(120)
            except Exception as e:
                logger.warning("Digest loop failed: %s", e)
            await asyncio.sleep(60)

    async def _run_digest(self) -> None:
        """Execute digest generation and send notification."""
        from vera.brain.agents.digest import GenerateDigestTool

        tool = GenerateDigestTool()
        result = await tool.execute(date="today")

        if result.get("status") == "success":
            digest = result.get("digest", {})
            items = digest.get("items", [])
            sources = digest.get("sources_count", 0)

            await self._notify(
                {
                    "type": "daily_digest",
                    "message": f"📰 Your daily digest is ready! {len(items)} items from {sources} sources.",
                    "mood": "happy",
                    "data": result,
                }
            )

    # --- Daily review reminder ---

    async def _daily_review_reminder_loop(self) -> None:
        """Remind user to do their daily review."""
        from config import settings

        if not settings.planner.enabled:
            return

        while self._running:
            now = datetime.now()
            try:
                h, m = map(int, settings.planner.daily_review_time.split(":"))
                if now.hour == h and now.minute == m:
                    await self._notify(
                        {
                            "type": "daily_review_reminder",
                            "message": (
                                "📊 Time for your daily review!\n"
                                "Let's reflect on what you accomplished today and plan for tomorrow.\n"
                                "Say 'daily review' to get started!"
                            ),
                            "mood": "thinking",
                            "data": {"date": now.strftime("%Y-%m-%d")},
                        }
                    )
                    await asyncio.sleep(120)
            except Exception as e:
                logger.warning("Daily review reminder failed: %s", e)
            await asyncio.sleep(60)

    # --- Mood check ---

    async def _mood_check_loop(self) -> None:
        """Proactive mood monitoring — check-in when negative patterns emerge."""
        from config import settings

        if not settings.emotional.enabled or not settings.emotional.proactive_empathy_enabled:
            return

        interval = settings.emotional.mood_check_interval_min * 60
        last_notification_time: datetime | None = None
        cooldown = timedelta(hours=4)

        logger.info("Mood check loop started — interval %d minutes", settings.emotional.mood_check_interval_min)

        while self._running:
            try:
                await self._run_mood_check(settings, last_notification_time, cooldown)
            except Exception as e:
                logger.warning("Mood check failed: %s", e)
            await asyncio.sleep(interval)

    # --- Ticket scan ---

    async def _ticket_scan_loop(self) -> None:
        """Periodically scan for newly assigned Jira tickets."""
        from config import settings

        if not settings.jira.enabled:
            return

        interval = settings.jira.scan_interval_minutes * 60
        logger.info("Ticket scan loop started — interval %d minutes", settings.jira.scan_interval_minutes)

        while self._running:
            try:
                await self._run_ticket_scan()
            except Exception as e:
                logger.warning("Ticket scan failed: %s", e)
            await asyncio.sleep(interval)

    async def _run_ticket_scan(self) -> None:
        """Check for newly assigned Jira tickets and notify."""
        last_scan_path = DATA_DIR / "jira_last_scan.json"
        try:
            last_scan = json.loads(last_scan_path.read_text()) if last_scan_path.exists() else {}
        except (OSError, json.JSONDecodeError):
            last_scan = {}

        known_keys = set(last_scan.get("known_tickets", []))

        from vera.brain.agents.jira_agent import GetMyTicketsTool

        tool = GetMyTicketsTool()
        result = await tool.execute()

        if result.get("status") != "success":
            return

        current_keys = set()
        new_tickets = []
        for ticket in result.get("tickets", []):
            key = ticket.get("key", "")
            current_keys.add(key)
            if key and key not in known_keys:
                new_tickets.append(ticket)

        if new_tickets:
            for ticket in new_tickets:
                await self._notify(
                    {
                        "type": "new_ticket",
                        "message": (
                            f"🎫 New ticket assigned to you: {ticket['key']}\n"
                            f"  {ticket.get('summary', '')}\n"
                            f"  Priority: {ticket.get('priority', 'N/A')} | Type: {ticket.get('type', 'N/A')}"
                        ),
                        "mood": "thinking",
                        "data": ticket,
                    }
                )

        last_scan_path.parent.mkdir(parents=True, exist_ok=True)
        last_scan_path.write_text(
            json.dumps(
                {
                    "known_tickets": list(current_keys),
                    "last_scan": datetime.now().isoformat(),
                },
                indent=2,
            )
        )

    # --- Channel monitor ---

    async def _channel_monitor_loop(self) -> None:
        """Monitor Slack channels for new messages and mentions."""
        from config import settings

        if not settings.channel_monitor.enabled:
            return

        interval = settings.channel_monitor.poll_interval_min * 60
        logger.info("Channel monitor loop started — interval %d minutes", settings.channel_monitor.poll_interval_min)

        while self._running:
            try:
                await self._run_channel_monitor()
            except Exception as e:
                logger.warning("Channel monitor failed: %s", e)
            await asyncio.sleep(interval)

    async def _run_channel_monitor(self) -> None:
        """Poll configured channels for new activity."""
        from config import settings
        from vera.messaging import SLACK_BOT_TOKEN, fetch_channel_history

        if not SLACK_BOT_TOKEN:
            return

        state_path = DATA_DIR / "channel_monitor.json"
        try:
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
        except (OSError, json.JSONDecodeError):
            state = {}

        channels = settings.channel_monitor.channels
        if not channels:
            return

        for channel_id in channels:
            last_ts = state.get(channel_id, "0")
            messages = await fetch_channel_history(channel_id, oldest=last_ts, limit=50)

            if not messages:
                continue

            new_msgs = [m for m in messages if m.get("ts", "0") > last_ts]
            if not new_msgs:
                continue

            state[channel_id] = max(m.get("ts", "0") for m in new_msgs)

            mention_count = sum(1 for m in new_msgs if "<@" in m.get("text", ""))

            if settings.channel_monitor.mention_alert and mention_count > 0:
                await self._notify(
                    {
                        "type": "mention_alert",
                        "message": f"💬 You were mentioned {mention_count} time(s) in channel {channel_id}!",
                        "mood": "excited",
                        "data": {"channel": channel_id, "mentions": mention_count, "total_new": len(new_msgs)},
                    }
                )
            else:
                await self._notify(
                    {
                        "type": "channel_activity",
                        "message": f"💬 {len(new_msgs)} new message(s) in channel {channel_id}.",
                        "mood": "neutral",
                        "data": {"channel": channel_id, "count": len(new_msgs)},
                    }
                )

        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))

    async def _run_mood_check(self, settings, last_notification_time, cooldown) -> None:
        """Execute one mood check cycle."""
        from vera.emotional.mood_tracker import MoodTracker
        from vera.emotional.pattern_detector import detect_patterns
        from vera.emotional.sentiment import NEGATIVE_MOODS

        now = datetime.now()
        if last_notification_time and (now - last_notification_time) < cooldown:
            return

        tracker = MoodTracker(DATA_DIR / "mood_history.json")
        recent = tracker.recent(hours=4)
        history = tracker.history(days=settings.emotional.pattern_lookback_days)

        if not recent:
            return

        # Check for consecutive negative streak
        threshold = settings.emotional.negative_mood_threshold
        streak = 0
        for entry in reversed(recent):
            if entry.mood in NEGATIVE_MOODS:
                streak += 1
            else:
                break

        if streak >= threshold:
            last_mood = recent[-1].mood
            await self._notify(
                {
                    "type": "mood_checkin",
                    "message": (
                        f"Hey, I've noticed you've been feeling {last_mood} lately. "
                        "I just want to check in — is there anything I can help with? "
                        "Sometimes talking it out helps. 💙"
                    ),
                    "mood": "empathetic",
                    "data": {"streak": streak, "current_mood": last_mood},
                }
            )
            return

        # Check for day-of-week pattern
        patterns = detect_patterns(history, lookback_days=settings.emotional.pattern_lookback_days)
        today_name = now.strftime("%A")

        for p in patterns:
            if p.pattern_type == "day_of_week" and p.data.get("day") == today_name:
                await self._notify(
                    {
                        "type": "mood_preemptive",
                        "message": (
                            f"I know {today_name}s can be tough sometimes. "
                            "Just a heads up — I'm here if you need me today! 🌟"
                        ),
                        "mood": "empathetic",
                        "data": {"pattern": p.pattern_type, "day": today_name},
                    }
                )
                return
