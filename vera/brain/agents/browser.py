"""Browser Agent — automates web browsing, form filling, login, and web tasks.

Uses Playwright for real browser automation. Can navigate sites, click buttons,
fill forms, extract content, handle logins, and complete tasks on websites.

Install: pip install playwright && python -m playwright install chromium
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
COOKIES_DIR = DATA_DIR / "browser_sessions"


def _ensure_dirs():
    COOKIES_DIR.mkdir(parents=True, exist_ok=True)


# --- Playwright auto-install ---

_playwright_ready = False


def _ensure_playwright() -> bool:
    """Auto-install Playwright and Chromium if not available. Runs once per session."""
    global _playwright_ready
    if _playwright_ready:
        return True

    try:
        import playwright  # noqa: F401

        _playwright_ready = True
        return True
    except ImportError:
        logger.info("Playwright not installed — auto-installing...")

    import subprocess
    import sys

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "playwright"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
        )
        _playwright_ready = True
        logger.info("Playwright + Chromium installed successfully")
        return True
    except Exception as e:
        logger.error("Playwright auto-install failed: %s", e)
        return False


# --- Shared browser state ---

_browser_state = {
    "browser": None,
    "context": None,
    "page": None,
}


async def _get_page():
    """Get or create a Playwright browser page with persistent session."""
    if _browser_state["page"] and not _browser_state["page"].is_closed():
        return _browser_state["page"]

    if not _ensure_playwright():
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"
        )

    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    _ensure_dirs()

    _browser_state["browser"] = await pw.chromium.launch(
        headless=False,  # Visible browser so user can see what's happening
        args=["--disable-blink-features=AutomationControlled"],
    )

    # Use persistent context with saved cookies
    _browser_state["context"] = await _browser_state["browser"].new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )

    # Load saved cookies if they exist
    cookies_file = COOKIES_DIR / "cookies.json"
    if cookies_file.exists():
        try:
            cookies = json.loads(cookies_file.read_text())
            await _browser_state["context"].add_cookies(cookies)
            logger.info("Loaded %d saved cookies", len(cookies))
        except Exception as e:
            logger.warning("Failed to load cookies: %s", e)

    _browser_state["page"] = await _browser_state["context"].new_page()
    return _browser_state["page"]


async def _save_cookies():
    """Save browser cookies for session persistence."""
    if _browser_state["context"]:
        try:
            _ensure_dirs()
            cookies = await _browser_state["context"].cookies()
            (COOKIES_DIR / "cookies.json").write_text(json.dumps(cookies, indent=2))
            logger.info("Saved %d cookies", len(cookies))
        except Exception as e:
            logger.warning("Failed to save cookies: %s", e)


# --- Tool implementations ---


class NavigateTool(Tool):
    """Navigate to a URL."""

    def __init__(self) -> None:
        super().__init__(
            name="navigate",
            description="Navigate the browser to a URL",
            parameters={
                "url": {"type": "str", "description": "URL to navigate to (e.g. https://google.com)"},
                "wait_for": {
                    "type": "str",
                    "description": "Wait condition: load, domcontentloaded, networkidle (default: load)",
                },
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        url = kwargs.get("url", "")
        wait_for = kwargs.get("wait_for", "load")

        if not url:
            return {"status": "error", "message": "No URL provided"}
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            page = await _get_page()
            await page.goto(url, wait_until=wait_for, timeout=30000)
            await _save_cookies()

            title = await page.title()
            current_url = page.url
            return {
                "status": "success",
                "url": current_url,
                "title": title,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ClickTool(Tool):
    """Click an element on the page."""

    def __init__(self) -> None:
        super().__init__(
            name="click",
            description="Click an element on the page by text content, CSS selector, or role",
            parameters={
                "target": {"type": "str", "description": "Text content, CSS selector, or aria role to click"},
                "selector_type": {"type": "str", "description": "Type: text, css, role (default: text)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        target = kwargs.get("target", "")
        selector_type = kwargs.get("selector_type", "text").lower()

        if not target:
            return {"status": "error", "message": "No target provided"}

        try:
            page = await _get_page()

            if selector_type == "css":
                await page.click(target, timeout=10000)
            elif selector_type == "role":
                await page.get_by_role(target).click(timeout=10000)
            else:
                # Try text first, then CSS fallback
                try:
                    await page.get_by_text(target, exact=False).first.click(timeout=5000)
                except Exception:
                    try:
                        await page.click(f'text="{target}"', timeout=5000)
                    except Exception:
                        await page.click(f'[aria-label*="{target}" i]', timeout=5000)

            await page.wait_for_load_state("domcontentloaded")
            await _save_cookies()

            return {
                "status": "success",
                "clicked": target,
                "current_url": page.url,
                "title": await page.title(),
            }
        except Exception as e:
            return {"status": "error", "message": f"Could not click '{target}': {e}"}


class FillFormTool(Tool):
    """Fill a form field with text."""

    def __init__(self) -> None:
        super().__init__(
            name="fill_form",
            description="Fill a form field (input, textarea) with text",
            parameters={
                "field": {"type": "str", "description": "Field identifier: name, placeholder, label, or CSS selector"},
                "value": {"type": "str", "description": "Text value to fill in"},
                "submit": {"type": "bool", "description": "Press Enter after filling (default: false)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        field_id = kwargs.get("field", "")
        value = kwargs.get("value", "")
        submit = kwargs.get("submit", False)

        if not field_id:
            return {"status": "error", "message": "No field identifier provided"}

        try:
            page = await _get_page()

            # Try multiple strategies to find the field
            filled = False
            strategies = [
                lambda: page.get_by_placeholder(field_id, exact=False).first,
                lambda: page.get_by_label(field_id, exact=False).first,
                lambda: page.locator(f'input[name="{field_id}"]').first,
                lambda: page.locator(f'input[type="{field_id}"]').first,
                lambda: page.locator(field_id).first,
            ]

            for strategy in strategies:
                try:
                    locator = strategy()
                    await locator.fill(value, timeout=5000)
                    filled = True
                    break
                except Exception:
                    continue

            if not filled:
                return {"status": "error", "message": f"Could not find field: {field_id}"}

            if submit:
                await page.keyboard.press("Enter")
                await page.wait_for_load_state("domcontentloaded")

            await _save_cookies()
            return {"status": "success", "field": field_id, "filled": True, "submitted": submit}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ExtractTextTool(Tool):
    """Extract text content from the current page."""

    def __init__(self) -> None:
        super().__init__(
            name="extract_text",
            description="Extract text content from the current webpage",
            parameters={
                "selector": {"type": "str", "description": "CSS selector to extract from (default: body)"},
                "max_length": {"type": "int", "description": "Maximum text length (default: 5000)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        selector = kwargs.get("selector", "body")
        max_length = kwargs.get("max_length", 5000)

        try:
            page = await _get_page()
            text = await page.inner_text(selector, timeout=10000)
            text = text.strip()

            if len(text) > max_length:
                text = text[:max_length] + "... [truncated]"

            return {
                "status": "success",
                "url": page.url,
                "title": await page.title(),
                "text": text,
                "length": len(text),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class PageScreenshotTool(Tool):
    """Take a screenshot of the current page."""

    def __init__(self) -> None:
        super().__init__(
            name="page_screenshot",
            description="Take a screenshot of the current browser page",
            parameters={
                "full_page": {"type": "bool", "description": "Capture full scrollable page (default: false)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        full_page = kwargs.get("full_page", False)

        try:
            page = await _get_page()
            _ensure_dirs()
            path = str(COOKIES_DIR / "page_screenshot.png")
            await page.screenshot(path=path, full_page=full_page)

            return {
                "status": "success",
                "path": path,
                "url": page.url,
                "title": await page.title(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class AnalyzePageTool(Tool):
    """Analyze the current page using vision LLM to understand layout and content."""

    def __init__(self) -> None:
        super().__init__(
            name="analyze_page",
            description="Use AI vision to analyze what's on the current browser page",
            parameters={
                "question": {"type": "str", "description": "What to look for on the page"},
            },
        )
        self._screenshot = PageScreenshotTool()

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        question = kwargs.get(
            "question", "Describe the page layout and main content. List all clickable buttons and links."
        )

        shot_result = await self._screenshot.execute(full_page=False)
        if shot_result.get("status") != "success":
            return shot_result

        try:
            with open(shot_result["path"], "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()

            import litellm

            from config import settings

            models = []
            if settings.llm.openai_api_key:
                models.append("gpt-4o")
            if settings.llm.gemini_api_key:
                models.append("gemini/gemini-2.0-flash")

            if not models:
                return {"status": "error", "message": "No vision LLM configured"}

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    ],
                }
            ]

            for model in models:
                try:
                    resp = await litellm.acompletion(model=model, messages=messages, max_tokens=1024)
                    return {
                        "status": "success",
                        "analysis": resp.choices[0].message.content,
                        "url": shot_result.get("url"),
                        "model": model,
                    }
                except Exception:
                    continue

            return {"status": "error", "message": "All vision models failed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class GetPageElementsTool(Tool):
    """List interactive elements on the current page."""

    def __init__(self) -> None:
        super().__init__(
            name="get_page_elements",
            description="List all interactive elements (links, buttons, inputs) on the page",
            parameters={
                "element_type": {
                    "type": "str",
                    "description": "Type to list: all, links, buttons, inputs (default: all)",
                },
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        element_type = kwargs.get("element_type", "all").lower()

        try:
            page = await _get_page()

            elements = []

            if element_type in ("all", "links"):
                links = await page.eval_on_selector_all(
                    "a[href]",
                    "els => els.slice(0, 30).map(el => ({type: 'link', text: el.innerText.trim().substring(0, 80), href: el.href}))",
                )
                elements.extend(links)

            if element_type in ("all", "buttons"):
                buttons = await page.eval_on_selector_all(
                    "button, [role='button'], input[type='submit']",
                    "els => els.slice(0, 20).map(el => ({type: 'button', text: (el.innerText || el.value || el.ariaLabel || '').trim().substring(0, 80)}))",
                )
                elements.extend(buttons)

            if element_type in ("all", "inputs"):
                inputs = await page.eval_on_selector_all(
                    "input:not([type='hidden']):not([type='submit']), textarea, select",
                    """els => els.slice(0, 20).map(el => ({
                        type: 'input',
                        input_type: el.type || el.tagName.toLowerCase(),
                        name: el.name || '',
                        placeholder: el.placeholder || '',
                        label: el.ariaLabel || '',
                        value: el.value ? el.value.substring(0, 50) : ''
                    }))""",
                )
                elements.extend(inputs)

            return {
                "status": "success",
                "url": page.url,
                "elements": elements,
                "count": len(elements),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class LoginTool(Tool):
    """Login to a website using saved or provided credentials."""

    def __init__(self) -> None:
        super().__init__(
            name="login",
            description="Login to a website. Uses saved credentials or provided ones.",
            parameters={
                "site": {"type": "str", "description": "Site name or URL to login to"},
                "username": {"type": "str", "description": "Username or email (optional if saved)"},
                "password": {"type": "str", "description": "Password (optional if saved)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        site = kwargs.get("site", "")
        username = kwargs.get("username", "")
        password = kwargs.get("password", "")

        if not site:
            return {"status": "error", "message": "No site provided"}

        # Check saved credentials (encrypted)
        _ensure_dirs()
        from vera.memory.secure import SecureVault

        vault = SecureVault(vault_path=COOKIES_DIR / "creds.enc")

        site_key = site.lower().replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

        if not username:
            saved_user = vault.retrieve(f"{site_key}_user")
            saved_pass = vault.retrieve(f"{site_key}_pass")
            if saved_user and saved_pass:
                username = saved_user
                password = saved_pass

        if not username or not password:
            return {
                "status": "needs_credentials",
                "message": f"I need login credentials for {site}. Please provide your username and password.",
                "site": site,
            }

        # Save credentials encrypted for next time
        vault.store(f"{site_key}_user", username)
        vault.store(f"{site_key}_pass", password)

        # Login flow
        try:
            page = await _get_page()

            # Common login URLs
            login_urls = {
                "google": "https://accounts.google.com",
                "facebook": "https://www.facebook.com/login",
                "twitter": "https://twitter.com/login",
                "x": "https://twitter.com/login",
                "instagram": "https://www.instagram.com/accounts/login",
                "linkedin": "https://www.linkedin.com/login",
                "github": "https://github.com/login",
                "reddit": "https://www.reddit.com/login",
                "youtube": "https://accounts.google.com",
            }

            url = login_urls.get(site_key, site if site.startswith("http") else f"https://{site}/login")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Try to fill login form — common field names
            username_selectors = [
                'input[name="username"]',
                'input[name="email"]',
                'input[name="login"]',
                'input[name="identifier"]',
                'input[type="email"]',
                'input[name="user"]',
                'input[id="username"]',
                'input[id="email"]',
                'input[id="login_field"]',
            ]
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                'input[id="password"]',
                'input[name="pass"]',
            ]

            # Fill username
            filled_user = False
            for sel in username_selectors:
                try:
                    await page.fill(sel, username, timeout=3000)
                    filled_user = True
                    break
                except Exception:
                    continue

            if not filled_user:
                return {"status": "error", "message": "Could not find username field on login page"}

            # Some sites have two-step login (username then password)
            try:
                submit = await page.query_selector('button[type="submit"], input[type="submit"]')
                if submit:
                    password_field = await page.query_selector('input[type="password"]')
                    if not password_field or not await password_field.is_visible():
                        await submit.click()
                        await page.wait_for_load_state("domcontentloaded")
                        await page.wait_for_timeout(1500)
            except Exception:
                pass

            # Fill password
            filled_pass = False
            for sel in password_selectors:
                try:
                    await page.fill(sel, password, timeout=3000)
                    filled_pass = True
                    break
                except Exception:
                    continue

            if not filled_pass:
                return {"status": "error", "message": "Could not find password field"}

            # Submit
            try:
                await page.click('button[type="submit"], input[type="submit"]', timeout=5000)
            except Exception:
                await page.keyboard.press("Enter")

            await page.wait_for_load_state("networkidle", timeout=15000)
            await _save_cookies()

            return {
                "status": "success",
                "site": site,
                "url": page.url,
                "title": await page.title(),
                "message": f"Logged into {site}!",
            }
        except Exception as e:
            return {"status": "error", "message": f"Login failed: {e}"}


class ScrollTool(Tool):
    """Scroll the page up or down."""

    def __init__(self) -> None:
        super().__init__(
            name="scroll",
            description="Scroll the page up or down",
            parameters={
                "direction": {"type": "str", "description": "Direction: up, down, top, bottom"},
                "amount": {"type": "int", "description": "Pixels to scroll (default: 500)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        direction = kwargs.get("direction", "down").lower()
        amount = kwargs.get("amount", 500)

        try:
            page = await _get_page()

            if direction == "top":
                await page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "up":
                await page.evaluate(f"window.scrollBy(0, -{amount})")
            else:
                await page.evaluate(f"window.scrollBy(0, {amount})")

            return {"status": "success", "direction": direction}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class TypeInBrowserTool(Tool):
    """Type text into the browser, optionally with keyboard shortcuts."""

    def __init__(self) -> None:
        super().__init__(
            name="type_in_browser",
            description="Type text or press keyboard shortcuts in the browser",
            parameters={
                "text": {"type": "str", "description": "Text to type or key combo (e.g. 'Enter', 'Control+a', 'Tab')"},
                "is_key": {"type": "bool", "description": "If true, treat as keyboard shortcut (default: false)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        text = kwargs.get("text", "")
        is_key = kwargs.get("is_key", False)

        if not text:
            return {"status": "error", "message": "No text provided"}

        try:
            page = await _get_page()
            if is_key:
                await page.keyboard.press(text)
            else:
                await page.keyboard.type(text, delay=50)

            return {"status": "success", "typed": text[:50], "is_key": is_key}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class GoBackTool(Tool):
    """Go back or forward in browser history."""

    def __init__(self) -> None:
        super().__init__(
            name="go_back",
            description="Go back or forward in browser history",
            parameters={
                "direction": {"type": "str", "description": "back or forward (default: back)"},
            },
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        direction = kwargs.get("direction", "back").lower()
        try:
            page = await _get_page()
            if direction == "forward":
                await page.go_forward()
            else:
                await page.go_back()
            await page.wait_for_load_state("domcontentloaded")
            return {"status": "success", "url": page.url, "title": await page.title()}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# --- Browser Agent ---


class BrowserAgent(BaseAgent):
    """Automates web browsing — navigates sites, fills forms, logs in, completes tasks."""

    name = "browser"
    description = "Automates web browsing, form filling, login, social media, and web tasks"
    tier = ModelTier.SPECIALIST
    system_prompt = (
        "You are a web browsing assistant. You can control a real browser to help the user "
        "with any website task: searching, logging in, posting on social media, filling forms, "
        "reading content, and more.\n\n"
        "Workflow for any web task:\n"
        "1. Use navigate() to go to the website\n"
        "2. Use get_page_elements() to see what's on the page (links, buttons, inputs)\n"
        "3. Use fill_form() for text inputs and click() for buttons/links\n"
        "4. Use extract_text() to read page content\n"
        "5. Use analyze_page() if you need vision to understand complex layouts\n\n"
        "For login: use login() with the site name — it handles common login flows.\n"
        "For social media posts: navigate to the site, find the post/compose box, fill it, and click post.\n\n"
        "Always tell the user what you're doing step by step.\n"
        "NEVER share credentials in chat — handle them securely via the login tool.\n"
        "Ask for confirmation before submitting important forms or posting content."
    )

    offline_responses = {
        "browse": "🌐 I can browse the web for you! Connect an LLM and I'll navigate any site!",
        "login": "🔐 I can log you in! Just tell me which site.",
        "post": "📝 I can post for you! Tell me what and where.",
        "website": "🌐 I can interact with any website for you!",
        "social": "📱 I can help with social media! What would you like to do?",
    }

    def _setup_tools(self) -> None:
        self._tools = [
            NavigateTool(),
            ClickTool(),
            FillFormTool(),
            ExtractTextTool(),
            PageScreenshotTool(),
            AnalyzePageTool(),
            GetPageElementsTool(),
            LoginTool(),
            ScrollTool(),
            TypeInBrowserTool(),
            GoBackTool(),
        ]
