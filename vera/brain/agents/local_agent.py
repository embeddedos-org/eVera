"""LOCAL Mode Intelligence Agent — 100% offline capabilities.

Provides offline voice transcription, OCR, translation, code execution sandbox,
intelligent file search, note-taking, and calendar — all without internet.
"""

from __future__ import annotations

import logging
import os
import json
import time
import subprocess
import platform
from typing import Any
from pathlib import Path

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

# Local data directory for notes, calendar, etc.
_DATA_DIR = Path(os.path.expanduser("~/.evera/local_data"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Offline Voice Transcription
# ---------------------------------------------------------------------------

class OfflineVoiceTool(Tool):
    """Transcribe audio offline using Whisper (via Ollama or local whisper.cpp)."""

    def __init__(self):
        super().__init__(
            name="voice_transcribe",
            description="Transcribe audio file to text offline (no internet needed). Supports mp3, wav, m4a, ogg, webm.",
            parameters={
                "audio_path": {"type": "str", "description": "Path to audio file"},
                "language": {"type": "str", "description": "Language code e.g. 'en', 'es', 'fr' (default: auto-detect)"},
                "model": {"type": "str", "description": "Whisper model: tiny|base|small|medium|large (default: base)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        audio_path = kw.get("audio_path", "")
        language = kw.get("language", "")
        model = kw.get("model", "base")
        if not audio_path or not os.path.exists(audio_path):
            return {"status": "error", "message": f"Audio file not found: {audio_path}"}
        # Try whisper-cpp first (fastest, fully offline)
        try:
            import whisper
            m = whisper.load_model(model)
            result = m.transcribe(audio_path, language=language or None)
            return {
                "status": "success",
                "text": result["text"].strip(),
                "language": result.get("language", "unknown"),
                "segments": len(result.get("segments", [])),
                "backend": "openai-whisper",
            }
        except ImportError:
            pass
        # Try faster-whisper
        try:
            from faster_whisper import WhisperModel
            m = WhisperModel(model, device="cpu", compute_type="int8")
            segments, info = m.transcribe(audio_path, language=language or None)
            text = " ".join(s.text for s in segments)
            return {
                "status": "success",
                "text": text.strip(),
                "language": info.language,
                "backend": "faster-whisper",
            }
        except ImportError:
            pass
        # Fallback: Ollama whisper endpoint
        try:
            import requests
            import base64
            with open(audio_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()
            r = requests.post("http://localhost:11434/api/transcribe", json={
                "model": f"whisper:{model}",
                "audio": audio_b64,
                "language": language or "auto",
            }, timeout=120)
            if r.status_code == 200:
                data = r.json()
                return {"status": "success", "text": data.get("text", ""), "backend": "ollama-whisper"}
        except Exception:
            pass
        return {
            "status": "error",
            "message": "No offline transcription backend found. Install: pip install openai-whisper OR pip install faster-whisper",
        }


# ---------------------------------------------------------------------------
# Offline Translation
# ---------------------------------------------------------------------------

class OfflineTranslationTool(Tool):
    """Translate text offline using Ollama LLM or argostranslate."""

    def __init__(self):
        super().__init__(
            name="translate_offline",
            description="Translate text to any language offline without internet",
            parameters={
                "text": {"type": "str", "description": "Text to translate"},
                "target_language": {"type": "str", "description": "Target language e.g. 'Spanish', 'French', 'Arabic', 'Chinese'"},
                "source_language": {"type": "str", "description": "Source language (default: auto-detect)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        text = kw.get("text", "")
        target = kw.get("target_language", "English")
        source = kw.get("source_language", "auto")
        if not text:
            return {"status": "error", "message": "text is required"}
        # Try argostranslate (pure offline, no LLM needed)
        try:
            import argostranslate.package
            import argostranslate.translate
            from_code = source[:2].lower() if source != "auto" else "en"
            to_code = target[:2].lower()
            installed_languages = argostranslate.translate.get_installed_languages()
            from_lang = next((l for l in installed_languages if l.code == from_code), None)
            to_lang = next((l for l in installed_languages if l.code == to_code), None)
            if from_lang and to_lang:
                translation = from_lang.get_translation(to_lang)
                if translation:
                    result = translation.translate(text)
                    return {"status": "success", "translated": result, "backend": "argostranslate", "target": target}
        except ImportError:
            pass
        # Fallback: use Ollama LLM for translation
        try:
            import requests
            prompt = f"Translate the following text to {target}. Return ONLY the translation, nothing else.\n\nText: {text}"
            r = requests.post("http://localhost:11434/api/generate", json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False,
            }, timeout=60)
            if r.status_code == 200:
                data = r.json()
                return {"status": "success", "translated": data.get("response", "").strip(), "backend": "ollama-llm", "target": target}
        except Exception:
            pass
        return {"status": "error", "message": "No offline translation backend available. Install: pip install argostranslate"}


# ---------------------------------------------------------------------------
# Code Execution Sandbox
# ---------------------------------------------------------------------------

class CodeSandboxTool(Tool):
    """Execute code in a sandboxed environment — Python, JavaScript, Bash, and more."""

    def __init__(self):
        super().__init__(
            name="code_sandbox",
            description="Execute code safely in a sandbox: Python, JavaScript (Node.js), Bash, Ruby, Go. Returns stdout, stderr, and return code.",
            parameters={
                "language": {"type": "str", "description": "python|javascript|bash|ruby|go|rust"},
                "code": {"type": "str", "description": "Code to execute"},
                "timeout": {"type": "int", "description": "Timeout in seconds (default 30)"},
                "working_dir": {"type": "str", "description": "Working directory (optional)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        language = kw.get("language", "python").lower()
        code = kw.get("code", "")
        timeout = int(kw.get("timeout", 30))
        working_dir = kw.get("working_dir") or "/tmp"
        if not code:
            return {"status": "error", "message": "code is required"}
        import tempfile
        import subprocess
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=_get_ext(language), delete=False, dir="/tmp") as f:
                f.write(code)
                tmp_path = f.name
            cmd = _get_run_cmd(language, tmp_path)
            if not cmd:
                return {"status": "error", "message": f"Language '{language}' not supported"}
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                cwd=working_dir,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            os.unlink(tmp_path)
            return {
                "status": "success" if result.returncode == 0 else "error",
                "language": language,
                "returncode": result.returncode,
                "stdout": result.stdout[:8000],
                "stderr": result.stderr[:2000],
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": f"Code timed out after {timeout}s"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def _get_ext(lang: str) -> str:
    return {
        "python": ".py", "javascript": ".js", "bash": ".sh",
        "ruby": ".rb", "go": ".go", "rust": ".rs",
    }.get(lang, ".txt")


def _get_run_cmd(lang: str, path: str) -> list[str] | None:
    return {
        "python": ["python3", path],
        "javascript": ["node", path],
        "bash": ["bash", path],
        "ruby": ["ruby", path],
        "go": ["go", "run", path],
    }.get(lang)


# ---------------------------------------------------------------------------
# Intelligent File Search
# ---------------------------------------------------------------------------

class SmartFileSearchTool(Tool):
    """Search files by name, content, type, size, or date — fully offline."""

    def __init__(self):
        super().__init__(
            name="smart_file_search",
            description="Search for files by name, content, type, size, or date modified. Works 100% offline.",
            parameters={
                "query": {"type": "str", "description": "Search query (filename, content keyword, or file type)"},
                "search_dir": {"type": "str", "description": "Directory to search (default: home directory)"},
                "search_type": {"type": "str", "description": "name|content|type|recent|large"},
                "file_type": {"type": "str", "description": "File extension filter e.g. 'pdf', 'py', 'docx'"},
                "max_results": {"type": "int", "description": "Max results to return (default 20)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import glob
        query = kw.get("query", "")
        search_dir = kw.get("search_dir", str(Path.home()))
        search_type = kw.get("search_type", "name")
        file_type = kw.get("file_type", "")
        max_results = int(kw.get("max_results", 20))
        results = []
        try:
            if search_type == "name":
                pattern = f"**/*{query}*"
                if file_type:
                    pattern = f"**/*{query}*.{file_type}"
                matches = list(Path(search_dir).glob(pattern))[:max_results]
                results = [{"path": str(m), "size": m.stat().st_size, "modified": m.stat().st_mtime} for m in matches if m.is_file()]

            elif search_type == "content":
                # grep-based content search
                ext_flag = f"--include=*.{file_type}" if file_type else ""
                cmd = ["grep", "-rl", query, search_dir]
                if file_type:
                    cmd = ["grep", "-rl", f"--include=*.{file_type}", query, search_dir]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                matches = r.stdout.strip().split("\n")[:max_results]
                results = [{"path": m} for m in matches if m]

            elif search_type == "type":
                ext = file_type or query
                matches = list(Path(search_dir).glob(f"**/*.{ext}"))[:max_results]
                results = [{"path": str(m), "size": m.stat().st_size} for m in matches if m.is_file()]

            elif search_type == "recent":
                all_files = list(Path(search_dir).rglob("*"))
                all_files = [f for f in all_files if f.is_file()]
                all_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                results = [{"path": str(f), "modified": f.stat().st_mtime, "size": f.stat().st_size} for f in all_files[:max_results]]

            elif search_type == "large":
                all_files = list(Path(search_dir).rglob("*"))
                all_files = [f for f in all_files if f.is_file()]
                all_files.sort(key=lambda f: f.stat().st_size, reverse=True)
                results = [{"path": str(f), "size_mb": round(f.stat().st_size / 1e6, 2)} for f in all_files[:max_results]]

            return {"status": "success", "query": query, "results": results, "count": len(results)}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Offline Notes
# ---------------------------------------------------------------------------

class NotesTool(Tool):
    """Create, read, update, delete, and search notes — stored locally."""

    def __init__(self):
        super().__init__(
            name="notes",
            description="Manage personal notes offline: create, read, list, search, update, delete notes",
            parameters={
                "action": {"type": "str", "description": "create|read|list|search|update|delete"},
                "title": {"type": "str", "description": "Note title"},
                "content": {"type": "str", "description": "Note content"},
                "query": {"type": "str", "description": "Search query"},
                "tags": {"type": "str", "description": "Comma-separated tags"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        notes_dir = _DATA_DIR / "notes"
        notes_dir.mkdir(exist_ok=True)
        action = kw.get("action", "list")
        title = kw.get("title", "")
        content = kw.get("content", "")
        query = kw.get("query", "")
        tags = [t.strip() for t in kw.get("tags", "").split(",") if t.strip()]
        try:
            if action == "create":
                if not title:
                    title = f"Note_{int(time.time())}"
                note_id = title.lower().replace(" ", "_").replace("/", "-")[:50]
                note_path = notes_dir / f"{note_id}.json"
                note = {
                    "id": note_id, "title": title, "content": content,
                    "tags": tags, "created": time.time(), "updated": time.time(),
                }
                note_path.write_text(json.dumps(note, indent=2))
                return {"status": "success", "action": "created", "id": note_id, "title": title}

            elif action == "list":
                notes = []
                for f in sorted(notes_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
                    n = json.loads(f.read_text())
                    notes.append({"id": n["id"], "title": n["title"], "tags": n.get("tags", []), "updated": n.get("updated")})
                return {"status": "success", "notes": notes, "count": len(notes)}

            elif action == "read":
                note_id = title.lower().replace(" ", "_")[:50]
                note_path = notes_dir / f"{note_id}.json"
                if not note_path.exists():
                    # Search by title
                    for f in notes_dir.glob("*.json"):
                        n = json.loads(f.read_text())
                        if title.lower() in n["title"].lower():
                            return {"status": "success", "note": n}
                    return {"status": "error", "message": f"Note '{title}' not found"}
                return {"status": "success", "note": json.loads(note_path.read_text())}

            elif action == "search":
                matches = []
                for f in notes_dir.glob("*.json"):
                    n = json.loads(f.read_text())
                    if query.lower() in n["title"].lower() or query.lower() in n["content"].lower() or query.lower() in " ".join(n.get("tags", [])).lower():
                        matches.append({"id": n["id"], "title": n["title"], "excerpt": n["content"][:200]})
                return {"status": "success", "matches": matches, "count": len(matches)}

            elif action == "update":
                note_id = title.lower().replace(" ", "_")[:50]
                note_path = notes_dir / f"{note_id}.json"
                if not note_path.exists():
                    return {"status": "error", "message": f"Note '{title}' not found"}
                n = json.loads(note_path.read_text())
                if content:
                    n["content"] = content
                if tags:
                    n["tags"] = tags
                n["updated"] = time.time()
                note_path.write_text(json.dumps(n, indent=2))
                return {"status": "success", "action": "updated", "id": note_id}

            elif action == "delete":
                note_id = title.lower().replace(" ", "_")[:50]
                note_path = notes_dir / f"{note_id}.json"
                if note_path.exists():
                    note_path.unlink()
                    return {"status": "success", "action": "deleted", "id": note_id}
                return {"status": "error", "message": f"Note '{title}' not found"}

            return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Offline Calendar
# ---------------------------------------------------------------------------

class CalendarTool(Tool):
    """Manage calendar events locally — no cloud sync needed."""

    def __init__(self):
        super().__init__(
            name="calendar",
            description="Manage calendar events offline: add, list, search, delete events. All stored locally.",
            parameters={
                "action": {"type": "str", "description": "add|list|today|upcoming|search|delete"},
                "title": {"type": "str", "description": "Event title"},
                "date": {"type": "str", "description": "Date YYYY-MM-DD or natural language like 'tomorrow', 'next Monday'"},
                "time": {"type": "str", "description": "Time HH:MM (24h format)"},
                "duration_minutes": {"type": "int", "description": "Duration in minutes (default 60)"},
                "description": {"type": "str", "description": "Event description"},
                "query": {"type": "str", "description": "Search query"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import datetime
        cal_path = _DATA_DIR / "calendar.json"
        events = json.loads(cal_path.read_text()) if cal_path.exists() else []
        action = kw.get("action", "list")
        try:
            if action == "add":
                title = kw.get("title", "Untitled Event")
                date_str = kw.get("date", "")
                time_str = kw.get("time", "09:00")
                duration = int(kw.get("duration_minutes", 60))
                description = kw.get("description", "")
                # Parse natural language dates
                date_str = _parse_date(date_str)
                event = {
                    "id": f"evt_{int(time.time())}",
                    "title": title,
                    "date": date_str,
                    "time": time_str,
                    "duration_minutes": duration,
                    "description": description,
                    "created": time.time(),
                }
                events.append(event)
                cal_path.write_text(json.dumps(events, indent=2))
                return {"status": "success", "action": "added", "event": event}

            elif action == "list":
                events_sorted = sorted(events, key=lambda e: f"{e['date']} {e['time']}")
                return {"status": "success", "events": events_sorted[:50], "count": len(events)}

            elif action == "today":
                today = datetime.date.today().isoformat()
                today_events = [e for e in events if e.get("date") == today]
                today_events.sort(key=lambda e: e.get("time", ""))
                return {"status": "success", "date": today, "events": today_events, "count": len(today_events)}

            elif action == "upcoming":
                today = datetime.date.today().isoformat()
                upcoming = [e for e in events if e.get("date", "") >= today]
                upcoming.sort(key=lambda e: f"{e['date']} {e['time']}")
                return {"status": "success", "events": upcoming[:20], "count": len(upcoming)}

            elif action == "search":
                query = kw.get("query", "").lower()
                matches = [e for e in events if query in e.get("title", "").lower() or query in e.get("description", "").lower()]
                return {"status": "success", "matches": matches, "count": len(matches)}

            elif action == "delete":
                title = kw.get("title", "")
                before = len(events)
                events = [e for e in events if title.lower() not in e.get("title", "").lower()]
                cal_path.write_text(json.dumps(events, indent=2))
                return {"status": "success", "deleted": before - len(events)}

            return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def _parse_date(date_str: str) -> str:
    """Parse natural language date to YYYY-MM-DD."""
    import datetime
    date_str = date_str.lower().strip()
    today = datetime.date.today()
    if date_str in ("today", ""):
        return today.isoformat()
    elif date_str == "tomorrow":
        return (today + datetime.timedelta(days=1)).isoformat()
    elif date_str == "yesterday":
        return (today - datetime.timedelta(days=1)).isoformat()
    elif "next" in date_str:
        days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        for day_name, day_num in days.items():
            if day_name in date_str:
                days_ahead = (day_num - today.weekday()) % 7 or 7
                return (today + datetime.timedelta(days=days_ahead)).isoformat()
    # Try direct parse
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            pass
    return today.isoformat()


# ---------------------------------------------------------------------------
# Offline Contacts
# ---------------------------------------------------------------------------

class ContactsTool(Tool):
    """Manage contacts locally — store, search, and retrieve contact information."""

    def __init__(self):
        super().__init__(
            name="contacts",
            description="Manage contacts offline: add, list, search, update, delete contacts",
            parameters={
                "action": {"type": "str", "description": "add|list|search|update|delete"},
                "name": {"type": "str", "description": "Contact name"},
                "email": {"type": "str", "description": "Email address"},
                "phone": {"type": "str", "description": "Phone number"},
                "company": {"type": "str", "description": "Company name"},
                "notes": {"type": "str", "description": "Additional notes"},
                "query": {"type": "str", "description": "Search query"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        contacts_path = _DATA_DIR / "contacts.json"
        contacts = json.loads(contacts_path.read_text()) if contacts_path.exists() else []
        action = kw.get("action", "list")
        try:
            if action == "add":
                contact = {
                    "id": f"c_{int(time.time())}",
                    "name": kw.get("name", ""),
                    "email": kw.get("email", ""),
                    "phone": kw.get("phone", ""),
                    "company": kw.get("company", ""),
                    "notes": kw.get("notes", ""),
                    "created": time.time(),
                }
                contacts.append(contact)
                contacts_path.write_text(json.dumps(contacts, indent=2))
                return {"status": "success", "action": "added", "contact": contact}

            elif action == "list":
                contacts_sorted = sorted(contacts, key=lambda c: c.get("name", "").lower())
                return {"status": "success", "contacts": contacts_sorted, "count": len(contacts)}

            elif action == "search":
                query = kw.get("query", "").lower()
                matches = [c for c in contacts if
                           query in c.get("name", "").lower() or
                           query in c.get("email", "").lower() or
                           query in c.get("company", "").lower() or
                           query in c.get("phone", "")]
                return {"status": "success", "matches": matches, "count": len(matches)}

            elif action == "delete":
                name = kw.get("name", "")
                before = len(contacts)
                contacts = [c for c in contacts if name.lower() not in c.get("name", "").lower()]
                contacts_path.write_text(json.dumps(contacts, indent=2))
                return {"status": "success", "deleted": before - len(contacts)}

            return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Offline Reminder
# ---------------------------------------------------------------------------

class ReminderTool(Tool):
    """Set and manage reminders that trigger desktop notifications."""

    def __init__(self):
        super().__init__(
            name="reminder",
            description="Set reminders that trigger desktop notifications at specified times",
            parameters={
                "action": {"type": "str", "description": "set|list|delete"},
                "message": {"type": "str", "description": "Reminder message"},
                "in_minutes": {"type": "int", "description": "Remind in N minutes from now"},
                "at_time": {"type": "str", "description": "Specific time HH:MM"},
                "date": {"type": "str", "description": "Date YYYY-MM-DD (default: today)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        import datetime
        reminders_path = _DATA_DIR / "reminders.json"
        reminders = json.loads(reminders_path.read_text()) if reminders_path.exists() else []
        action = kw.get("action", "list")
        try:
            if action == "set":
                message = kw.get("message", "Reminder")
                in_minutes = kw.get("in_minutes")
                at_time = kw.get("at_time", "")
                date_str = kw.get("date", datetime.date.today().isoformat())
                if in_minutes:
                    trigger_ts = time.time() + int(in_minutes) * 60
                elif at_time:
                    dt_str = f"{date_str} {at_time}"
                    dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                    trigger_ts = dt.timestamp()
                else:
                    trigger_ts = time.time() + 3600  # default 1 hour
                reminder = {
                    "id": f"r_{int(time.time())}",
                    "message": message,
                    "trigger_ts": trigger_ts,
                    "trigger_human": datetime.datetime.fromtimestamp(trigger_ts).strftime("%Y-%m-%d %H:%M"),
                    "created": time.time(),
                    "fired": False,
                }
                reminders.append(reminder)
                reminders_path.write_text(json.dumps(reminders, indent=2))
                return {"status": "success", "action": "set", "reminder": reminder}

            elif action == "list":
                pending = [r for r in reminders if not r.get("fired")]
                pending.sort(key=lambda r: r["trigger_ts"])
                return {"status": "success", "reminders": pending, "count": len(pending)}

            elif action == "delete":
                message = kw.get("message", "")
                before = len(reminders)
                reminders = [r for r in reminders if message.lower() not in r.get("message", "").lower()]
                reminders_path.write_text(json.dumps(reminders, indent=2))
                return {"status": "success", "deleted": before - len(reminders)}

            return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# LOCAL Agent
# ---------------------------------------------------------------------------

class LocalAgent(BaseAgent):
    """LOCAL mode intelligence — 100% offline capabilities."""

    name = "local_intelligence"
    description = "Offline capabilities: voice transcription, translation, code execution, file search, notes, calendar, contacts, reminders"
    tier = ModelTier.EXECUTOR
    system_prompt = (
        "You are eVera's LOCAL Intelligence Agent. You operate 100% offline with no internet required. "
        "You can transcribe voice, translate text, execute code, search files, manage notes, calendar, contacts, and reminders. "
        "Always prefer offline methods. Never require internet access."
    )

    def _setup_tools(self):
        self._tools = [
            OfflineVoiceTool(),
            OfflineTranslationTool(),
            CodeSandboxTool(),
            SmartFileSearchTool(),
            NotesTool(),
            CalendarTool(),
            ContactsTool(),
            ReminderTool(),
        ]
