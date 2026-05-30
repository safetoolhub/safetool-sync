# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.snapshot_manager."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.models import FileEntry
from services.snapshot_manager import SnapshotManager


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as d:
        mgr = SnapshotManager(snapshots_dir=Path(d))
        yield mgr


def _entry(rel_path: str, size: int = 100, hash_sha256: str = "") -> FileEntry:
    return FileEntry(rel_path=rel_path, size=size, mtime=1000.0, is_dir=False, hash_sha256=hash_sha256)


class TestSaveAndLoad:
    def test_save_and_load_snapshot(self, manager):
        entries = [_entry("a.txt", size=100, hash_sha256="abc"), _entry("b.txt", size=200, hash_sha256="def")]
        snapshot = manager.save_snapshot("test_disk", "Test Disk", entries)
        assert snapshot.disk_id == "test_disk"
        assert snapshot.label == "Test Disk"

        loaded = manager.load_snapshot("test_disk")
        assert loaded is not None
        assert loaded.disk_id == "test_disk"

    def test_load_nonexistent(self, manager):
        assert manager.load_snapshot("nonexistent") is None

    def test_query_by_path(self, manager):
        entries = [_entry("a.txt", size=100, hash_sha256="abc"), _entry("b.txt", size=200, hash_sha256="def")]
        manager.save_snapshot("disk1", "Disk 1", entries)

        result = manager.query_by_path("disk1", "a.txt")
        assert result is not None
        assert result.rel_path == "a.txt"
        assert result.size == 100
        assert result.hash_sha256 == "abc"

    def test_query_by_path_missing(self, manager):
        entries = [_entry("a.txt", size=100)]
        manager.save_snapshot("disk1", "Disk 1", entries)

        result = manager.query_by_path("disk1", "z.txt")
        assert result is None

    def test_query_by_hash(self, manager):
        entries = [_entry("a.txt", size=100, hash_sha256="abc"), _entry("b.txt", size=200, hash_sha256="abc")]
        manager.save_snapshot("disk1", "Disk 1", entries)

        results = manager.query_by_hash("disk1", "abc")
        assert len(results) == 2

    def test_load_all_entries(self, manager):
        entries = [_entry("a.txt", size=100), _entry("b.txt", size=200)]
        manager.save_snapshot("disk1", "Disk 1", entries)

        loaded = manager.load_all_entries("disk1")
        assert len(loaded) == 2
        paths = {e.rel_path for e in loaded}
        assert "a.txt" in paths
        assert "b.txt" in paths


class TestBuildHashIndex:
    def test_hash_index(self, manager):
        entries = [
            _entry("a.txt", size=100, hash_sha256="hash1"),
            _entry("b.txt", size=200, hash_sha256="hash2"),
            _entry("c.txt", size=300, hash_sha256="hash1"),
        ]
        manager.save_snapshot("disk1", "Disk 1", entries)

        index = manager.build_hash_index("disk1")
        assert "hash1" in index
        assert len(index["hash1"]) == 2
        assert "hash2" in index
        assert len(index["hash2"]) == 1


class TestDeleteSnapshot:
    def test_delete_existing(self, manager):
        entries = [_entry("a.txt")]
        manager.save_snapshot("disk1", "Disk 1", entries)
        assert manager.delete_snapshot("disk1") is True
        assert manager.load_snapshot("disk1") is None

    def test_delete_nonexistent(self, manager):
        assert manager.delete_snapshot("nonexistent") is False


class TestListSnapshots:
    def test_list_empty(self, manager):
        assert manager.list_snapshots() == []

    def test_list_after_save(self, manager):
        entries = [_entry("a.txt")]
        manager.save_snapshot("disk_a", "Disk A", entries)
        manager.save_snapshot("disk_b", "Disk B", entries)

        snapshots = manager.list_snapshots()
        assert len(snapshots) == 2
        ids = {s.disk_id for s in snapshots}
        assert "disk_a" in ids
        assert "disk_b" in ids


class TestUpdateIncremental:
    def test_incremental_update(self, manager):
        entries = [_entry("a.txt", size=100)]
        manager.save_snapshot("disk1", "Disk 1", entries)

        new_entries = [_entry("b.txt", size=200)]
        manager.update_incremental("disk1", new_entries)

        all_entries = manager.load_all_entries("disk1")
        paths = {e.rel_path for e in all_entries}
        assert "a.txt" in paths
        assert "b.txt" in paths