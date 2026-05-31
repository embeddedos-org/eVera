"""WWW Mode Intelligence Agent — full internet access.

Provides real-time web search, stock/crypto data, news aggregation,
weather, email, multi-LLM routing, and all internet-connected capabilities.
Only available in WWW mode.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Web Search
# ---------------------------------------------------------------------------


class WebSearchTool(Tool):
    """Search the web using DuckDuckGo (no API key required)."""

    def __init__(self):
        super().__init__(
            name="web_search",
            description=(
                "Search the internet for any topic. Returns titles, URLs, and snippets. "
                "Use for current events, facts, research, product info, news, etc."
            ),
            parameters={
                "query": {"type": "str", "description": "Search query"},
                "max_results": {"type": "int", "description": "Max results to return (default 10)"},
                "region": {"type": "str", "description": "Region code e.g. 'us-en', 'uk-en' (default us-en)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        query = kw.get("query", "")
        max_results = int(kw.get("max_results", 10))
        region = kw.get("region", "us-en")
        if not query:
            return {"status": "error", "message": "query is required"}
        try:
            from duckduckgo_search import DDGS  # type: ignore
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, region=region, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })
            return {"status": "success", "query": query, "results": results, "count": len(results)}
        except ImportError:
            return await self._fallback_search(query, max_results)
        except Exception as e:
            return await self._fallback_search(query, max_results)

    async def _fallback_search(self, query: str, max_results: int) -> dict[str, Any]:
        """Fallback: DuckDuckGo HTML scrape."""
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            import re
            results = []
            titles = re.findall(r'class="result__a"[^>]*>([^<]+)<', html)
            urls = re.findall(r'class="result__url"[^>]*>([^<]+)<', html)
            snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
            for i in range(min(max_results, len(titles))):
                results.append({
                    "title": titles[i] if i < len(titles) else "",
                    "url": urls[i].strip() if i < len(urls) else "",
                    "snippet": snippets[i] if i < len(snippets) else "",
                })
            return {"status": "success", "query": query, "results": results, "count": len(results)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Web Page Reader
# ---------------------------------------------------------------------------


class WebPageReaderTool(Tool):
    """Fetch and read the full content of any web page."""

    def __init__(self):
        super().__init__(
            name="read_webpage",
            description="Fetch and read the text content of any web page URL",
            parameters={
                "url": {"type": "str", "description": "URL to fetch"},
                "extract": {"type": "str", "description": "What to extract: text|links|images|all (default text)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        url = kw.get("url", "")
        extract = kw.get("extract", "text")
        if not url:
            return {"status": "error", "message": "url is required"}
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            try:
                from bs4 import BeautifulSoup  # type: ignore
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)[:10000]
                links = [a.get("href", "") for a in soup.find_all("a", href=True)][:50]
                images = [img.get("src", "") for img in soup.find_all("img", src=True)][:20]
                if extract == "text":
                    return {"status": "success", "url": url, "text": text}
                elif extract == "links":
                    return {"status": "success", "url": url, "links": links}
                elif extract == "images":
                    return {"status": "success", "url": url, "images": images}
                else:
                    return {"status": "success", "url": url, "text": text, "links": links, "images": images}
            except ImportError:
                import re
                text = re.sub(r"<[^>]+>", " ", html)
                text = re.sub(r"\s+", " ", text).strip()[:10000]
                return {"status": "success", "url": url, "text": text}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Stock & Crypto Data
# ---------------------------------------------------------------------------


class StockDataTool(Tool):
    """Get real-time stock prices, crypto rates, and financial data."""

    def __init__(self):
        super().__init__(
            name="stock_data",
            description=(
                "Get real-time stock prices, historical data, company info, crypto prices. "
                "Supports NYSE, NASDAQ, crypto (BTC, ETH, etc.)"
            ),
            parameters={
                "symbol": {"type": "str", "description": "Stock ticker or crypto symbol e.g. 'AAPL', 'NVDA', 'BTC-USD'"},
                "data_type": {"type": "str", "description": "price|history|info|news|crypto (default price)"},
                "period": {"type": "str", "description": "For history: 1d|5d|1mo|3mo|6mo|1y|2y|5y (default 1mo)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        symbol = kw.get("symbol", "").upper()
        data_type = kw.get("data_type", "price")
        period = kw.get("period", "1mo")
        if not symbol:
            return {"status": "error", "message": "symbol is required"}
        try:
            import yfinance as yf  # type: ignore
            ticker = yf.Ticker(symbol)
            if data_type == "price":
                info = ticker.fast_info
                return {
                    "status": "success",
                    "symbol": symbol,
                    "price": getattr(info, "last_price", None),
                    "change": getattr(info, "regular_market_previous_close", None),
                    "market_cap": getattr(info, "market_cap", None),
                    "volume": getattr(info, "three_month_average_volume", None),
                }
            elif data_type == "history":
                hist = ticker.history(period=period)
                records = []
                for date, row in hist.tail(30).iterrows():
                    records.append({
                        "date": str(date.date()),
                        "open": round(row["Open"], 4),
                        "high": round(row["High"], 4),
                        "low": round(row["Low"], 4),
                        "close": round(row["Close"], 4),
                        "volume": int(row["Volume"]),
                    })
                return {"status": "success", "symbol": symbol, "period": period, "history": records}
            elif data_type == "info":
                info = ticker.info
                keys = ["longName", "sector", "industry", "country", "website", "longBusinessSummary",
                        "marketCap", "trailingPE", "dividendYield", "52WeekHigh", "52WeekLow"]
                return {"status": "success", "symbol": symbol, "info": {k: info.get(k) for k in keys}}
            elif data_type == "news":
                news = ticker.news[:10]
                return {"status": "success", "symbol": symbol, "news": news}
            return {"status": "error", "message": f"Unknown data_type: {data_type}"}
        except ImportError:
            return await self._fallback_price(symbol)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _fallback_price(self, symbol: str) -> dict[str, Any]:
        """Fallback: Yahoo Finance JSON API."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            meta = data["chart"]["result"][0]["meta"]
            return {
                "status": "success",
                "symbol": symbol,
                "price": meta.get("regularMarketPrice"),
                "currency": meta.get("currency"),
                "exchange": meta.get("exchangeName"),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# News Aggregator
# ---------------------------------------------------------------------------


class NewsTool(Tool):
    """Get latest news from around the world."""

    def __init__(self):
        super().__init__(
            name="get_news",
            description="Get latest news headlines and articles on any topic",
            parameters={
                "topic": {"type": "str", "description": "Topic or keywords e.g. 'AI technology', 'stock market', 'sports'"},
                "category": {"type": "str", "description": "Category: general|business|technology|science|health|sports|entertainment"},
                "max_results": {"type": "int", "description": "Max articles to return (default 10)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        topic = kw.get("topic", "")
        category = kw.get("category", "general")
        max_results = int(kw.get("max_results", 10))
        query = topic or category
        try:
            from duckduckgo_search import DDGS  # type: ignore
            results = []
            with DDGS() as ddgs:
                for r in ddgs.news(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "source": r.get("source", ""),
                        "published": r.get("date", ""),
                        "summary": r.get("body", ""),
                    })
            return {"status": "success", "topic": query, "articles": results, "count": len(results)}
        except ImportError:
            return await self._rss_news(query, max_results)
        except Exception as e:
            return await self._rss_news(query, max_results)

    async def _rss_news(self, query: str, max_results: int) -> dict[str, Any]:
        """Fallback: Google News RSS."""
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            import re
            titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", content)
            links = re.findall(r"<link>(.+?)</link>", content)
            articles = []
            for i in range(min(max_results, len(titles))):
                articles.append({
                    "title": titles[i],
                    "url": links[i] if i < len(links) else "",
                })
            return {"status": "success", "topic": query, "articles": articles, "count": len(articles)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------


class WeatherTool(Tool):
    """Get current weather and forecasts for any location."""

    def __init__(self):
        super().__init__(
            name="get_weather",
            description="Get current weather conditions and forecast for any city or location",
            parameters={
                "location": {"type": "str", "description": "City name or coordinates e.g. 'New York', 'London', '40.7128,-74.0060'"},
                "days": {"type": "int", "description": "Forecast days 1-7 (default 3)"},
                "units": {"type": "str", "description": "metric|imperial (default metric)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        location = kw.get("location", "")
        days = int(kw.get("days", 3))
        units = kw.get("unit", "metric")
        if not location:
            return {"status": "error", "message": "location is required"}
        try:
            # wttr.in — free, no API key
            url = f"https://wttr.in/{urllib.parse.quote(location)}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            current = data["current_condition"][0]
            weather = {
                "location": location,
                "temperature_c": current.get("temp_C"),
                "temperature_f": current.get("temp_F"),
                "feels_like_c": current.get("FeelsLikeC"),
                "humidity": current.get("humidity"),
                "wind_speed_kmh": current.get("windspeedKmph"),
                "wind_direction": current.get("winddir16Point"),
                "description": current.get("weatherDesc", [{}])[0].get("value", ""),
                "visibility_km": current.get("visibility"),
                "uv_index": current.get("uvIndex"),
            }
            forecast = []
            for day in data.get("weather", [])[:days]:
                forecast.append({
                    "date": day.get("date"),
                    "max_c": day.get("maxtempC"),
                    "min_c": day.get("mintempC"),
                    "description": day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", ""),
                    "sunrise": day.get("astronomy", [{}])[0].get("sunrise"),
                    "sunset": day.get("astronomy", [{}])[0].get("sunset"),
                })
            return {"status": "success", "current": weather, "forecast": forecast}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Wikipedia / Knowledge Base
# ---------------------------------------------------------------------------


class WikipediaTool(Tool):
    """Search and read Wikipedia articles."""

    def __init__(self):
        super().__init__(
            name="wikipedia",
            description="Search Wikipedia and get article summaries or full content on any topic",
            parameters={
                "query": {"type": "str", "description": "Topic to search or article title"},
                "action": {"type": "str", "description": "search|summary|full (default summary)"},
                "language": {"type": "str", "description": "Language code e.g. 'en', 'es', 'fr' (default en)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        query = kw.get("query", "")
        action = kw.get("action", "summary")
        language = kw.get("language", "en")
        if not query:
            return {"status": "error", "message": "query is required"}
        try:
            base = f"https://{language}.wikipedia.org/api/rest_v1"
            if action == "search":
                url = f"https://{language}.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=5&format=json"
                req = urllib.request.Request(url, headers={"User-Agent": "eVera/2.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                results = [{"title": t, "url": u} for t, u in zip(data[1], data[3])]
                return {"status": "success", "results": results}
            else:
                url = f"{base}/page/summary/{urllib.parse.quote(query)}"
                req = urllib.request.Request(url, headers={"User-Agent": "eVera/2.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                if action == "summary":
                    return {
                        "status": "success",
                        "title": data.get("title"),
                        "summary": data.get("extract", "")[:3000],
                        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                        "image": data.get("thumbnail", {}).get("source", ""),
                    }
                else:
                    return {"status": "success", "title": data.get("title"), "content": data.get("extract", "")}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Currency & Crypto Exchange Rates
# ---------------------------------------------------------------------------


class CurrencyTool(Tool):
    """Get real-time currency exchange rates and crypto prices."""

    def __init__(self):
        super().__init__(
            name="currency_exchange",
            description="Get real-time currency exchange rates and cryptocurrency prices",
            parameters={
                "from_currency": {"type": "str", "description": "Source currency e.g. 'USD', 'EUR', 'BTC'"},
                "to_currency": {"type": "str", "description": "Target currency e.g. 'EUR', 'GBP', 'ETH'"},
                "amount": {"type": "float", "description": "Amount to convert (default 1)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        from_cur = kw.get("from_currency", "USD").upper()
        to_cur = kw.get("to_currency", "EUR").upper()
        amount = float(kw.get("amount", 1))
        try:
            url = f"https://api.exchangerate-api.com/v4/latest/{from_cur}"
            req = urllib.request.Request(url, headers={"User-Agent": "eVera/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            rate = data.get("rates", {}).get(to_cur)
            if rate is None:
                return {"status": "error", "message": f"Currency {to_cur} not found"}
            converted = round(amount * rate, 6)
            return {
                "status": "success",
                "from": from_cur,
                "to": to_cur,
                "rate": rate,
                "amount": amount,
                "converted": converted,
                "date": data.get("date"),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Email (IMAP/SMTP)
# ---------------------------------------------------------------------------


class EmailTool(Tool):
    """Read and send emails via IMAP/SMTP."""

    def __init__(self):
        super().__init__(
            name="email",
            description="Read inbox, search emails, send emails via IMAP/SMTP",
            parameters={
                "action": {"type": "str", "description": "read_inbox|search|send|read_email"},
                "server": {"type": "str", "description": "IMAP/SMTP server e.g. 'imap.gmail.com'"},
                "username": {"type": "str", "description": "Email address"},
                "password": {"type": "str", "description": "Password or app password"},
                "to": {"type": "str", "description": "Recipient email (for send)"},
                "subject": {"type": "str", "description": "Email subject (for send)"},
                "body": {"type": "str", "description": "Email body (for send)"},
                "query": {"type": "str", "description": "Search query (for search)"},
                "max_results": {"type": "int", "description": "Max emails to return (default 10)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        action = kw.get("action", "read_inbox")
        server = kw.get("server", "")
        username = kw.get("username", "")
        password = kw.get("password", "")
        max_results = int(kw.get("max_results", 10))
        if not server or not username or not password:
            return {"status": "error", "message": "server, username, and password are required"}
        try:
            if action in ("read_inbox", "search"):
                import imaplib
                import email as email_lib
                imap = imaplib.IMAP4_SSL(server)
                imap.login(username, password)
                imap.select("INBOX")
                query = kw.get("query", "ALL")
                if action == "search" and query:
                    _, msg_ids = imap.search(None, f'SUBJECT "{query}"')
                else:
                    _, msg_ids = imap.search(None, "ALL")
                ids = msg_ids[0].split()[-max_results:]
                emails = []
                for msg_id in reversed(ids):
                    _, msg_data = imap.fetch(msg_id, "(RFC822)")
                    msg = email_lib.message_from_bytes(msg_data[0][1])
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode("utf-8", errors="replace")[:1000]
                                break
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:1000]
                    emails.append({
                        "from": msg.get("From"),
                        "subject": msg.get("Subject"),
                        "date": msg.get("Date"),
                        "body": body,
                    })
                imap.logout()
                return {"status": "success", "emails": emails, "count": len(emails)}

            elif action == "send":
                import smtplib
                from email.mime.text import MIMEText
                to = kw.get("to", "")
                subject = kw.get("subject", "")
                body = kw.get("body", "")
                if not to or not subject:
                    return {"status": "error", "message": "to and subject are required for send"}
                smtp_server = server.replace("imap.", "smtp.")
                msg = MIMEText(body)
                msg["Subject"] = subject
                msg["From"] = username
                msg["To"] = to
                with smtplib.SMTP_SSL(smtp_server, 465) as smtp:
                    smtp.login(username, password)
                    smtp.sendmail(username, [to], msg.as_string())
                return {"status": "success", "message": f"Email sent to {to}"}

            return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# WWW Agent
# ---------------------------------------------------------------------------


class WWWAgent(BaseAgent):
    """WWW mode intelligence — full internet access.

    Provides web search, stock data, news, weather, Wikipedia,
    currency exchange, email, and all internet-connected capabilities.
    Only available in WWW mode.
    """

    name = "www_intelligence"
    description = (
        "Full internet access: web search, stock/crypto prices, news, weather, "
        "Wikipedia, currency exchange, email, and any online data source"
    )
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are eVera's WWW Intelligence Agent. You have full access to the internet. "
        "You can search the web, get real-time stock prices, read news, check weather, "
        "look up Wikipedia articles, convert currencies, read and send emails, and access "
        "any public web service. Always cite your sources and provide accurate, up-to-date information."
    )

    def _setup_tools(self):
        self._tools = [
            WebSearchTool(),
            WebPageReaderTool(),
            StockDataTool(),
            NewsTool(),
            WeatherTool(),
            WikipediaTool(),
            CurrencyTool(),
            EmailTool(),
        ]
