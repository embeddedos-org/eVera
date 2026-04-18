"""Researcher Agent — conducts web research, summarization, and fact-checking."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

from voca.brain.agents.base import BaseAgent, Tool
from voca.providers.models import ModelTier

logger = logging.getLogger(__name__)


# --- Concrete tool implementations ---

class WebSearchTool(Tool):
    """Search the web using DuckDuckGo (no API key needed)."""

    def __init__(self) -> None:
        super().__init__(
            name="web_search",
            description="Search the web for information",
            parameters={
                "query": {"type": "str", "description": "Search query string"},
                "num_results": {"type": "int", "description": "Number of results (default 5)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query = kwargs.get("query", "")
        num = kwargs.get("num_results", 5)
        if not query:
            return {"status": "error", "message": "No query provided"}

        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=num))
            formatted = [
                {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                for r in results
            ]
            return {"status": "success", "query": query, "results": formatted, "count": len(formatted)}
        except ImportError:
            return await self._fallback_search(query, num)
        except Exception as e:
            logger.warning("DuckDuckGo search failed: %s — using fallback", e)
            return await self._fallback_search(query, num)

    async def _fallback_search(self, query: str, num: int) -> dict[str, Any]:
        """Fallback: use httpx to scrape DuckDuckGo HTML results."""
        try:
            import httpx
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Voca/1.0)"}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                text = resp.text

            results = []
            # Simple regex extraction from DDG HTML
            links = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', text)
            snippets = re.findall(r'class="result__snippet"[^>]*>([^<]*)<', text)

            for i, (href, title) in enumerate(links[:num]):
                snippet = snippets[i] if i < len(snippets) else ""
                results.append({"title": title.strip(), "url": href.strip(), "snippet": snippet.strip()})

            return {"status": "success", "query": query, "results": results, "count": len(results), "method": "fallback"}
        except Exception as e:
            return {"status": "error", "message": f"Search failed: {e}. Install duckduckgo-search: pip install duckduckgo-search"}


class SummarizeUrlTool(Tool):
    """Fetch and summarize a webpage."""

    def __init__(self) -> None:
        super().__init__(
            name="summarize_url",
            description="Fetch and extract text from a webpage URL",
            parameters={"url": {"type": "str", "description": "URL of the page to summarize"}},
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        url = kwargs.get("url", "")
        if not url:
            return {"status": "error", "message": "No URL provided"}

        try:
            import httpx
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Voca/1.0)"}
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(url, headers=headers, follow_redirects=True)
                html = resp.text

            # Try BeautifulSoup, fall back to regex
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                title = soup.title.string if soup.title else ""
                text = soup.get_text(separator="\n", strip=True)
            except ImportError:
                title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
                title = title.group(1).strip() if title else ""
                text = re.sub(r"<[^>]+>", " ", html)
                text = re.sub(r"\s+", " ", text).strip()

            # Truncate to reasonable size
            text = text[:3000]

            return {"status": "success", "url": url, "title": title, "text": text, "length": len(text)}
        except ImportError:
            return {"status": "error", "message": "Install httpx: pip install httpx"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to fetch URL: {e}"}


class FindPapersTool(Tool):
    """Search for academic papers on arXiv."""

    def __init__(self) -> None:
        super().__init__(
            name="find_papers",
            description="Search for academic papers on arXiv",
            parameters={
                "topic": {"type": "str", "description": "Research topic or keywords"},
                "max_results": {"type": "int", "description": "Max papers to return (default 5)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        topic = kwargs.get("topic", "")
        max_results = kwargs.get("max_results", 5)
        if not topic:
            return {"status": "error", "message": "No topic provided"}

        try:
            import httpx
            url = f"http://export.arxiv.org/api/query?search_query=all:{quote_plus(topic)}&max_results={max_results}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                xml = resp.text

            papers = []
            entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
            for entry in entries[:max_results]:
                title = re.search(r"<title>(.*?)</title>", entry, re.S)
                summary = re.search(r"<summary>(.*?)</summary>", entry, re.S)
                link = re.search(r'<id>(.*?)</id>', entry)
                authors = re.findall(r"<name>(.*?)</name>", entry)

                papers.append({
                    "title": title.group(1).strip() if title else "",
                    "summary": (summary.group(1).strip()[:300] + "...") if summary else "",
                    "url": link.group(1).strip() if link else "",
                    "authors": authors[:3],
                })

            return {"status": "success", "topic": topic, "papers": papers, "count": len(papers)}
        except ImportError:
            return {"status": "error", "message": "Install httpx: pip install httpx"}
        except Exception as e:
            return {"status": "error", "message": f"arXiv search failed: {e}"}


class FactCheckTool(Tool):
    """Verify a claim by searching for supporting/contradicting evidence."""

    def __init__(self) -> None:
        super().__init__(
            name="fact_check",
            description="Verify a factual claim by searching for evidence",
            parameters={"claim": {"type": "str", "description": "The claim to verify"}},
        )
        self._search = WebSearchTool()

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        claim = kwargs.get("claim", "")
        if not claim:
            return {"status": "error", "message": "No claim provided"}

        result = await self._search.execute(query=f"is it true that {claim}", num_results=5)
        if result.get("status") != "success":
            return {"status": "error", "message": "Could not search for evidence"}

        return {
            "status": "success",
            "claim": claim,
            "evidence": result.get("results", []),
            "note": "Review the evidence sources to determine veracity",
        }


class ResearcherAgent(BaseAgent):
    """Conducts web research, summarization, and fact-checking."""

    name = "researcher"
    description = "Conducts web research, summarization, and fact-checking"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are an AI research assistant. You can search the web, summarize webpages, "
        "find academic papers on arXiv, and fact-check claims. "
        "When the user asks a question, search for current information using web_search, "
        "then provide a concise answer with sources. "
        "Always cite your sources with URLs when available."
    )

    offline_responses = {
        "search": "🔍 Let me search that for you!",
        "research": "🔍 I'll research that right away!",
        "summarize": "📄 I'll summarize that for you!",
        "find": "🔍 Looking into that now!",
        "lookup": "🔍 Let me look that up!",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            WebSearchTool(),
            SummarizeUrlTool(),
            FindPapersTool(),
            FactCheckTool(),
        ]
