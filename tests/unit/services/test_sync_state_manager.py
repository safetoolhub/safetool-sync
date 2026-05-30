# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.sync_state_manager."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.models import ComparisonEntry, DiffType, FileEntry, SyncAction
from services.sync_state_manager import SyncStateManager


def _comparison(rel_path: str, action: SyncAction = SyncAction.COPY_TO_DEST) -> ComparisonEntry:
    return ComparisonEntry(
        rel_path=rel_path,
        diff_type=DiffType.SOURCE_ONLY,
        source=FileEntry(rel_path=rel_path, size=100, mtime=1000.0, is_dir=False),
        dest=None,
        action=action,
    )


@pytest.fixture
def manager():
    with tempfile.TemporaryDirectory() as d:
        mgr = SyncStateManager(db_path=Path(d) / "test_state.db")
        yield mgr


class TestSaveAndLoad:
    def test_save_and_load(self, manager):
        manager.save_state("/source", "/dest", total_ops=10)
        state = manager.load_state()
        assert state is not None
        assert state["source"] == "/source"
        assert state["dest"] == "/dest"
        assert state["total_ops"] == 10

    def test_load_nonexistent(self, manager):
        assert manager.load_state() is None


class TestMarkCompleted:
    def test_mark_single_operation(self, manager):
        manager.save_state("/source", "/dest", total_ops=3)
        manager.mark_completed("a.txt", "copy_to_dest")
        assert manager.get_completed_count() == 1

    def test_mark_multiple(self, manager):
        manager.save_state("/source", "/dest", total_ops=3)
        manager.mark_completed("a.txt", "copy_to_dest")
        manager.mark_completed("b.txt", "copy_to_dest")
        manager.mark_completed("c.txt", "skip")
        assert manager.get_completed_count() == 3

    def test_completed_count_without_db(self, manager):
        assert manager.get_completed_count() == 0


class TestGetPendingOps:
    def test_get_pending(self, manager):
        entries = [_comparison("a.txt"), _comparison("b.txt"), _comparison("c.txt")]
        manager.save_state("/source", "/dest", total_ops=3)
        manager.mark_completed("a.txt", "copy_to_dest")

        pending = manager.get_pending_ops(entries)
        assert len(pending) == 2
        paths = {e.rel_path for e in pending}
        assert "b.txt" in paths
        assert "c.txt" in paths
        assert "a.txt" not in paths

    def test_get_pending_without_db(self, manager):
        entries = [_comparison("a.txt")]
        pending = manager.get_pending_ops(entries)
        assert len(pending) == 1


class TestHasIncompleteSync:
    def test_has_incomplete(self, manager):
        manager.save_state("/source", "/dest", total_ops=5)
        assert manager.has_incomplete_sync() is True

    def test_completed_state(self, manager):
        manager.save_state("/source", "/dest", total_ops=5)
        manager.mark_completed_state()
        assert manager.has_incomplete_sync() is False

    def test_no_state(self, manager):
        assert manager.has_incomplete_sync() is False


class TestClearState:
    def test_clear(self, manager):
        manager.save_state("/source", "/dest", total_ops=5)
        manager.clear_state()
        assert manager.load_state() is None

    def test_clear_nonexistent(self, manager):
        manager.clear_state()