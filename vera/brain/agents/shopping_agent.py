"""Shopping Agent -- product search, price compare, deals, wish lists, reviews."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class ProductSearchTool(Tool):
    def __init__(self):
        super().__init__(
            name="product_search",
            description="Search products across stores",
            parameters={
                "query": {"type": "str", "description": "Product query"},
                "max_results": {"type": "int", "description": "Max results"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(d.text(f"{kw.get('query', '')} buy price", max_results=kw.get("max_results", 5)))
            return {
                "status": "success",
                "products": [{"title": r["title"], "url": r["href"], "info": r.get("body", "")} for r in results],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class PriceCompareTool(Tool):
    def __init__(self):
        super().__init__(
            name="price_compare",
            description="Compare prices across retailers",
            parameters={"product": {"type": "str", "description": "Product name"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(d.text(f"{kw['product']} price comparison best deal", max_results=8))
            return {
                "status": "success",
                "comparisons": [{"store": r["title"], "url": r["href"], "info": r.get("body", "")} for r in results],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class DealFinderTool(Tool):
    def __init__(self):
        super().__init__(
            name="deal_finder",
            description="Find deals, coupons, discounts",
            parameters={"query": {"type": "str", "description": "Product/store for deals"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(d.text(f"{kw['query']} coupon deal discount 2025", max_results=5))
            return {"status": "success", "deals": [{"title": r["title"], "url": r["href"]} for r in results]}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WishListTool(Tool):
    def __init__(self):
        super().__init__(
            name="wish_list",
            description="Manage wish list",
            parameters={
                "action": {"type": "str", "description": "add|remove|list|clear"},
                "item": {"type": "str", "description": "Item name"},
                "price": {"type": "str", "description": "Price"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        from datetime import datetime

        wl = Path("data/wish_list.json")
        wl.parent.mkdir(parents=True, exist_ok=True)
        items = json.loads(wl.read_text()) if wl.exists() else []
        a = kw.get("action", "list")
        if a == "add":
            items.append(
                {"item": kw.get("item", ""), "price": kw.get("price", ""), "added": datetime.now().isoformat()}
            )
            wl.write_text(json.dumps(items, indent=2))
            return {"status": "success", "added": kw.get("item", ""), "total": len(items)}
        elif a == "remove":
            items = [i for i in items if i["item"] != kw.get("item", "")]
            wl.write_text(json.dumps(items, indent=2))
            return {"status": "success", "removed": True}
        elif a == "clear":
            wl.write_text("[]")
            return {"status": "success", "cleared": True}
        return {"status": "success", "items": items}


class ProductReviewTool(Tool):
    def __init__(self):
        super().__init__(
            name="product_review",
            description="Find product reviews",
            parameters={"product": {"type": "str", "description": "Product name"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(d.text(f"{kw['product']} review rating 2025", max_results=5))
            return {
                "status": "success",
                "reviews": [{"title": r["title"], "url": r["href"], "info": r.get("body", "")} for r in results],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ShoppingAgent(BaseAgent):
    name = "shopping"
    description = "Product search, price comparison, deal finder, wish lists, product reviews"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are eVera's Shopping Agent. Search products, compare prices, find deals, manage wish lists, find reviews."
    )
    offline_responses = {
        "buy": "\U0001f6d2 Searching!",
        "deal": "\U0001f4b0 Finding deals!",
        "price": "\U0001f4b2 Comparing!",
        "shop": "\U0001f6cd Shopping!",
    }

    def _setup_tools(self):
        self._tools = [ProductSearchTool(), PriceCompareTool(), DealFinderTool(), WishListTool(), ProductReviewTool()]
