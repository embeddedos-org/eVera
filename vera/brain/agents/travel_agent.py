"""Travel Agent -- flights, hotels, currency, weather, packing, itineraries."""

from __future__ import annotations

import logging
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class FlightSearchTool(Tool):
    def __init__(self):
        super().__init__(
            name="flight_search",
            description="Search flights between cities",
            parameters={
                "origin": {"type": "str", "description": "Origin city"},
                "destination": {"type": "str", "description": "Destination city"},
                "date": {"type": "str", "description": "Date YYYY-MM-DD"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(
                    d.text(f"flights {kw['origin']} to {kw['destination']} {kw.get('date', '')} price", max_results=5)
                )
            return {
                "status": "success",
                "flights": [{"title": r["title"], "url": r["href"], "info": r.get("body", "")} for r in results],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class HotelSearchTool(Tool):
    def __init__(self):
        super().__init__(
            name="hotel_search",
            description="Search hotels in a city",
            parameters={
                "city": {"type": "str", "description": "City"},
                "checkin": {"type": "str", "description": "Check-in date"},
                "checkout": {"type": "str", "description": "Check-out date"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(d.text(f"hotels {kw['city']} {kw.get('checkin', '')} best deals", max_results=5))
            return {
                "status": "success",
                "hotels": [{"title": r["title"], "url": r["href"], "info": r.get("body", "")} for r in results],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class CurrencyConvertTool(Tool):
    def __init__(self):
        super().__init__(
            name="currency_convert",
            description="Convert between currencies",
            parameters={
                "amount": {"type": "float", "description": "Amount"},
                "from_currency": {"type": "str", "description": "Source (USD)"},
                "to_currency": {"type": "str", "description": "Target (EUR)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"https://api.exchangerate-api.com/v4/latest/{kw.get('from_currency', 'USD')}")
                rate = r.json().get("rates", {}).get(kw.get("to_currency", "EUR"), 1)
            return {
                "status": "success",
                "amount": kw.get("amount", 1),
                "from": kw.get("from_currency", "USD"),
                "to": kw.get("to_currency", "EUR"),
                "rate": rate,
                "converted": round(kw.get("amount", 1) * rate, 2),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class WeatherTool(Tool):
    def __init__(self):
        super().__init__(
            name="weather_check",
            description="Check weather for a location",
            parameters={"location": {"type": "str", "description": "City name"}},
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"https://wttr.in/{kw.get('location', 'London')}?format=j1")
                cur = r.json().get("current_condition", [{}])[0]
            return {
                "status": "success",
                "location": kw.get("location", ""),
                "temp_c": cur.get("temp_C"),
                "temp_f": cur.get("temp_F"),
                "desc": cur.get("weatherDesc", [{}])[0].get("value", ""),
                "humidity": cur.get("humidity"),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class PackingListTool(Tool):
    def __init__(self):
        super().__init__(
            name="packing_list",
            description="Generate packing list for trip",
            parameters={
                "destination": {"type": "str", "description": "Destination"},
                "trip_type": {"type": "str", "description": "business|beach|adventure|winter|city"},
                "duration_days": {"type": "int", "description": "Trip duration"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        tt = kw.get("trip_type", "city")
        days = kw.get("duration_days", 5)
        base = ["Passport/ID", "Phone charger", "Toiletries", "Medications"]
        extras = {
            "business": ["Laptop", "Formal attire", "Business cards"],
            "beach": ["Swimsuit", "Sunscreen", "Sunglasses", "Flip flops"],
            "adventure": ["Hiking boots", "Backpack", "First aid kit", "Rain jacket"],
            "winter": ["Heavy coat", "Gloves", "Scarf", "Thermal underwear"],
            "city": ["Walking shoes", "Day bag", "Camera", "Umbrella"],
        }.get(tt, [])
        return {
            "status": "success",
            "essentials": base,
            "trip_specific": extras,
            "clothing": [f"{min(days, 7)} underwear", f"{min(days, 5)} shirts", f"{min(days, 3)} pants"],
        }


class ItineraryTool(Tool):
    def __init__(self):
        super().__init__(
            name="create_itinerary",
            description="Create travel itinerary",
            parameters={
                "destination": {"type": "str", "description": "Destination"},
                "duration_days": {"type": "int", "description": "Trip length"},
                "interests": {"type": "str", "description": "Interests (food,history,nature)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as d:
                results = list(
                    d.text(
                        f"top things to do {kw['destination']} {kw.get('duration_days', 3)} day itinerary",
                        max_results=5,
                    )
                )
            return {
                "status": "success",
                "destination": kw["destination"],
                "suggestions": [r["body"][:200] for r in results if r.get("body")],
                "sources": [r["href"] for r in results],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class TravelAgent(BaseAgent):
    name = "travel"
    description = "Flight/hotel search, currency conversion, weather, packing lists, itinerary planning"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Travel Agent. Search flights/hotels, convert currency, check weather, generate packing lists, create itineraries."
    offline_responses = {
        "flight": "\u2708 Searching flights!",
        "hotel": "\U0001f3e8 Finding hotels!",
        "travel": "\U0001f30d Planning trip!",
        "weather": "\u26c5 Checking weather!",
    }

    def _setup_tools(self):
        self._tools = [
            FlightSearchTool(),
            HotelSearchTool(),
            CurrencyConvertTool(),
            WeatherTool(),
            PackingListTool(),
            ItineraryTool(),
        ]
