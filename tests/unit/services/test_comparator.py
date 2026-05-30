# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.comparator."""
from __future__ import annotations

import pytest

from services.models import (
    CompareMode,
    ComparisonEntry,
    ConflictPolicy,
    DiffType,
    FileEntry,
    SyncAction,
)
from services.comparator import compare, detect_renames, _compare_entries, _default_action_for_diff


def _entry(rel_path: str, size: int = 100, mtime: float = 1000.0, hash_sha256: str = "", is_dir: bool = False) -> FileEntry:
    return FileEntry(rel_path=rel_path, size=size, mtime=mtime, hash_sha256=hash_sha256, is_dir=is_dir)


class TestCompare:
    def test_identical_files(self):
        source = [_entry("a.txt", size=100, mtime=1000.0)]
        dest = [_entry("a.txt", size=100, mtime=1000.0)]
        results = compare(source, dest, mode=CompareMode.FAST)
        assert len(results) == 1
        assert results[0].diff_type == DiffType.IDENTICAL
        assert results[0].action == SyncAction.SKIP

    def test_source_only(self):
        source = [_entry("new.txt", size=50)]
        dest = []
        results = compare(source, dest)
        assert len(results) == 1
        assert results[0].diff_type == DiffType.SOURCE_ONLY
        assert results[0].action == SyncAction.COPY_TO_DEST

    def test_dest_only(self):
        source = []
        dest = [_entry("orphan.txt", size=50)]
        results = compare(source, dest)
        assert len(results) == 1
        assert results[0].diff_type == DiffType.DEST_ONLY
        assert results[0].action == SyncAction.MOVE_TO_TRASH

    def test_dest_only_skip(self):
        source = []
        dest = [_entry("orphan.txt", size=50)]
        results = compare(source, dest, dest_only_default=SyncAction.SKIP)
        assert results[0].action == SyncAction.SKIP

    def test_modified_file(self):
        source = [_entry("changed.txt", size=200, mtime=2000.0)]
        dest = [_entry("changed.txt", size=100, mtime=1000.0)]
        results = compare(source, dest, mode=CompareMode.FAST)
        assert results[0].diff_type == DiffType.MODIFIED
        assert results[0].action == SyncAction.OVERWRITE_DEST

    def test_mixed_entries(self):
        source = [_entry("same.txt", size=100, mtime=1000.0), _entry("new.txt", size=50)]
        dest = [_entry("same.txt", size=100, mtime=1000.0), _entry("orphan.txt", size=30)]
        results = compare(source, dest, mode=CompareMode.FAST)
        by_path = {e.rel_path: e for e in results}
        assert by_path["same.txt"].diff_type == DiffType.IDENTICAL
        assert by_path["new.txt"].diff_type == DiffType.SOURCE_ONLY
        assert by_path["orphan.txt"].diff_type == DiffType.DEST_ONLY


class TestDetectRenames:
    def test_detect_simple_rename(self):
        entries = [
            ComparisonEntry(rel_path="new_name.txt", diff_type=DiffType.SOURCE_ONLY, source=_entry("new_name.txt", hash_sha256="abc123"), dest=None, action=SyncAction.COPY_TO_DEST),
            ComparisonEntry(rel_path="old_name.txt", diff_type=DiffType.DEST_ONLY, source=None, dest=_entry("old_name.txt", hash_sha256="abc123"), action=SyncAction.MOVE_TO_TRASH),
        ]
        results = detect_renames(entries)
        assert all(e.diff_type == DiffType.RENAMED for e in results)

    def test_no_rename_when_hashes_differ(self):
        entries = [
            ComparisonEntry(rel_path="a.txt", diff_type=DiffType.SOURCE_ONLY, source=_entry("a.txt", hash_sha256="hash_a"), dest=None, action=SyncAction.COPY_TO_DEST),
            ComparisonEntry(rel_path="b.txt", diff_type=DiffType.DEST_ONLY, source=None, dest=_entry("b.txt", hash_sha256="hash_b"), action=SyncAction.MOVE_TO_TRASH),
        ]
        results = detect_renames(entries)
        assert results[0].diff_type == DiffType.SOURCE_ONLY
        assert results[1].diff_type == DiffType.DEST_ONLY

    def test_no_rename_when_no_hash(self):
        entries = [
            ComparisonEntry(rel_path="a.txt", diff_type=DiffType.SOURCE_ONLY, source=_entry("a.txt", hash_sha256=""), dest=None, action=SyncAction.COPY_TO_DEST),
            ComparisonEntry(rel_path="b.txt", diff_type=DiffType.DEST_ONLY, source=None, dest=_entry("b.txt", hash_sha256=""), action=SyncAction.MOVE_TO_TRASH),
        ]
        results = detect_renames(entries)
        assert results[0].diff_type == DiffType.SOURCE_ONLY


class TestCompareEntries:
    def test_fast_mode_identical(self):
        src = _entry("f.txt", size=100, mtime=1000.0)
        dst = _entry("f.txt", size=100, mtime=1000.0)
        assert _compare_entries(src, dst, CompareMode.FAST) == DiffType.IDENTICAL

    def test_fast_mode_modified(self):
        src = _entry("f.txt", size=200, mtime=2000.0)
        dst = _entry("f.txt", size=100, mtime=1000.0)
        assert _compare_entries(src, dst, CompareMode.FAST) == DiffType.MODIFIED

    def test_smart_mode_same_size_mtime(self):
        src = _entry("f.txt", size=100, mtime=1000.0)
        dst = _entry("f.txt", size=100, mtime=1000.0)
        assert _compare_entries(src, dst, CompareMode.SMART) == DiffType.IDENTICAL

    def test_smart_mode_same_hash(self):
        src = _entry("f.txt", size=100, mtime=2000.0, hash_sha256="abc")
        dst = _entry("f.txt", size=100, mtime=1000.0, hash_sha256="abc")
        assert _compare_entries(src, dst, CompareMode.SMART) == DiffType.IDENTICAL


class TestDefaultActionForDiff:
    def test_identical_skips(self):
        assert _default_action_for_diff(DiffType.IDENTICAL, ConflictPolicy.SOURCE_WINS, SyncAction.MOVE_TO_TRASH) == SyncAction.SKIP

    def test_source_only_copies(self):
        assert _default_action_for_diff(DiffType.SOURCE_ONLY, ConflictPolicy.SOURCE_WINS, SyncAction.MOVE_TO_TRASH) == SyncAction.COPY_TO_DEST

    def test_modified_overwrites(self):
        assert _default_action_for_diff(DiffType.MODIFIED, ConflictPolicy.SOURCE_WINS, SyncAction.MOVE_TO_TRASH) == SyncAction.OVERWRITE_DEST