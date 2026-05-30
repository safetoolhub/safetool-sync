# This file is part of SafeTool Sync, licensed under GPLv3 with
# additional terms. See LICENSE or https://safetoolhub.org for details.
"""E2E tests — conflict resolution: grouping, batch resolution, quick actions."""
from __future__ import annotations

import pytest

from services.comparator import compare
from services.conflict_resolver import (
    apply_resolution,
    apply_resolution_all,
    count_conflicts,
    get_quick_resolution,
    group_conflicts,
)
from services.models import (
    CompareMode,
    ComparisonEntry,
    ConflictPolicy,
    ConflictResolution,
    DiffType,
    FileEntry,
    SyncAction,
)
from services.planner import build_plan
from services.scanner import scan_directory
from tests.fixtures.scenario_builder import ScenarioResult


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_comparison(result: ScenarioResult) -> list[ComparisonEntry]:
    src_scan = scan_directory(result.source_root)
    dst_scan = scan_directory(result.dest_root)
    return compare(
        src_scan.entries,
        dst_scan.entries,
        mode=CompareMode.FAST,
        policy=ConflictPolicy.SOURCE_WINS,
    )


def _make_conflict_entries() -> list[ComparisonEntry]:
    """Create synthetic ComparisonEntry objects with CONFLICT diff_type for direct testing."""
    entries = []
    for i in range(3):
        entries.append(ComparisonEntry(
            rel_path=f"docs/report_{i}.docx",
            diff_type=DiffType.CONFLICT,
            source=FileEntry(f"docs/report_{i}.docx", 500 + i * 10, 1000.0 + i, False),
            dest=FileEntry(f"docs/report_{i}.docx", 480 + i * 5, 999.0 + i, False),
            action=SyncAction.MARK_REVIEW,
        ))
    for i in range(2):
        entries.append(ComparisonEntry(
            rel_path=f"images/photo_{i}.png",
            diff_type=DiffType.CONFLICT,
            source=FileEntry(f"images/photo_{i}.png", 2000 + i * 100, 1000.0, False),
            dest=FileEntry(f"images/photo_{i}.png", 1800 + i * 50, 998.0, False),
            action=SyncAction.MARK_REVIEW,
        ))
    entries.append(ComparisonEntry(
        rel_path="readme.txt",
        diff_type=DiffType.IDENTICAL,
        source=FileEntry("readme.txt", 100, 1000.0, False),
        dest=FileEntry("readme.txt", 100, 1000.0, False),
        action=SyncAction.SKIP,
    ))
    for i in range(2):
        entries.append(ComparisonEntry(
            rel_path=f"data/file_{i}.csv",
            diff_type=DiffType.CONFLICT,
            source=FileEntry(f"data/file_{i}.csv", 300, 1000.0, False),
            dest=FileEntry(f"data/file_{i}.csv", 280, 995.0, False),
            action=SyncAction.MARK_REVIEW,
        ))
    return entries


# ── Tests: Conflict Grouping ─────────────────────────────────────────────────


class TestConflictGrouping:
    def test_group_by_extension(self):
        entries = _make_conflict_entries()
        groups = group_conflicts(entries, group_by="extension")

        assert ".docx" in groups
        assert ".png" in groups
        assert ".csv" in groups
        assert len(groups[".docx"]) == 3
        assert len(groups[".png"]) == 2
        assert len(groups[".csv"]) == 2

    def test_group_by_folder(self):
        entries = _make_conflict_entries()
        groups = group_conflicts(entries, group_by="folder")

        assert "docs" in groups
        assert "images" in groups
        assert "data" in groups
        assert len(groups["docs"]) == 3
        assert len(groups["images"]) == 2
        assert len(groups["data"]) == 2

    def test_non_conflict_entries_excluded_from_groups(self):
        entries = _make_conflict_entries()
        groups = group_conflicts(entries, group_by="extension")

        all_grouped = []
        for group_entries in groups.values():
            all_grouped.extend(group_entries)

        for entry in all_grouped:
            assert entry.diff_type == DiffType.CONFLICT

    def test_count_conflicts(self):
        entries = _make_conflict_entries()
        assert count_conflicts(entries) == 7

    def test_count_conflicts_no_conflicts(self):
        entries = [e for e in _make_conflict_entries() if e.diff_type != DiffType.CONFLICT]
        assert count_conflicts(entries) == 0

    def test_group_from_real_scenario(self, conflict_batch_ext_scenario: ScenarioResult):
        comparison = _build_comparison(conflict_batch_ext_scenario)
        modified = [e for e in comparison if e.diff_type == DiffType.MODIFIED]
        assert len(modified) >= 8


# ── Tests: Conflict Resolution — apply_resolution ────────────────────────────


class TestConflictResolution:
    def test_apply_resolution_to_extension_group(self):
        entries = _make_conflict_entries()
        resolution = ConflictResolution(action=SyncAction.OVERWRITE_DEST)

        result = apply_resolution(entries, resolution, group_key=".docx", group_by="extension")

        for entry in result:
            if entry.diff_type == DiffType.CONFLICT and entry.rel_path.endswith(".docx"):
                assert entry.action == SyncAction.OVERWRITE_DEST

        png_conflicts = [e for e in result if e.diff_type == DiffType.CONFLICT and e.rel_path.endswith(".png")]
        for entry in png_conflicts:
            assert entry.action == SyncAction.MARK_REVIEW

    def test_apply_resolution_to_folder_group(self):
        entries = _make_conflict_entries()
        resolution = ConflictResolution(action=SyncAction.KEEP_DEST)

        result = apply_resolution(entries, resolution, group_key="images", group_by="folder")

        for entry in result:
            if entry.diff_type == DiffType.CONFLICT and entry.rel_path.startswith("images/"):
                assert entry.action == SyncAction.KEEP_DEST

        doc_conflicts = [e for e in result if e.diff_type == DiffType.CONFLICT and entry.rel_path.startswith("docs/")]
        for entry in doc_conflicts:
            assert entry.action == SyncAction.MARK_REVIEW

    def test_apply_resolution_all(self):
        entries = _make_conflict_entries()
        resolution = ConflictResolution(action=SyncAction.OVERWRITE_DEST)

        result = apply_resolution_all(entries, resolution)

        for entry in result:
            if entry.diff_type == DiffType.CONFLICT:
                assert entry.action == SyncAction.OVERWRITE_DEST

    def test_apply_resolution_preserves_non_conflicts(self):
        entries = _make_conflict_entries()
        resolution = ConflictResolution(action=SyncAction.OVERWRITE_DEST)

        result = apply_resolution_all(entries, resolution)

        non_conflicts = [e for e in result if e.diff_type != DiffType.CONFLICT]
        assert len(non_conflicts) == 1
        assert non_conflicts[0].action == SyncAction.SKIP

    def test_sequential_group_resolution(self):
        entries = _make_conflict_entries()

        result = apply_resolution(
            entries,
            ConflictResolution(action=SyncAction.OVERWRITE_DEST),
            group_key=".docx",
            group_by="extension",
        )
        result = apply_resolution(
            result,
            ConflictResolution(action=SyncAction.KEEP_DEST),
            group_key=".png",
            group_by="extension",
        )
        result = apply_resolution(
            result,
            ConflictResolution(action=SyncAction.SKIP),
            group_key=".csv",
            group_by="extension",
        )

        for entry in result:
            if entry.diff_type != DiffType.CONFLICT:
                continue
            if entry.rel_path.endswith(".docx"):
                assert entry.action == SyncAction.OVERWRITE_DEST
            elif entry.rel_path.endswith(".png"):
                assert entry.action == SyncAction.KEEP_DEST
            elif entry.rel_path.endswith(".csv"):
                assert entry.action == SyncAction.SKIP


# ── Tests: Quick Resolution ──────────────────────────────────────────────────


class TestQuickResolution:
    def _make_entry(self, src_size: int, dst_size: int, src_mtime: float, dst_mtime: float) -> ComparisonEntry:
        return ComparisonEntry(
            rel_path="conflict_file.txt",
            diff_type=DiffType.CONFLICT,
            source=FileEntry("conflict_file.txt", src_size, src_mtime, False),
            dest=FileEntry("conflict_file.txt", dst_size, dst_mtime, False),
            action=SyncAction.MARK_REVIEW,
        )

    def test_quick_source_wins(self):
        entry = self._make_entry(500, 400, 1000.0, 999.0)
        action = get_quick_resolution(entry, "source")
        assert action == SyncAction.OVERWRITE_DEST

    def test_quick_dest_wins(self):
        entry = self._make_entry(500, 400, 1000.0, 999.0)
        action = get_quick_resolution(entry, "dest")
        assert action == SyncAction.KEEP_DEST

    def test_quick_newest_source_newer(self):
        entry = self._make_entry(500, 400, 1000.0, 999.0)
        action = get_quick_resolution(entry, "newest")
        assert action == SyncAction.OVERWRITE_DEST

    def test_quick_newest_dest_newer(self):
        entry = self._make_entry(500, 400, 999.0, 1000.0)
        action = get_quick_resolution(entry, "newest")
        assert action == SyncAction.KEEP_DEST

    def test_quick_largest_source_larger(self):
        entry = self._make_entry(500, 400, 1000.0, 1000.0)
        action = get_quick_resolution(entry, "largest")
        assert action == SyncAction.OVERWRITE_DEST

    def test_quick_largest_dest_larger(self):
        entry = self._make_entry(400, 500, 1000.0, 1000.0)
        action = get_quick_resolution(entry, "largest")
        assert action == SyncAction.KEEP_DEST

    def test_quick_unknown_returns_mark_review(self):
        entry = self._make_entry(500, 400, 1000.0, 999.0)
        action = get_quick_resolution(entry, "unknown_strategy")
        assert action == SyncAction.MARK_REVIEW


# ── Tests: Conflict → Plan Integration ───────────────────────────────────────


class TestConflictPlanIntegration:
    def test_mark_review_conflicts_are_skipped_in_plan(self):
        entries = _make_conflict_entries()
        plan = build_plan(entries)

        skipped = [e for e in plan.entries if e.diff_type == DiffType.CONFLICT and e.action == SyncAction.SKIP]
        assert len(skipped) == 7

    def test_pre_resolved_overwrite_dest_kept_in_plan(self):
        entries = _make_conflict_entries()
        for entry in entries:
            if entry.diff_type == DiffType.CONFLICT:
                entry.action = SyncAction.OVERWRITE_DEST
        plan = build_plan(entries)

        for entry in plan.entries:
            if entry.diff_type == DiffType.CONFLICT:
                assert entry.action == SyncAction.OVERWRITE_DEST

    def test_pre_resolved_keep_dest_kept_in_plan(self):
        entries = _make_conflict_entries()
        for entry in entries:
            if entry.diff_type == DiffType.CONFLICT:
                entry.action = SyncAction.KEEP_DEST
        plan = build_plan(entries)

        for entry in plan.entries:
            if entry.diff_type == DiffType.CONFLICT:
                assert entry.action == SyncAction.KEEP_DEST

    def test_resolved_conflicts_then_plan(self):
        entries = _make_conflict_entries()
        resolved = apply_resolution(
            entries,
            ConflictResolution(action=SyncAction.OVERWRITE_DEST),
            group_key=".docx",
            group_by="extension",
        )
        resolved = apply_resolution(
            resolved,
            ConflictResolution(action=SyncAction.KEEP_DEST),
            group_key=".png",
            group_by="extension",
        )

        for entry in resolved:
            if entry.diff_type == DiffType.CONFLICT and entry.rel_path.endswith(".docx"):
                assert entry.action == SyncAction.OVERWRITE_DEST
            elif entry.diff_type == DiffType.CONFLICT and entry.rel_path.endswith(".png"):
                assert entry.action == SyncAction.KEEP_DEST

        plan = build_plan(resolved)

        for entry in plan.entries:
            if entry.diff_type == DiffType.CONFLICT:
                if entry.rel_path.endswith(".docx"):
                    assert entry.action == SyncAction.OVERWRITE_DEST
                elif entry.rel_path.endswith(".png"):
                    assert entry.action == SyncAction.KEEP_DEST
                else:
                    assert entry.action == SyncAction.SKIP

    def test_batch_conflict_by_ext_scenario(self, conflict_batch_ext_scenario: ScenarioResult):
        comparison = _build_comparison(conflict_batch_ext_scenario)
        for entry in comparison:
            if entry.diff_type == DiffType.CONFLICT:
                entry.action = SyncAction.OVERWRITE_DEST
        plan = build_plan(comparison)
        assert plan.total_overwrite_count >= 8

    def test_batch_conflict_by_folder_scenario(self, conflict_batch_folder_scenario: ScenarioResult):
        comparison = _build_comparison(conflict_batch_folder_scenario)
        for entry in comparison:
            if entry.diff_type == DiffType.CONFLICT:
                entry.action = SyncAction.OVERWRITE_DEST
        plan = build_plan(comparison)
        assert plan.total_overwrite_count >= 9
