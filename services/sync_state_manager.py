# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Sync state manager — persists sync progress in SQLite for resume after crash."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import Config
from services.models import ComparisonEntry, SyncAction


class SyncStateManager:
    """Persist and recover synchronization state in SQLite.

    Allows resuming a sync after crash or disk disconnect.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Config.SYNC_STATE_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                source TEXT NOT NULL,
                dest TEXT NOT NULL,
                total_ops INTEGER NOT NULL DEFAULT 0,
                completed_ops INTEGER NOT NULL DEFAULT 0,
                current_op TEXT,
                timestamp REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS completed_ops (
                rel_path TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.commit()

    def save_state(
        self,
        source: str,
        dest: str,
        total_ops: int,
    ) -> None:
        """Save or update the sync state header."""
        conn = self._connect()
        try:
            self._ensure_tables(conn)
            conn.execute("DELETE FROM sync_state")
            conn.execute("DELETE FROM completed_ops")
            conn.execute(
                "INSERT INTO sync_state (source, dest, total_ops, completed_ops, current_op, timestamp, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (source, dest, total_ops, 0, "", datetime.now().timestamp(), "in_progress"),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_completed(self, rel_path: str, action: str) -> None:
        """Mark a single operation as completed."""
        conn = self._connect()
        try:
            self._ensure_tables(conn)
            conn.execute(
                "INSERT OR REPLACE INTO completed_ops (rel_path, action, timestamp) VALUES (?, ?, ?)",
                (rel_path, action, datetime.now().timestamp()),
            )
            conn.execute(
                "UPDATE sync_state SET completed_ops = (SELECT COUNT(*) FROM completed_ops), current_op = ?, timestamp = ? WHERE id = 1",
                (rel_path, datetime.now().timestamp()),
            )
            conn.commit()
        finally:
            conn.close()

    def load_state(self) -> Optional[dict]:
        """Load the current sync state. Returns None if no state exists."""
        if not self._db_path.exists():
            return None
        conn = self._connect()
        try:
            self._ensure_tables(conn)
            row = conn.execute("SELECT * FROM sync_state WHERE id = 1").fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    def get_completed_count(self) -> int:
        """Get the number of completed operations."""
        if not self._db_path.exists():
            return 0
        conn = self._connect()
        try:
            self._ensure_tables(conn)
            row = conn.execute("SELECT COUNT(*) as cnt FROM completed_ops").fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def get_pending_ops(self, entries: list[ComparisonEntry]) -> list[ComparisonEntry]:
        """Get entries that have not yet been completed.

        Args:
            entries: Full list of ComparisonEntry from the original plan.

        Returns:
            Sublist of entries not yet completed.
        """
        if not self._db_path.exists():
            return entries
        conn = self._connect()
        try:
            self._ensure_tables(conn)
            rows = conn.execute("SELECT rel_path FROM completed_ops").fetchall()
            completed_paths = {row["rel_path"] for row in rows}
            return [e for e in entries if e.rel_path not in completed_paths]
        finally:
            conn.close()

    def has_incomplete_sync(self) -> bool:
        """Check if there is an incomplete sync state."""
        if not self._db_path.exists():
            return False
        state = self.load_state()
        if state is None:
            return False
        return state.get("status", "") == "in_progress"

    def mark_completed_state(self) -> None:
        """Mark the sync as fully completed."""
        conn = self._connect()
        try:
            self._ensure_tables(conn)
            conn.execute(
                "UPDATE sync_state SET status = 'completed', timestamp = ? WHERE id = 1",
                (datetime.now().timestamp(),),
            )
            conn.commit()
        finally:
            conn.close()

    def clear_state(self) -> None:
        """Delete the sync state (completed or abandoned)."""
        conn = self._connect()
        try:
            self._ensure_tables(conn)
            conn.execute("DELETE FROM sync_state")
            conn.execute("DELETE FROM completed_ops")
            conn.commit()
        finally:
            conn.close()
            if self._db_path.exists():
                self._db_path.unlink(missing_ok=True)