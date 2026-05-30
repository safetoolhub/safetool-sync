# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""Unit tests for services.planner."""
from __future__ import annotations

import pytest

from services.models import (
    ComparisonEntry,
    ConflictPolicy,
    DiffType,
    FileEntry,
    SyncAction,
    SyncPreset,
    VerifyMode,
)
from services.planner import build_plan, apply_preset


def _entry(rel_path: str, size: int = 100) -> FileEntry:
    return FileEntry(rel_path=rel_path, size=size, mtime=1000.0, is_dir=False, hash_sha256="")


def _comparison(rel_path: str, diff_type: DiffType, action: SyncAction, source: FileEntry | None = None, dest: FileEntry | None = None) -> ComparisonEntry:
    return ComparisonEntry(
        rel_path=rel_path,
        diff_type=diff_type,
        source=source or _entry(rel_path),
        dest=dest,
        action=action,
    )


class TestBuildPlan:
    def test_copy_action_counts_bytes(self):
        entries = [
            _comparison("a.txt", DiffType.SOURCE_ONLY, SyncAction.COPY_TO_DEST, source=_entry("a.txt", size=500)),
        ]
        plan = build_plan(entries)
        assert plan.total_copy_bytes == 500
        assert plan.total_delete_count == 0

    def test_delete_replaced_with_trash(self):
        entries = [
            _comparison("b.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, dest=_entry("b.txt")),
        ]
        plan = build_plan(entries, use_trash=True)
        assert entries[0].action == SyncAction.DELETE_FROM_DEST
        updated = plan.entries[0]
        assert updated.action == SyncAction.MOVE_TO_TRASH
        assert plan.total_delete_count == 1

    def test_delete_kept_without_trash(self):
        entries = [
            _comparison("b.txt", DiffType.DEST_ONLY, SyncAction.DELETE_FROM_DEST, dest=_entry("b.txt")),
        ]
        plan = build_plan(entries, use_trash=False)
        assert plan.entries[0].action == SyncAction.DELETE_FROM_DEST

    def test_conflict_mark_review_becomes_skip(self):
        entries = [
            _comparison("c.txt", DiffType.CONFLICT, SyncAction.MARK_REVIEW, source=_entry("c.txt"), dest=_entry("c.txt")),
        ]
        plan = build_plan(entries)
        assert plan.entries[0].action == SyncAction.SKIP

    def test_conflict_already_resolved_kept(self):
        entries = [
            _comparison("c.txt", DiffType.CONFLICT, SyncAction.OVERWRITE_DEST, source=_entry("c.txt"), dest=_entry("c.txt")),
        ]
        plan = build_plan(entries)
        assert plan.entries[0].action == SyncAction.OVERWRITE_DEST

    def test_overwrite_counts_bytes(self):
        entries = [
            _comparison("a.txt", DiffType.MODIFIED, SyncAction.OVERWRITE_DEST, source=_entry("a.txt", size=300)),
        ]
        plan = build_plan(entries)
        assert plan.total_copy_bytes == 300
        assert plan.total_overwrite_count == 1

    def test_rename_count(self):
        entries = [
            _comparison("a.txt", DiffType.RENAMED, SyncAction.RENAME_IN_DEST, source=_entry("a.txt"), dest=_entry("b.txt")),
        ]
        plan = build_plan(entries)
        assert plan.total_rename_count == 1

    def test_empty_entries(self):
        plan = build_plan([])
        assert plan.total_copy_bytes == 0
        assert plan.total_delete_count == 0
        assert plan.total_overwrite_count == 0
        assert plan.total_rename_count == 0


class TestApplyPreset:
    def test_mirror_exact(self):
        config = apply_preset(SyncPreset.MIRROR_EXACT)
        assert config["use_trash"] is False
        assert config["verify_mode"] == VerifyMode.FULL

    def test_mirror_safe(self):
        config = apply_preset(SyncPreset.MIRROR_SAFE)
        assert config["use_trash"] is True

    def test_copy_only(self):
        config = apply_preset(SyncPreset.COPY_ONLY)
        assert config["dest_only_action"] == SyncAction.SKIP

    def test_custom_preset(self):
        config = apply_preset(SyncPreset.CUSTOM)
        assert config["conflict_policy"] == ConflictPolicy.MARK_PENDING