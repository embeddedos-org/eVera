"""Digest Agent — information curation, RSS feeds, news digests, and reading lists."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
DIGESTS_DIR = DATA_DIR / "digests"


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
    return []


def _save_json(path: Path, data: Any) -> None:
    _ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# --- Tool implementations ---


class AddSourceTool(Tool):
    """Add an RSS feed, website, or topic to monitor."""

    def __init__(self) -> None:
        super().__init__(
            name="add_source",
            description="Add an RSS feed URL, website, or topic keyword to monitor for daily digests",
            parameters={
                "name": {"type": "str", "description": "Source name (e.g. 'TechCrunch', 'AI News')"},
                "type": {"type": "str", "description": "Source type: rss, website, or topic"},
                "url": {"type": "str", "description": "URL for RSS/website sources, or search keyword for topic sources"},
                "category": {"type": "str", "description": "Category for grouping (e.g. 'tech', 'business', 'science')"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        name = kwargs.get("name", "")
        source_type = kwargs.get("type", "rss").lower()
        url = kwargs.get("url", "")
        category = kwargs.get("category", "general")

        if not name:
            return {"status": "error", "message": "No source name provided"}
        if not url:
            return {"status": "error", "message": "No URL or keyword provided"}

        if source_type not in ("rss", "website", "topic"):
            source_type = "rss"

        # Validate URL accessibility for rss/website
        if source_type in ("rss", "website"):
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.head(url, follow_redirects=True)
                    if resp.status_code >= 400:
                        logger.warning("Source URL returned status %d: %s", resp.status_code, url)
            except ImportError:
                pass
            except Exception as e:
                logger.warning("Could not validate source URL: %s", e)

        _ensure_dirs()
        sources = _load_json(DATA_DIR / "digest_sources.json")

        # Check for duplicates
        for s in sources:
            if s.get("url") == url:
                return {"status": "error", "message": f"Source already exists: {s.get('name')}"}

        source = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "name": name,
            "type": source_type,
            "url": url,
            "category": category,
            "added_at": datetime.now().isoformat(),
        }

        sources.append(source)
        _save_json(DATA_DIR / "digest_sources.json", sources)

        return {"status": "success", "source": source}


class RemoveSourceTool(Tool):
    """Remove a source from the monitoring list."""

    def __init__(self) -> None:
        super().__init__(
            name="remove_source",
            description="Remove a source from the digest monitoring list by name or ID",
            parameters={
                "source_id": {"type": "str", "description": "Source ID or name to remove"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        source_id = kwargs.get("source_id", "")
        if not source_id:
            return {"status": "error", "message": "No source ID or name provided"}

        sources = _load_json(DATA_DIR / "digest_sources.json")
        original_count = len(sources)

        sources = [
            s for s in sources
            if s.get("id") != source_id and s.get("name", "").lower() != source_id.lower()
        ]

        if len(sources) == original_count:
            return {"status": "error", "message": f"Source not found: {source_id}"}

        _save_json(DATA_DIR / "digest_sources.json", sources)

        return {"status": "success", "message": f"Removed source: {source_id}", "remaining": len(sources)}


class GenerateDigestTool(Tool):
    """Fetch all sources and generate a daily digest."""

    def __init__(self) -> None:
        super().__init__(
            name="generate_digest",
            description="Fetch all monitored sources, extract content, and compile a daily digest",
            parameters={
                "date": {"type": "str", "description": "Date for digest (YYYY-MM-DD or 'today'). Default: today"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        from config import settings

        date_str = kwargs.get("date", "today").strip()
        if date_str == "today":
            date_str = datetime.now().strftime("%Y-%m-%d")

        _ensure_dirs()
        sources = _load_json(DATA_DIR / "digest_sources.json")

        if not sources:
            return {"status": "error", "message": "No sources configured. Use add_source to add RSS feeds, websites, or topics."}

        max_items = settings.digest.max_items_per_source
        all_items: list[dict] = []

        for source in sources:
            try:
                items = await self._fetch_source(source, max_items)
                all_items.extend(items)
            except Exception as e:
                logger.warning("Failed to fetch source '%s': %s", source.get("name"), e)
                all_items.append({
                    "source": source.get("name", "Unknown"),
                    "category": source.get("category", "general"),
                    "title": f"[Error fetching {source.get('name')}]",
                    "snippet": str(e),
                    "url": source.get("url", ""),
                })

        digest = {
            "date": date_str,
            "generated_at": datetime.now().isoformat(),
            "sources_count": len(sources),
            "items_count": len(all_items),
            "items": all_items,
        }

        _save_json(DIGESTS_DIR / f"{date_str}.json", digest)

        return {
            "status": "success",
            "digest": digest,
            "message": f"📰 Daily digest generated with {len(all_items)} items from {len(sources)} sources",
        }

    async def _fetch_source(self, source: dict, max_items: int) -> list[dict]:
        """Fetch items from a single source."""
        source_type = source.get("type", "rss")
        source_name = source.get("name", "Unknown")
        source_url = source.get("url", "")
        category = source.get("category", "general")

        if source_type == "rss":
            return await self._fetch_rss(source_url, source_name, category, max_items)
        elif source_type == "website":
            return await self._fetch_website(source_url, source_name, category, max_items)
        elif source_type == "topic":
            return await self._fetch_topic(source_url, source_name, category, max_items)

        return []

    async def _fetch_rss(self, url: str, name: str, category: str, max_items: int) -> list[dict]:
        """Parse an RSS feed."""
        try:
            import httpx
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Vera/1.0)"}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                xml = resp.text

            items = []
            entries = re.findall(r"<item>(.*?)</item>", xml, re.S)
            if not entries:
                entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)

            for entry in entries[:max_items]:
                title = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", entry, re.S)
                link = re.search(r"<link[^>]*(?:href=[\"']([^\"']*)[\"']|>(.*?)</link>)", entry, re.S)
                desc = re.search(r"<(?:description|summary)>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</(?:description|summary)>", entry, re.S)

                item_url = ""
                if link:
                    item_url = link.group(1) or link.group(2) or ""

                items.append({
                    "source": name,
                    "category": category,
                    "title": (title.group(1).strip() if title else "Untitled"),
                    "url": item_url.strip(),
                    "snippet": (desc.group(1).strip()[:200] if desc else ""),
                })

            return items
        except ImportError:
            return [{"source": name, "category": category, "title": "[httpx not installed]", "snippet": "pip install httpx", "url": url}]
        except Exception as e:
            logger.warning("RSS fetch failed for %s: %s", name, e)
            return []

    async def _fetch_website(self, url: str, name: str, category: str, max_items: int) -> list[dict]:
        """Scrape a website for headlines."""
        try:
            import httpx
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Vera/1.0)"}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                html = resp.text

            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                headlines = []
                for tag in soup.find_all(["h1", "h2", "h3", "a"], limit=max_items * 3):
                    text = tag.get_text(strip=True)
                    link = tag.get("href", "")
                    if text and len(text) > 10:
                        if link and not link.startswith("http"):
                            link = url.rstrip("/") + "/" + link.lstrip("/")
                        headlines.append({
                            "source": name,
                            "category": category,
                            "title": text[:150],
                            "url": link,
                            "snippet": "",
                        })
                return headlines[:max_items]
            except ImportError:
                titles = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.S | re.I)
                return [
                    {"source": name, "category": category, "title": re.sub(r"<[^>]+>", "", t).strip()[:150], "url": url, "snippet": ""}
                    for t in titles[:max_items]
                ]
        except ImportError:
            return [{"source": name, "category": category, "title": "[httpx not installed]", "snippet": "pip install httpx", "url": url}]
        except Exception as e:
            logger.warning("Website fetch failed for %s: %s", name, e)
            return []

    async def _fetch_topic(self, keyword: str, name: str, category: str, max_items: int) -> list[dict]:
        """Search for a topic using DuckDuckGo."""
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(keyword, max_results=max_items))
            return [
                {
                    "source": name,
                    "category": category,
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:200],
                }
                for r in results
            ]
        except ImportError:
            # Fallback to httpx scraping
            try:
                import httpx
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(keyword)}"
                headers = {"User-Agent": "Mozilla/5.0 (compatible; Vera/1.0)"}
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, headers=headers, follow_redirects=True)
                    text = resp.text

                links = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', text)
                return [
                    {"source": name, "category": category, "title": title.strip(), "url": href.strip(), "snippet": ""}
                    for href, title in links[:max_items]
                ]
            except Exception:
                return []
        except Exception as e:
            logger.warning("Topic search failed for %s: %s", name, e)
            return []


class SummarizeThreadTool(Tool):
    """Summarize a long email thread or message conversation."""

    def __init__(self) -> None:
        super().__init__(
            name="summarize_thread",
            description="Summarize a long email thread or message conversation — extracts key decisions, action items, and summary",
            parameters={
                "text": {"type": "str", "description": "The full thread text to summarize"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        text = kwargs.get("text", "")
        if not text:
            return {"status": "error", "message": "No text provided to summarize"}

        # Truncate very long threads
        text = text[:5000]

        return {
            "status": "success",
            "original_length": len(text),
            "text": text,
            "note": "LLM will generate key decisions, action items, and summary from this thread",
        }


class ReadingListTool(Tool):
    """Manage a read-later queue."""

    def __init__(self) -> None:
        super().__init__(
            name="reading_list",
            description="Add, view, or complete items in a read-later queue",
            parameters={
                "action": {"type": "str", "description": "Action: add, list, complete, remove. Default: list"},
                "title": {"type": "str", "description": "Article title (for add)"},
                "url": {"type": "str", "description": "Article URL (for add)"},
                "item_id": {"type": "str", "description": "Item ID (for complete/remove)"},
                "priority": {"type": "str", "description": "Priority: high, medium, low. Default: medium"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        action = kwargs.get("action", "list").lower()
        title = kwargs.get("title", "")
        url = kwargs.get("url", "")
        item_id = kwargs.get("item_id", "")
        priority = kwargs.get("priority", "medium")

        _ensure_dirs()
        reading_list = _load_json(DATA_DIR / "reading_list.json")

        if action == "add":
            if not title and not url:
                return {"status": "error", "message": "Provide at least a title or URL"}

            item = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "title": title or url,
                "url": url,
                "added_at": datetime.now().isoformat(),
                "read": False,
                "priority": priority,
                "notes": "",
            }

            reading_list.append(item)
            _save_json(DATA_DIR / "reading_list.json", reading_list)
            return {"status": "success", "action": "added", "item": item}

        elif action == "complete":
            for item in reading_list:
                if item.get("id") == item_id:
                    item["read"] = True
                    item["completed_at"] = datetime.now().isoformat()
                    _save_json(DATA_DIR / "reading_list.json", reading_list)
                    return {"status": "success", "action": "completed", "item": item}
            return {"status": "error", "message": f"Item not found: {item_id}"}

        elif action == "remove":
            original_len = len(reading_list)
            reading_list = [item for item in reading_list if item.get("id") != item_id]
            if len(reading_list) < original_len:
                _save_json(DATA_DIR / "reading_list.json", reading_list)
                return {"status": "success", "action": "removed", "item_id": item_id}
            return {"status": "error", "message": f"Item not found: {item_id}"}

        else:  # list
            unread = [item for item in reading_list if not item.get("read")]
            priority_order = {"high": 0, "medium": 1, "low": 2}
            unread.sort(key=lambda x: priority_order.get(x.get("priority", "medium"), 1))
            return {"status": "success", "reading_list": unread, "count": len(unread)}


class FilterNoiseTool(Tool):
    """Rank items by relevance to user's goals/interests."""

    def __init__(self) -> None:
        super().__init__(
            name="filter_noise",
            description="Given a list of items, rank by relevance to user's goals and interests. Reduces information overload",
            parameters={
                "items": {"type": "str", "description": "JSON array of items with title/snippet fields, or comma-separated titles"},
                "threshold": {"type": "float", "description": "Relevance threshold 0-1. Default: 0.5"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        items_str = kwargs.get("items", "")
        threshold = kwargs.get("threshold", 0.5)

        if not items_str:
            return {"status": "error", "message": "No items provided"}

        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            threshold = 0.5

        # Try to parse as JSON array
        try:
            items = json.loads(items_str)
        except (json.JSONDecodeError, TypeError):
            items = [{"title": t.strip()} for t in items_str.split(",") if t.strip()]

        # Load user goals for relevance context
        goals = _load_json(DATA_DIR / "goals.json")
        active_goals = [g for g in goals if g.get("status") == "active"]

        return {
            "status": "success",
            "items": items,
            "items_count": len(items),
            "goals_context": [g.get("title", "") for g in active_goals],
            "threshold": threshold,
            "note": "LLM will score each item by relevance to goals and filter below threshold",
        }


class DigestAgent(BaseAgent):
    """Information curator that aggregates, filters, and summarizes content from multiple sources."""

    name = "digest"
    description = "Information curator for RSS feeds, news digests, thread summarization, and reading lists"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are an information curator that helps the user stay informed without being "
        "overwhelmed. You:\n"
        "- Manage RSS feeds, websites, and topic monitors\n"
        "- Generate concise daily digests grouped by category\n"
        "- Summarize long email threads and conversations\n"
        "- Maintain a read-later queue with priority sorting\n"
        "- Filter noise by scoring items against the user's goals and interests\n\n"
        "When generating digests, group items by category, highlight the 3 most important "
        "items, and keep summaries concise. For thread summarization, extract key decisions, "
        "action items, and a brief summary."
    )

    offline_responses = {
        "digest": "📰 Let me generate your digest!",
        "news": "📰 Fetching the latest news for you!",
        "rss": "📡 Managing your RSS feeds!",
        "feed": "📡 Let me check your feeds!",
        "reading_list": "📚 Let me check your reading list!",
        "newsletter": "📰 Let me compile your newsletter!",
        "summarize_thread": "📝 Let me summarize that thread for you!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            AddSourceTool(),
            RemoveSourceTool(),
            GenerateDigestTool(),
            SummarizeThreadTool(),
            ReadingListTool(),
            FilterNoiseTool(),
        ]
