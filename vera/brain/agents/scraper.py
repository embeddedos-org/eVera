"""Web Scraper Agent — structured data extraction from web pages.

Navigates to URLs, extracts data according to a schema, handles pagination,
and outputs JSON/CSV/Markdown.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from vera.providers.manager import ProviderManager
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a web data extraction expert. Given the page HTML content and a data schema, extract structured data.

Schema (fields to extract):
{schema}

Page content (truncated):
{content}

Extract ALL matching items from the page content. Respond with ONLY a JSON array of objects matching the schema:
[{{"field1": "value1", "field2": "value2", ...}}, ...]

If no data matches the schema, respond with an empty array: []"""

PAGINATION_PROMPT = """Analyze this page's HTML to find the "next page" link or button.

Page HTML (truncated):
{content}

Respond with ONLY a JSON object:
{{"has_next": true/false, "next_url": "..." or null, "next_selector": "CSS selector for next button" or null}}"""


@dataclass
class ScrapeResult:
    """Result from a web scraping operation."""

    url: str
    items: list[dict[str, Any]] = field(default_factory=list)
    pages_scraped: int = 0
    total_items: int = 0
    status: str = "success"
    error: str | None = None


class WebScraper:
    """Scrapes structured data from web pages using LLM-guided extraction."""

    def __init__(self, provider: ProviderManager) -> None:
        self._provider = provider

    async def scrape(
        self,
        url: str,
        schema: dict[str, str],
        max_pages: int = 5,
        output_format: str = "json",
    ) -> ScrapeResult:
        """Scrape structured data from a URL.

        @param url: Starting URL to scrape.
        @param schema: Dict of field_name → description.
        @param max_pages: Maximum pages to follow via pagination.
        @param output_format: Output format (json, csv, markdown).
        """
        from vera.brain.agents.browser import _get_page

        result = ScrapeResult(url=url)
        current_url = url

        try:
            page = await _get_page()

            for page_num in range(max_pages):
                # Navigate to page
                await page.goto(current_url, wait_until="networkidle", timeout=30000)

                # Get page content
                content = await page.content()
                # Truncate to avoid token limits
                content_truncated = content[:15000]

                # Extract data using LLM
                items = await self._extract_data(content_truncated, schema)
                result.items.extend(items)
                result.pages_scraped += 1

                logger.info(
                    "Scraped page %d (%s): %d items",
                    page_num + 1,
                    current_url[:80],
                    len(items),
                )

                # Check for pagination
                if page_num < max_pages - 1:
                    pagination = await self._find_next_page(content_truncated)
                    if pagination.get("has_next"):
                        if pagination.get("next_url"):
                            current_url = pagination["next_url"]
                        elif pagination.get("next_selector"):
                            try:
                                await page.click(pagination["next_selector"])
                                await page.wait_for_load_state("networkidle")
                                current_url = page.url
                            except Exception as e:
                                logger.warning("Pagination click failed: %s", e)
                                break
                        else:
                            break
                    else:
                        break

            result.total_items = len(result.items)
            result.status = "success"

        except Exception as e:
            result.status = "error"
            result.error = str(e)
            logger.error("Scraping failed: %s", e)

        return result

    async def _extract_data(
        self,
        html_content: str,
        schema: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Use LLM to extract structured data from HTML."""
        schema_str = json.dumps(schema, indent=2)
        prompt = EXTRACTION_PROMPT.format(schema=schema_str, content=html_content[:10000])

        try:
            result = await self._provider.complete(
                messages=[{"role": "user", "content": prompt}],
                tier=ModelTier.SPECIALIST,
                max_tokens=4096,
                temperature=0.1,
            )

            content = result.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Data extraction failed: %s", e)
            return []

    async def _find_next_page(self, html_content: str) -> dict[str, Any]:
        """Use LLM to find pagination links."""
        prompt = PAGINATION_PROMPT.format(content=html_content[:5000])

        try:
            result = await self._provider.complete(
                messages=[{"role": "user", "content": prompt}],
                tier=ModelTier.EXECUTOR,
                max_tokens=256,
                temperature=0.1,
            )

            content = result.content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])

            return json.loads(content)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Pagination detection failed: %s", e)
            return {"has_next": False}

    @staticmethod
    def to_csv(items: list[dict[str, Any]]) -> str:
        """Convert items to CSV string."""
        if not items:
            return ""

        import csv
        import io

        output = io.StringIO()
        headers = list(items[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(items)
        return output.getvalue()

    @staticmethod
    def to_markdown(items: list[dict[str, Any]]) -> str:
        """Convert items to Markdown table."""
        if not items:
            return ""

        headers = list(items[0].keys())
        lines = ["| " + " | ".join(headers) + " |"]
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for item in items:
            row = [str(item.get(h, ""))[:50] for h in headers]
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)
