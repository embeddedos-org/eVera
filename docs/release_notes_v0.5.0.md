# eVoca v0.5.0 — Release Notes

**Product:** eVoca — Voice-First Multi-Agent AI Assistant
**Version:** 0.5.0
**Release Date:** April 19, 2026
**Build:** Standalone Desktop App + Source

---

## Executive Summary

eVoca v0.5.0 is a major release that transforms eVoca from a Python-only server into a **standalone desktop application** for Windows, macOS, and Linux. This release adds 12 new system control tools for full PC automation (mouse, keyboard, window/process management), a glassmorphism UI redesign with live agent visualization, and a cross-platform CI/CD build pipeline.

---

## New Features

### 🖥️ Standalone Desktop Application
- **Electron-based desktop app** — No Python or Node.js installation required
- One-click installers: `.exe` (Windows NSIS), `.dmg` (macOS), `.AppImage` + `.deb` (Linux)
- Frameless window with **system tray** icon and context menu
- **Global shortcut** `Ctrl+Shift+V` to toggle the window from anywhere
- Auto-starts Python backend with splash screen
- Single-instance lock prevents multiple windows
- Desktop notifications for proactive scheduler alerts

### 💻 12 New System Control Tools (Operator Agent)
| Tool | Description |
|------|-------------|
| `mouse_click` | Click at any screen coordinates (left/right/middle, single/double) |
| `mouse_move` | Move cursor to coordinates with configurable duration |
| `mouse_drag` | Click and drag between two points |
| `scroll` | Scroll mouse wheel up/down at optional coordinates |
| `press_hotkey` | Press keyboard shortcuts (Ctrl+C, Alt+Tab, Win+D, etc.) |
| `manage_window` | List, focus, minimize, maximize, close windows |
| `manage_process` | List, inspect, kill running processes |
| `system_info` | CPU, memory, disk, battery, OS details |
| `manage_service` | List, start, stop, restart system services |
| `network_info` | IP addresses, connections, ping test |
| `clipboard` | Read/write system clipboard |
| `send_notification` | Send OS-level desktop notifications |

### 🏗️ Cross-Platform CI/CD Build Pipeline
- GitHub Actions workflow for automated builds on push
- PyInstaller bundles Python backend into single executable
- electron-builder packages platform-specific installers
- Automated release artifact upload

### 🎨 Glassmorphism UI Redesign
- Complete visual overhaul with frosted glass panels and `backdrop-filter: blur(20px)`
- Animated particle background with orbital nebula effects
- Gradient glow ring around face canvas with rotating border animation
- Spring-based animations for message bubbles, agent cards, timeline entries
- Shimmer progress bars with gradient fills for tool execution

### 👁️ Live Agent Visualization (3 Modes)
- **Card View** — Glass-effect cards with real-time status, current tool call, animated progress
- **Timeline View** — Vertical timeline with timestamps, agent icons, staggered animations
- **Constellation View** — Canvas network graph with animated particles along connections

### 📡 Agent Status Streaming
- New `/agents/stream` SSE endpoint broadcasting real-time agent events
- `BaseAgent.run()` emits status events: `working` (with tool name/args), `done` (with result)
- Frontend consumes SSE stream and updates all 3 visualization modes live

### 📱 Progressive Web App (PWA) Support
- `manifest.json` with app name, theme colors, icons, shortcuts
- Service worker with cache-first for static assets, network-first for API
- Installable from Chrome/Edge/Safari as a standalone web app

---

## Improvements

- Upgraded from 78 to **90+ tools** across 10 agents
- Cross-platform app launch maps for Windows, macOS, and Linux
- Improved type text tool: uses temp file instead of inline PowerShell to prevent injection
- Better error messages across all tool executions

---

## Bug Fixes

- Fixed Python 3.8 compatibility: `dict[str, Any]` → `Dict[str, Any]` in `bus.py`
- Applied 126 ruff auto-fixes across the codebase
- Fixed edge cases in keyboard shortcut key mapping

---

## Breaking Changes

None. This release is fully backward compatible with v0.4.x configurations.

---

## Known Issues

- **macOS Gatekeeper** — First launch may require "Open Anyway" in Security settings
- **Linux Wayland** — Mouse automation (`pyautogui`) may not work on Wayland; use X11
- **Large Ollama models** — Models >7B may be slow on systems with <16GB RAM
- **Playwright browsers** — Must be installed separately (`playwright install chromium`)

---

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **OS** | Windows 10, macOS 12, Ubuntu 20.04 | Windows 11, macOS 14, Ubuntu 22.04 |
| **RAM** | 4 GB | 8 GB (16 GB for local LLM) |
| **Disk** | 500 MB | 2 GB (with Ollama models) |
| **Python** | 3.11+ (source only) | 3.12 |
| **Node.js** | 18+ (dev only) | 20 LTS |

---

## Upgrade Path (from v0.4.x)

1. **Desktop app users:** Download the latest installer — it replaces the previous version
2. **Source users:**
   ```bash
   git pull origin main
   pip install -r requirements.txt  # New dependencies: pyautogui, pygetwindow, pyperclip
   ```
3. No configuration changes required — `.env` is fully compatible

---

## Download

| Platform | File | Size |
|----------|------|------|
| Windows | [Voca-Setup.exe](https://github.com/patchava-sr/eVoca/releases/v0.5.0) | ~120 MB |
| macOS | [Voca.dmg](https://github.com/patchava-sr/eVoca/releases/v0.5.0) | ~110 MB |
| Linux | [Voca.AppImage](https://github.com/patchava-sr/eVoca/releases/v0.5.0) | ~130 MB |
| Source | [Source code (zip)](https://github.com/patchava-sr/eVoca/archive/v0.5.0.zip) | ~2 MB |

---

*Released by Srikanth Patchava — April 19, 2026*
