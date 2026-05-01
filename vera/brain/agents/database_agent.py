"""Database Agent -- SQLite queries, schema, migrations, optimization, backups."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from vera.brain.agents.base import BaseAgent, Tool
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)


class SQLiteTool(Tool):
    def __init__(self):
        super().__init__(
            name="sqlite_query",
            description="Execute SQLite queries",
            parameters={
                "database": {"type": "str", "description": "Database path"},
                "query": {"type": "str", "description": "SQL query"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            conn = sqlite3.connect(kw.get("database", "data/vera.db"))
            conn.row_factory = sqlite3.Row
            cur = conn.execute(kw["query"])
            if kw["query"].strip().upper().startswith("SELECT"):
                rows = [dict(r) for r in cur.fetchall()[:100]]
                return {
                    "status": "success",
                    "rows": rows,
                    "count": len(rows),
                    "columns": [d[0] for d in cur.description] if cur.description else [],
                }
            conn.commit()
            return {"status": "success", "affected": cur.rowcount}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()


class DatabaseInfoTool(Tool):
    def __init__(self):
        super().__init__(
            name="db_info",
            description="Get database schema/table info",
            parameters={
                "database": {"type": "str", "description": "Database path"},
                "table": {"type": "str", "description": "Table name (optional)"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            conn = sqlite3.connect(kw.get("database", "data/vera.db"))
            if kw.get("table"):
                cols = [
                    {"name": r[1], "type": r[2], "pk": r[5]}
                    for r in conn.execute(f"PRAGMA table_info({kw['table']})").fetchall()
                ]
                count = conn.execute(f"SELECT COUNT(*) FROM {kw['table']}").fetchone()[0]
                return {"status": "success", "table": kw["table"], "columns": cols, "rows": count}
            return {
                "status": "success",
                "tables": [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()],
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class MigrationTool(Tool):
    def __init__(self):
        super().__init__(
            name="db_migrate",
            description="Create/run database migrations",
            parameters={
                "action": {"type": "str", "description": "create|status"},
                "name": {"type": "str", "description": "Migration name"},
                "sql_up": {"type": "str", "description": "SQL up"},
                "sql_down": {"type": "str", "description": "SQL rollback"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        md = Path("data/migrations")
        md.mkdir(parents=True, exist_ok=True)
        a = kw.get("action", "status")
        if a == "create":
            name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{kw.get('name', 'mig')}"
            (md / f"{name}.json").write_text(
                json.dumps(
                    {"name": name, "up": kw.get("sql_up", ""), "down": kw.get("sql_down", ""), "applied": False},
                    indent=2,
                )
            )
            return {"status": "success", "migration": name}
        migs = [json.loads(f.read_text()) for f in sorted(md.glob("*.json"))]
        return {"status": "success", "migrations": [{"name": m["name"], "applied": m["applied"]} for m in migs]}


class QueryOptimizerTool(Tool):
    def __init__(self):
        super().__init__(
            name="query_optimizer",
            description="Analyze/optimize SQL queries",
            parameters={
                "query": {"type": "str", "description": "SQL to optimize"},
                "database": {"type": "str", "description": "Database path"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        try:
            conn = sqlite3.connect(kw.get("database", "data/vera.db"))
            plan = conn.execute(f"EXPLAIN QUERY PLAN {kw['query']}").fetchall()
            return {
                "status": "success",
                "plan": [{"detail": r[3]} for r in plan],
                "tip": "SCAN=slow, SEARCH=fast. Add indexes for queried columns.",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


class BackupTool(Tool):
    def __init__(self):
        super().__init__(
            name="db_backup",
            description="Backup/restore database",
            parameters={
                "action": {"type": "str", "description": "backup|restore|list"},
                "database": {"type": "str", "description": "Database path"},
                "backup_path": {"type": "str", "description": "Backup path"},
            },
        )

    async def execute(self, **kw: Any) -> dict[str, Any]:
        db = kw.get("database", "data/vera.db")
        bd = Path("data/backups")
        bd.mkdir(parents=True, exist_ok=True)
        a = kw.get("action", "backup")
        if a == "backup":
            bp = bd / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(db, bp)
            return {"status": "success", "backup": str(bp)}
        elif a == "restore":
            shutil.copy2(kw.get("backup_path", ""), db)
            return {"status": "success", "restored": db}
        return {
            "status": "success",
            "backups": [
                {"name": b.name, "size_mb": round(b.stat().st_size / 1e6, 2)}
                for b in sorted(bd.glob("*.db"), reverse=True)[:10]
            ],
        }


class DatabaseAgent(BaseAgent):
    name = "database"
    description = "SQLite queries, schema inspection, migrations, query optimization, backups"
    tier = ModelTier.SPECIALIST
    system_prompt = "You are eVera's Database Agent. Execute SQL, inspect schemas, manage migrations, optimize queries, handle backups."
    offline_responses = {
        "query": "\U0001f4be Query!",
        "database": "\U0001f5c4 Database ready!",
        "sql": "\U0001f4be SQL!",
        "backup": "\U0001f4be Backup!",
    }

    def _setup_tools(self):
        self._tools = [SQLiteTool(), DatabaseInfoTool(), MigrationTool(), QueryOptimizerTool(), BackupTool()]
