# 🤖 Agents Reference

eVoca ships with 10 specialized agents, each designed for a specific domain. All agents extend `BaseAgent` and use the same tool calling framework.

---

## 💬 Companion Agent

**File:** `voca/brain/agents/companion.py`
**Tier:** Executor (Ollama local)
**Description:** Casual conversation, emotional support, jokes, mood checks.

| Tool | Description |
|------|-------------|
| `chat` | Open-ended conversation |
| `tell_joke` | Generate a joke |
| `check_mood` | Empathetic mood check-in |
| `suggest_activity` | Suggest fun activities based on mood |

**Example:**
```
User: "Hey Voca, I'm feeling bored"
Voca: "I feel you! 😄 How about: 🎮 Try a new game, 📚 Start that book, 🎨 Do some creative sketching, or 🎵 Discover new music? What sounds fun?"
```

---

## 💻 Operator Agent

**File:** `voca/brain/agents/operator.py`
**Tier:** Specialist (GPT-4o-mini)
**Description:** Full PC automation — apps, scripts, files, mouse, keyboard, windows, processes, system info.

| Tool | Description |
|------|-------------|
| `open_application` | Open apps by name (cross-platform maps) |
| `execute_script` | Run shell/Python/PowerShell commands safely |
| `manage_files` | Copy, move, delete, list, mkdir, info |
| `take_screenshot` | Capture screen |
| `type_text` | Type text into focused window |
| `screen_capture` | Capture screen for AI analysis |
| `analyze_screen` | AI vision analysis of screen content |
| `ocr_screen` | OCR text extraction from screen |
| `mouse_click` | Click at screen coordinates |
| `mouse_move` | Move cursor to coordinates |
| `mouse_drag` | Click and drag between points |
| `scroll` | Scroll mouse wheel |
| `press_hotkey` | Press keyboard shortcuts |
| `manage_window` | List, focus, minimize, maximize, close windows |
| `manage_process` | List, inspect, kill processes |
| `system_info` | CPU, memory, disk, battery, OS details |
| `manage_service` | List, start, stop, restart services |
| `network_info` | IP, connections, ping |
| `clipboard` | Read/write system clipboard |
| `send_notification` | OS-level desktop notification |

**Example:**
```
User: "Open Chrome and click at 500, 300"
Voca: "Done! ✅ Opening Chrome for you! 🚀"
```

---

## 🌐 Browser Agent

**File:** `voca/brain/agents/browser.py`
**Tier:** Specialist (GPT-4o-mini)
**Description:** Web automation via Playwright — navigate, login, fill forms, post on social media.

| Tool | Description |
|------|-------------|
| `navigate` | Go to a URL |
| `click` | Click an element on the page |
| `fill_form` | Fill form fields |
| `login` | Login to a website |
| `type_in_browser` | Type text into browser elements |
| `extract_text` | Extract text from page |
| `page_screenshot` | Screenshot current page |
| `analyze_page` | AI analysis of page content |
| `get_page_elements` | List interactive elements |
| `scroll` | Scroll the page |
| `go_back` | Navigate back |

**Example:**
```
User: "Go to twitter.com and post 'Hello world!'"
Voca: "I'll need to log in first. Should I go ahead? 🤔 (yes/no)"
```

---

## 🔍 Researcher Agent

**File:** `voca/brain/agents/researcher.py`
**Tier:** Specialist (GPT-4o-mini)
**Description:** Web search, URL summarization, academic papers, fact-checking.

| Tool | Description |
|------|-------------|
| `web_search` | DuckDuckGo search (no API key needed) |
| `summarize_url` | Summarize content from a URL |
| `search_papers` | Search arXiv for academic papers |
| `fact_check` | Verify claims against multiple sources |

---

## ✍️ Writer Agent

**File:** `voca/brain/agents/writer.py`
**Tier:** Specialist (GPT-4o-mini)
**Description:** Draft, edit, format, and translate text.

| Tool | Description |
|------|-------------|
| `draft_text` | Draft text content (email, blog, report) |
| `edit_text` | Edit and improve existing text |
| `format_document` | Format text (markdown, HTML) |
| `translate` | Translate between languages |

---

## 📅 Life Manager Agent

**File:** `voca/brain/agents/life_manager.py`
**Tier:** Specialist (GPT-4o-mini)
**Description:** Calendar, reminders, to-do lists, email.

| Tool | Description |
|------|-------------|
| `check_calendar` | View upcoming events |
| `add_event` | Create calendar event |
| `create_reminder` | Set a reminder with time |
| `list_todos` / `add_todo` | Manage to-do list |
| `send_email` | Send email via SMTP |

---

## 🏠 Home Controller Agent

**File:** `voca/brain/agents/home_controller.py`
**Tier:** Executor (Ollama local)
**Description:** Smart home device control via Home Assistant API.

| Tool | Description |
|------|-------------|
| `control_light` | Turn lights on/off, set brightness/color |
| `set_thermostat` | Set temperature |
| `lock_door` | Lock/unlock doors |
| `check_security` | Check security system status |
| `play_media` | Control media playback |
| `set_scene` | Activate predefined scenes |

---

## 📈 Income Agent

**File:** `voca/brain/agents/income.py` + `voca/brain/agents/brokers.py`
**Tier:** Strategist (GPT-4o)
**Description:** Stock market monitoring, paper trading, and real broker integration.

| Tool | Description |
|------|-------------|
| `get_stock_price` | Real-time stock quotes (yfinance) |
| `get_stock_history` | Historical price data |
| `view_portfolio` | View paper trading portfolio |
| `paper_trade` | Buy/sell with virtual $100k |
| `smart_trade` | Intelligent trade execution |
| `alpaca_trade` | Alpaca broker integration |
| `ibkr_trade` | Interactive Brokers integration |
| `alpaca_account` | Alpaca account info |
| `ibkr_account` | IBKR account info |
| `market_overview` | Market summary |
| `stock_news` | Latest stock news |
| `watchlist` | Manage watchlist |
| `tradingview_setup` | TradingView webhook config |
| `automate_broker_app` | Broker app automation |

---

## 💻 Coder Agent

**File:** `voca/brain/agents/coder.py`
**Tier:** Specialist (GPT-4o-mini)
**Description:** Read, write, edit code files and integrate with VS Code.

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `write_file` | Create or overwrite files |
| `edit_file` | Edit specific sections of files |
| `search_in_files` | Grep/search across codebase |
| `open_in_vscode` | Open file in VS Code |

---

## 📦 Git Agent

**File:** `voca/brain/agents/git_agent.py`
**Tier:** Specialist (GPT-4o-mini)
**Description:** Git operations and AI-powered code review.

| Tool | Description |
|------|-------------|
| `git_status` | Repository status |
| `git_diff` | Show changes |
| `git_commit` | Commit with message |
| `git_push` | Push to remote |
| `git_pull` | Pull from remote |
| `git_branch` | Branch operations |
| `git_log` | Commit history |
| `git_stash` | Stash changes |
| `git_review` | AI-powered code review |

---

## 🔌 Plugin Agents

**Directory:** `plugins/`

Custom agents can be added as Python files in the `plugins/` directory. They are auto-discovered and registered at startup. See `plugins/_example_plugin.py` for a template.

---

## Multi-Agent Crews

**File:** `voca/brain/crew.py`

Multiple agents can collaborate on complex tasks using 4 strategies:

| Strategy | Description |
|----------|-------------|
| `sequential` | Agents process in order, passing results |
| `parallel` | All agents work simultaneously |
| `hierarchical` | Supervisor decomposes and delegates |
| `debate` | Agents argue perspectives, best wins |
