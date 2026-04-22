"""SQLite-backed conversation persistence for WorkingMemory.

@file vera/memory/persistence.py
@brief Persists conversation turns to a SQLite database so that
       working memory survives server restarts.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/conversations.db")


class ConversationStore:
    """SQLite-backed conversation storage.

    Provides methods to save and load conversation turns,
    enabling working memory persistence across server restarts.

    @param db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._db_path = self._db_path.resolve()
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
        except (sqlite3.OperationalError, OSError):
            # Fallback to in-memory database if file path is not writable
            logger.warning("Cannot open %s, using in-memory database", self._db_path)
            self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("ConversationStore initialized at %s", self._db_path)

    def _create_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL DEFAULT 'default',
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                agent TEXT,
                metadata TEXT,
                timestamp REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_turns_session
            ON turns(session_id, timestamp)
        """)
        self._conn.commit()

    def save_turn(
        self,
        role: str,
        content: str,
        session_id: str = "default",
        agent: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Save a single conversation turn.

        @param role: 'user' or 'assistant'.
        @param content: The message content.
        @param session_id: Session identifier.
        @param agent: Agent name (for assistant turns).
        @param metadata: Optional metadata dict (stored as JSON).
        """
        self._conn.execute(
            "INSERT INTO turns (session_id, role, content, agent, metadata, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (
                session_id,
                role,
                content,
                agent,
                json.dumps(metadata) if metadata else None,
                time.time(),
            ),
        )
        self._conn.commit()

    def load_turns(self, session_id: str = "default", limit: int = 20) -> list[dict]:
        """Load recent turns for a session.

        @param session_id: Session identifier.
        @param limit: Maximum number of turns to return.
        @return List of turn dicts with role, content, agent, metadata, timestamp.
        """
        cursor = self._conn.execute(
            "SELECT role, content, agent, metadata, timestamp FROM turns "
            "WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        )
        rows = cursor.fetchall()
        turns = []
        for row in reversed(rows):
            meta = json.loads(row["metadata"]) if row["metadata"] else None
            turns.append(
                {
                    "role": row["role"],
                    "content": row["content"],
                    "agent": row["agent"],
                    "metadata": meta,
                    "timestamp": row["timestamp"],
                }
            )
        return turns

    def list_sessions(self) -> list[str]:
        """List all session IDs with conversations."""
        cursor = self._conn.execute("SELECT DISTINCT session_id FROM turns ORDER BY session_id")
        return [row["session_id"] for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> int:
        """Delete all turns for a session.

        @param session_id: Session to delete.
        @return Number of turns deleted.
        """
        cursor = self._conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
        self._conn.commit()
        return cursor.rowcount

    def prune(self, max_age_days: int = 30) -> int:
        """Delete turns older than max_age_days.

        @param max_age_days: Maximum age in days.
        @return Number of turns pruned.
        """
        cutoff = time.time() - (max_age_days * 86400)
        cursor = self._conn.execute("DELETE FROM turns WHERE timestamp < ?", (cutoff,))
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
