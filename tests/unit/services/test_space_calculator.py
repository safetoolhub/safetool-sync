# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.space_calculator."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.models import ComparisonEntry, DiffType, FileEntry, SyncAction, SyncPlan
from services.space_calculator import (
    calculate_required_space,
    calculate_required_space_per_side,
    check_destination_space,
)


_DEFAULT_SOURCE: object = object()


def _entry(rel_path: str, size: int = 100) -> FileEntry:
    return FileEntry(rel_path=rel_path, size=size, mtime=1000.0, is_dir=False, hash_sha256="")


def _comparison(
    rel_path: str,
    diff_type: DiffType,
    action: SyncAction,
    source: FileEntry | None | object = _DEFAULT_SOURCE,
    dest: FileEntry | None = None,
) -> ComparisonEntry:
    if source is _DEFAULT_SOURCE:
        source = _entry(rel_path)
    return ComparisonEntry(
        rel_path=rel_path,
        diff_type=diff_type,
        source=source,  # type: ignore[arg-type]
        dest=dest,
        action=action,
    )


def _plan(entries: list[ComparisonEntry]) -> SyncPlan:
    return SyncPlan(
        entries=entries,
        total_copy_bytes=0,
        total_delete_count=0,
        total_overwrite_count=0,
        total_rename_count=0,
    )


class TestCalculateRequiredSpace:
    def test_copy_entries_sum(self):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt", size=500)),
            _comparison("b.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("b.txt", size=300)),
        ]
        plan = SyncPlan(entries=entries, total_copy_bytes=800, total_delete_count=0, total_overwrite_count=0, total_rename_count=0)
        assert calculate_required_space(plan) == 800

    def test_overwrite_entries_sum(self):
        entries = [
            _comparison("a.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("a.txt", size=200)),
        ]
        plan = SyncPlan(entries=entries, total_copy_bytes=200, total_delete_count=0, total_overwrite_count=1, total_rename_count=0)
        assert calculate_required_space(plan) == 200

    def test_skip_entries_zero(self):
        entries = [
            _comparison("a.txt", DiffType.IDENTICAL, SyncAction.SKIP),
        ]
        plan = SyncPlan(entries=entries, total_copy_bytes=0, total_delete_count=0, total_overwrite_count=0, total_rename_count=0)
        assert calculate_required_space(plan) == 0

    def test_mixed_entries(self):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt", size=1000)),
            _comparison("b.txt", DiffType.IDENTICAL, SyncAction.SKIP),
            _comparison("c.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("c.txt", size=500)),
        ]
        plan = SyncPlan(entries=entries, total_copy_bytes=1500, total_delete_count=0, total_overwrite_count=1, total_rename_count=0)
        assert calculate_required_space(plan) == 1500


class TestCheckDestinationSpace:
    def test_sufficient_space(self):
        with tempfile.TemporaryDirectory() as d:
            result = check_destination_space(Path(d), 1)
            assert result.free_bytes >= 0
            assert isinstance(result.sufficient, bool)
            assert isinstance(result.required_bytes, int)

    def test_zero_required_always_sufficient(self):
        with tempfile.TemporaryDirectory() as d:
            result = check_destination_space(Path(d), 0)
            assert result.sufficient is True
            assert result.shortfall_bytes == 0


class TestCalculateRequiredSpacePerSide:
    def test_per_side_unidirectional_returns_zero_source(self):
        entries = [
            _comparison(
                "a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST,
                source=_entry("a.txt", size=500),
            ),
            _comparison(
                "b.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST,
                source=_entry("b.txt", size=300),
            ),
        ]
        dest_required, source_required = calculate_required_space_per_side(_plan(entries))
        assert dest_required == 800
        assert source_required == 0

    def test_per_side_bidirectional_returns_both(self):
        entries = [
            _comparison(
                "a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST,
                source=_entry("a.txt", size=400),
            ),
            _comparison(
                "b.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST,
                source=_entry("b.txt", size=100),
            ),
            _comparison(
                "c.txt", DiffType.DEST_ONLY, SyncAction.COPY_TO_SOURCE,
                source=None,
                dest=_entry("c.txt", size=250),
            ),
            _comparison(
                "d.txt", DiffType.DEST_ONLY, SyncAction.COPY_TO_SOURCE,
                source=None,
                dest=_entry("d.txt", size=50),
            ),
        ]
        dest_required, source_required = calculate_required_space_per_side(_plan(entries))
        assert dest_required == 500
        assert source_required == 300

    def test_per_side_overwrite_counted(self):
        entries = [
            _comparison(
                "a.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST,
                source=_entry("a.txt", size=700),
                dest=_entry("a.txt", size=200),
            ),
            _comparison(
                "b.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_SOURCE,
                source=_entry("b.txt", size=10),
                dest=_entry("b.txt", size=900),
            ),
        ]
        dest_required, source_required = calculate_required_space_per_side(_plan(entries))
        assert dest_required == 700
        assert source_required == 900

    def test_per_side_skip_actions_ignored(self):
        entries = [
            _comparison(
                "identical.txt", DiffType.IDENTICAL, SyncAction.SKIP,
                source=_entry("identical.txt", size=100),
                dest=_entry("identical.txt", size=100),
            ),
            _comparison(
                "conflict.txt", DiffType.CONFLICT, SyncAction.MARK_REVIEW,
                source=_entry("conflict.txt", size=400),
                dest=_entry("conflict.txt", size=600),
            ),
            _comparison(
                "obsolete.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST,
                source=None,
                dest=_entry("obsolete.txt", size=2000),
            ),
            _comparison(
                "trashable.txt", DiffType.DEST_ONLY, SyncAction.MOVE_TO_TRASH,
                source=None,
                dest=_entry("trashable.txt", size=3000),
            ),
        ]
        dest_required, source_required = calculate_required_space_per_side(_plan(entries))
        assert dest_required == 0
        assert source_required == 0

    def test_per_side_handles_none_sides(self):
        entries = [
            _comparison(
                "missing_src.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST,
                source=None,
                dest=None,
            ),
            _comparison(
                "missing_dst.txt", DiffType.DEST_ONLY, SyncAction.COPY_TO_SOURCE,
                source=None,
                dest=None,
            ),
            _comparison(
                "ok_dest.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST,
                source=_entry("ok_dest.txt", size=120),
                dest=None,
            ),
            _comparison(
                "ok_source.txt", DiffType.DEST_ONLY, SyncAction.COPY_TO_SOURCE,
                source=None,
                dest=_entry("ok_source.txt", size=80),
            ),
        ]
        dest_required, source_required = calculate_required_space_per_side(_plan(entries))
        assert dest_required == 120
        assert source_required == 80