# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.conflict_resolver."""
from __future__ import annotations

import pytest

from services.models import ComparisonEntry, ConflictPolicy, ConflictResolution, DiffType, FileEntry, SyncAction
from services.conflict_resolver import group_conflicts, apply_resolution, apply_resolution_all, count_conflicts, get_quick_resolution


def _entry(rel_path: str, size: int = 100, mtime: float = 1000.0) -> FileEntry:
    return FileEntry(rel_path=rel_path, size=size, mtime=mtime, is_dir=False, hash_sha256="")


def _conflict(rel_path: str, source: FileEntry | None = None, dest: FileEntry | None = None) -> ComparisonEntry:
    return ComparisonEntry(
        rel_path=rel_path,
        diff_type=DiffType.CONFLICT,
        source=source or _entry(rel_path),
        dest=dest or _entry(rel_path),
        action=SyncAction.MARK_REVIEW,
    )


class TestGroupConflicts:
    def test_group_by_extension(self):
        entries = [
            _conflict("photo.jpg"),
            _conflict("doc.pdf"),
            _conflict("image.jpg"),
        ]
        groups = group_conflicts(entries, group_by="extension")
        assert ".jpg" in groups
        assert ".pdf" in groups
        assert len(groups[".jpg"]) == 2
        assert len(groups[".pdf"]) == 1

    def test_group_by_folder(self):
        entries = [
            _conflict("docs/report.pdf"),
            _conflict("docs/letter.pdf"),
            _conflict("photos/img.jpg"),
        ]
        groups = group_conflicts(entries, group_by="folder")
        assert "docs" in groups
        assert "photos" in groups

    def test_non_conflicts_excluded(self):
        entries = [
            ComparisonEntry(rel_path="ok.txt", diff_type=DiffType.IDENTICAL, source=_entry("ok.txt"), dest=_entry("ok.txt"), action=SyncAction.SKIP),
            _conflict("problem.doc"),
        ]
        groups = group_conflicts(entries, group_by="extension")
        assert len(groups) == 1
        assert ".doc" in groups

    def test_empty_entries(self):
        groups = group_conflicts([])
        assert groups == {}


class TestApplyResolution:
    def test_apply_source_wins(self):
        entries = [_conflict("f.txt")]
        resolution = ConflictResolution(action=SyncAction.OVERWRITE_DEST)
        result = apply_resolution(entries, resolution)
        assert result[0].action == SyncAction.OVERWRITE_DEST

    def test_apply_keep_dest(self):
        entries = [_conflict("f.txt")]
        resolution = ConflictResolution(action=SyncAction.KEEP_DEST)
        result = apply_resolution(entries, resolution)
        assert result[0].action == SyncAction.KEEP_DEST

    def test_apply_to_specific_group(self):
        entries = [
            _conflict("photo.jpg"),
            _conflict("doc.pdf"),
        ]
        resolution = ConflictResolution(action=SyncAction.OVERWRITE_DEST)
        result = apply_resolution(entries, resolution, group_key=".jpg", group_by="extension")
        photo = next(e for e in result if e.rel_path == "photo.jpg")
        doc = next(e for e in result if e.rel_path == "doc.pdf")
        assert photo.action == SyncAction.OVERWRITE_DEST
        assert doc.action == SyncAction.MARK_REVIEW


class TestApplyResolutionAll:
    def test_resolve_all(self):
        entries = [
            _conflict("a.txt"),
            _conflict("b.pdf"),
            ComparisonEntry(rel_path="c.txt", diff_type=DiffType.IDENTICAL, source=_entry("c.txt"), dest=_entry("c.txt"), action=SyncAction.SKIP),
        ]
        resolution = ConflictResolution(action=SyncAction.KEEP_DEST)
        result = apply_resolution_all(entries, resolution)
        conflicts = [e for e in result if e.diff_type == DiffType.CONFLICT]
        assert all(e.action == SyncAction.KEEP_DEST for e in conflicts)
        identical = next(e for e in result if e.rel_path == "c.txt")
        assert identical.action == SyncAction.SKIP


class TestCountConflicts:
    def test_count(self):
        entries = [
            _conflict("a.txt"),
            _conflict("b.pdf"),
            ComparisonEntry(rel_path="c.txt", diff_type=DiffType.IDENTICAL, source=_entry("c.txt"), dest=_entry("c.txt"), action=SyncAction.SKIP),
        ]
        assert count_conflicts(entries) == 2

    def test_count_zero(self):
        entries = [
            ComparisonEntry(rel_path="a.txt", diff_type=DiffType.IDENTICAL, source=_entry("a.txt"), dest=_entry("a.txt"), action=SyncAction.SKIP),
        ]
        assert count_conflicts(entries) == 0


class TestGetQuickResolution:
    def test_source_wins(self):
        entry = _conflict("f.txt")
        assert get_quick_resolution(entry, "source") == SyncAction.OVERWRITE_DEST

    def test_dest_wins(self):
        entry = _conflict("f.txt")
        assert get_quick_resolution(entry, "dest") == SyncAction.KEEP_DEST

    def test_newest_source_newer(self):
        entry = ComparisonEntry(
            rel_path="f.txt", diff_type=DiffType.CONFLICT,
            source=FileEntry(rel_path="f.txt", size=100, mtime=2000.0, is_dir=False, hash_sha256=""),
            dest=FileEntry(rel_path="f.txt", size=50, mtime=1000.0, is_dir=False, hash_sha256=""),
            action=SyncAction.MARK_REVIEW,
        )
        assert get_quick_resolution(entry, "newest") == SyncAction.OVERWRITE_DEST

    def test_newest_dest_newer(self):
        entry = ComparisonEntry(
            rel_path="f.txt", diff_type=DiffType.CONFLICT,
            source=FileEntry(rel_path="f.txt", size=50, mtime=1000.0, is_dir=False, hash_sha256=""),
            dest=FileEntry(rel_path="f.txt", size=100, mtime=2000.0, is_dir=False, hash_sha256=""),
            action=SyncAction.MARK_REVIEW,
        )
        assert get_quick_resolution(entry, "newest") == SyncAction.KEEP_DEST

    def test_largest_source_bigger(self):
        entry = ComparisonEntry(
            rel_path="f.txt", diff_type=DiffType.CONFLICT,
            source=FileEntry(rel_path="f.txt", size=200, mtime=1000.0, is_dir=False, hash_sha256=""),
            dest=FileEntry(rel_path="f.txt", size=50, mtime=1000.0, is_dir=False, hash_sha256=""),
            action=SyncAction.MARK_REVIEW,
        )
        assert get_quick_resolution(entry, "largest") == SyncAction.OVERWRITE_DEST

    def test_unknown_action(self):
        entry = _conflict("f.txt")
        assert get_quick_resolution(entry, "unknown") == SyncAction.MARK_REVIEW