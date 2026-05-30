# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Snapshot manager — SQLite-based disk snapshots for offline browsing and rename detection."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import Config
from services.models import FileEntry, DiskSnapshot


class SnapshotManager:
    """Manage disk snapshots stored in SQLite databases."""

    def __init__(self, snapshots_dir: Path | None = None) -> None:
        self._snapshots_dir = snapshots_dir or Config.SNAPSHOTS_DIR
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)

    def _db_path(self, disk_id: str) -> Path:
        safe_id = disk_id.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self._snapshots_dir / f"{safe_id}{Config.SNAPSHOT_DB_SUFFIX}"

    def _connect(self, disk_id: str) -> sqlite3.Connection:
        db_path = self._db_path(disk_id)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_table(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                rel_path TEXT PRIMARY KEY,
                size INTEGER NOT NULL,
                mtime REAL NOT NULL,
                hash_sha256 TEXT NOT NULL DEFAULT '',
                is_dir INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_hash_sha256
            ON files (hash_sha256)
        """)
        conn.commit()

    def save_snapshot(
        self,
        disk_id: str,
        label: str,
        entries: list[FileEntry],
    ) -> DiskSnapshot:
        """Save a snapshot of file entries to a SQLite database.

        Args:
            disk_id: Unique identifier for the disk.
            label: Human-readable label for the disk.
            entries: List of FileEntry to store.

        Returns:
            DiskSnapshot with metadata.
        """
        conn = self._connect(disk_id)
        try:
            self._ensure_table(conn)
            conn.execute("DELETE FROM files")
            conn.executemany(
                "INSERT OR REPLACE INTO files (rel_path, size, mtime, hash_sha256, is_dir) VALUES (?, ?, ?, ?, ?)",
                [(e.rel_path, e.size, e.mtime, e.hash_sha256, 1 if e.is_dir else 0) for e in entries],
            )
            conn.commit()
        finally:
            conn.close()

        return DiskSnapshot(
            disk_id=disk_id,
            label=label,
            timestamp=datetime.now().timestamp(),
        )

    def update_incremental(
        self,
        disk_id: str,
        entries: list[FileEntry],
    ) -> None:
        """Incrementally update snapshot entries without rewriting everything.

        Only inserts or replaces the given entries. Does not delete missing entries.
        """
        conn = self._connect(disk_id)
        try:
            self._ensure_table(conn)
            conn.executemany(
                "INSERT OR REPLACE INTO files (rel_path, size, mtime, hash_sha256, is_dir) VALUES (?, ?, ?, ?, ?)",
                [(e.rel_path, e.size, e.mtime, e.hash_sha256, 1 if e.is_dir else 0) for e in entries],
            )
            conn.commit()
        finally:
            conn.close()

    def load_snapshot(self, disk_id: str) -> Optional[DiskSnapshot]:
        """Load snapshot metadata. Returns None if no snapshot exists."""
        db_path = self._db_path(disk_id)
        if not db_path.exists():
            return None
        mtime = db_path.stat().st_mtime
        return DiskSnapshot(
            disk_id=disk_id,
            label=disk_id,
            timestamp=mtime,
        )

    def query_by_path(self, disk_id: str, rel_path: str) -> Optional[FileEntry]:
        """Query a single file entry by relative path. O(1) via primary key."""
        db_path = self._db_path(disk_id)
        if not db_path.exists():
            return None
        conn = self._connect(disk_id)
        try:
            self._ensure_table(conn)
            row = conn.execute(
                "SELECT rel_path, size, mtime, hash_sha256, is_dir FROM files WHERE rel_path = ?",
                (rel_path,),
            ).fetchone()
            if row is None:
                return None
            return FileEntry(
                rel_path=row["rel_path"],
                size=row["size"],
                mtime=row["mtime"],
                hash_sha256=row["hash_sha256"],
                is_dir=bool(row["is_dir"]),
            )
        finally:
            conn.close()

    def query_by_hash(self, disk_id: str, hash_sha256: str) -> list[FileEntry]:
        """Query file entries by SHA-256 hash. Used for rename detection."""
        db_path = self._db_path(disk_id)
        if not db_path.exists():
            return []
        conn = self._connect(disk_id)
        try:
            self._ensure_table(conn)
            rows = conn.execute(
                "SELECT rel_path, size, mtime, hash_sha256, is_dir FROM files WHERE hash_sha256 = ?",
                (hash_sha256,),
            ).fetchall()
            return [
                FileEntry(
                    rel_path=r["rel_path"],
                    size=r["size"],
                    mtime=r["mtime"],
                    hash_sha256=r["hash_sha256"],
                    is_dir=bool(r["is_dir"]),
                )
                for r in rows
            ]
        finally:
            conn.close()

    def load_all_entries(self, disk_id: str) -> list[FileEntry]:
        """Load all file entries from a snapshot database."""
        db_path = self._db_path(disk_id)
        if not db_path.exists():
            return []
        conn = self._connect(disk_id)
        try:
            self._ensure_table(conn)
            rows = conn.execute(
                "SELECT rel_path, size, mtime, hash_sha256, is_dir FROM files"
            ).fetchall()
            return [
                FileEntry(
                    rel_path=r["rel_path"],
                    size=r["size"],
                    mtime=r["mtime"],
                    hash_sha256=r["hash_sha256"],
                    is_dir=bool(r["is_dir"]),
                )
                for r in rows
            ]
        finally:
            conn.close()

    def build_hash_index(self, disk_id: str) -> dict[str, list[str]]:
        """Build a hash → [rel_paths] index from the snapshot.

        Used for efficient rename detection.
        """
        entries = self.load_all_entries(disk_id)
        index: dict[str, list[str]] = {}
        for e in entries:
            if e.hash_sha256:
                index.setdefault(e.hash_sha256, []).append(e.rel_path)
        return index

    def delete_snapshot(self, disk_id: str) -> bool:
        """Delete a snapshot database file. Returns True if deleted."""
        db_path = self._db_path(disk_id)
        if db_path.exists():
            db_path.unlink()
            return True
        return False

    def list_snapshots(self) -> list[DiskSnapshot]:
        """List all available snapshots."""
        snapshots = []
        if not self._snapshots_dir.exists():
            return snapshots
        for db_file in self._snapshots_dir.glob(f"*{Config.SNAPSHOT_DB_SUFFIX}"):
            disk_id = db_file.stem
            mtime = db_file.stat().st_mtime
            snapshots.append(DiskSnapshot(
                disk_id=disk_id,
                label=disk_id,
                timestamp=mtime,
            ))
        return sorted(snapshots, key=lambda s: s.timestamp, reverse=True)